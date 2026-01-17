import os
import json
import asyncio
from typing import Any, Dict
from scorsese.services.kie_client import KIEClient
from scorsese.services.llm_client import LLMClient
from scorsese.models import ViralScript
from scorsese.services.moviepy_service import MoviePyService
from scorsese.services.image_upload_service import ImageUploadService
from scorsese.services.music_service import MusicService
from scorsese.services.elevenlabs_service import ElevenLabsService
from scorsese.services.manim_service import ManimService
from scorsese.services.video_service import VideoService
from scorsese.services.pipeline_service import PipelineService

try:
    from agents import Agent, Runner, function_tool
except ImportError:
    class Agent:
        def __init__(self, **kwargs): pass
    class Runner:
        @staticmethod
        async def run(**kwargs): pass
    def function_tool(f): return f


class AgenticApproach:
    def __init__(self, kie_client: KIEClient, logic_model: str = "gpt-4o-mini", creative_model: str = "openai/gpt-4o"):
        """
        logic_model: The model used by the Agents themselves (Nano/Mini).
        creative_model: The model used by the consult_expert_writer tool (OpenRouter/Sonnet/etc).
        """
        self.kie = kie_client
        self.logic_model = logic_model
        self.creative_model = creative_model
        
        # Explicitly configure for OpenRouter to avoid key confusion
        or_key = os.getenv("OPENROUTER_API_KEY")
        or_url = "https://openrouter.ai/api/v1"
        print(f"[System] Initializing Creative Writer with model: {creative_model} via OpenRouter...")
        
        self.creative_llm = LLMClient(
            model=creative_model,
            api_key=or_key,
            base_url=or_url
        )
        self.speech_llm = LLMClient() # Default OpenAI client for TTS
        
        self.moviepy_service = MoviePyService()
        self.image_upload_service = ImageUploadService()
        self.music_service = MusicService(kie_client=self.kie)
        self.elevenlabs_service = ElevenLabsService()
        self.manim_service = ManimService()

        # Core Services
        self.video_service = VideoService(self.kie, self.image_upload_service, self.moviepy_service)
        self.pipeline_service = PipelineService(self.video_service, self.moviepy_service)
        
        self.guide_content = self._load_guide()
        
        # --- Tools ---
        
        @function_tool
        def generate_video_segment(prompt: str, mode: str = "normal", image_url: str = None) -> str:
            """
            Generates a video segment using KIE.AI (Grok).
            Returns the Task ID. You must check status later to get the URL.
            Example: generate_video_segment("cat jumping", "fun", image_url="http://...")
            """
            return self.video_service.generate_segment(prompt, mode, image_url)

        @function_tool
        def check_video_status(task_id: str) -> str:
            """
            Checks the status of a video generation task.
            Returns status and URL if successful.
            """
            return self.video_service.check_status(task_id)

        @function_tool
        def consult_expert_writer(topic: str, audience: str, goal: str, specific_instructions: str = "") -> str:
            """
            Calls an Expert Viral Writer (High-IQ LLM) to draft or edit a Tikok script.
            Use this for INITIAL DRAFTS and for REFINING CONTENT.
            Returns the full script content (usually JSON-like text).
            """
            print(f"[Tool: Expert Writer] Drafting for {topic}...")
            
            system_prompt = f"""
            You are a Viral Content Strategist & Video Prompt Engineer.
            
            GOAL: Write a TikTok script based on the guide:
            {self.guide_content[:15000]}
            
            CRITICAL: For the 'visual' field of each segment, you MUST use "Structural Prompting" for high-fidelity AI generation.
            Format visual descriptions as:
            "Subject: [Description of the character/object]. Action: [Precise movement vectors, MUST INCLUDE 'speaking to camera' if there is dialogue]. Environment: [Lighting/Context]. Technical: [Camera angle/fps]."
            
            RULES FOR VISUALS:
            1. SUBJECT: MUST be generic to match the input image (e.g., "The character in the image", "The speaker"). DO NOT invent gender/clothing details (e.g., "Male trader in hoodie") as this causes morphing artifacts if it conflicts with the user's image.
            2. NO TEXT: Do NOT include requests for "Text Overlay", "Captions", or "UI elements" in the visual description. The video should be clean.
            3. LIP SYNC: If the character speaks, the Action MUST include "speaking to the camera".
            
            Example Visual:
            "Subject: The character in the image. Action: Speaking to the camera with an excited expression, leaning in. Environment: A neon-lit room. Technical: Low angle, 24fps."

            PRIORITY: Focus on MOTIVATED CAMERA MOVEMENT (whip pans, zooms) and EXPRESSIVE FACIAL ACTIONS.
            AVOID: Excessive VFX (confetti, explosions) or "busy" elements unless the script demands it.
            
            JSON STRUCTURE REQUIREMENTS:
            1. Fields: 'visual', 'spoken', 'text_overlay', 'music', 'sound_effects'.
            2. SPOKEN TEXT: MUST be spoken naturally. NEVER put raw URLs, wallet hashes, or code snippets in the 'spoken' field (the AI cannot read them). Use "Link in bio" or "Address on screen".
            3. TEXT OVERLAY: Put all on-screen text HERE, not in 'visual'.
            
            Return a valid JSON structure (ViralScript schema).
            Ensure segments are <6 seconds.
            
            CRITICAL CONSTRAINT ADHERENCE:
            - If the user asks for "one segment", "single segment", or "extending the last segment", you MUST output EXACTLY ONE segment in the JSON list.
            - Do not generate Intro/Outro segments unless explicitly requested.
            - Do not ignore the user's explicit request for brevity.
            - If "Extending", the context is implied (continuation), so start immediately (no "Hey guys!" intro).
            """
            
            user_prompt = f"""
            Topic: {topic}
            Audience: {audience}
            Goal: {goal}
            Additional Instructions/Edits: {specific_instructions}
            
            Write/Rewrite the script with STRUCTURAL VISUAL PROMPTS.
            """
            
            try:
                # Use the creative_llm client (OpenRouter/High-IQ)
                result = self.creative_llm.generate_creative_completion(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    model=self.creative_model
                )
                return result
            except Exception as e:
                return f"Error calling expert writer: {e}"

        @function_tool
        def execute_editor_script(script_code: str, save_name: str = None) -> str:
            """
            Executes a Python script that uses MoviePy to edit videos.
            The script should import moviepy classes (e.g., VideoFileClip, TextClip, CompositeVideoClip).
            
            Args:
                script_code: The Python code to execute.
                save_name: Optional. If provided (e.g., "my_script"), the script is saved to 'scorsese/scripts/my_script.py'. 
                           Use this when the user asks to "save" the script or for reusable operations.
            
            Returns the stdout/stderr of the execution.
            """
            print(f"[Tool: MoviePy] Executing script...")
            if save_name:
                print(f"  > Saving script as: {save_name}")
            return self.moviepy_service.run_script(script_code, save_name=save_name)

        def _download_to_temp(url: str, suffix: str = ".mp4") -> str:
            """Helper to download a file to a temp path."""
            import tempfile
            import requests
            import uuid
            
            try:
                fname = f"temp_dl_{uuid.uuid4()}{suffix}"
                fpath = os.path.join(tempfile.gettempdir(), fname)
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    with open(fpath, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                return fpath
            except Exception as e:
                print(f"Download failed: {e}")
                return None

        @function_tool
        def run_daisychain_pipeline(segments_json: str, initial_image_url: str = None) -> str:
            """
            Executes a robust DAISYCHAIN generation pipeline.
            Guarantees that the output of Segment N is used as the input for Segment N+1.
            
            Args:
                segments_json: A JSON string list of dicts. Example:
                               '[{"prompt": "A cat", "mode": "normal"}, {"prompt": "The cat flies", "mode": "fun"}]'
                initial_image_url: Optional starting image URL for the first segment.
            
            Returns:
                Summary of generation with final local paths.
            """
            return self.pipeline_service.run_daisychain(segments_json, initial_image_url)

        @function_tool
        def stitch_videos(video_paths: str) -> str:
            """
            Stitches (concatenates) multiple video files into a single video.
            
            Args:
                video_paths: A JSON string list of absolute file paths to the videos. 
                             Example: '["C:/path/to/vid1.mp4", "C:/path/to/vid2.mp4"]'
            
            Returns:
                Path to the stitched video.
            """
            try:
                paths = json.loads(video_paths)
                if not isinstance(paths, list) or len(paths) < 2:
                    return "Error: Please provide a list of at least 2 video paths."
            except:
                return "Error: video_paths must be a valid JSON string list."
                
            return self.pipeline_service.stitch_videos(paths)

        @function_tool
        def extract_and_upload_last_frame(video_url: str) -> str:
            """
            Bridge tool for Step-by-Step Daisychaining.
            1. Downloads the video.
            2. Extracts the last frame.
            3. Uploads it to a public host.
            
            Args:
                video_url: URL of the video to extract from.
            
            Returns:
                The URL of the extracted frame (use this as `image_url` for the next segment).
            """
            return self.video_service.extract_and_upload_last_frame(video_url)

        @function_tool
        def upload_local_image(file_path: str) -> str:
            """
            Uploads a local image file to a temporary public host (0x0.st) to get a URL.
            Use this when you have a local file (e.g. 'frame.png') that needs to be passed to 'generate_video_segment'.
            Returns the public URL.
            """
            print(f"[Tool: Uploader] Uploading {file_path}...")
            try:
                url = self.image_upload_service.upload_image(file_path)
                print(f"  > Uploaded to: {url}")
                return url
            except Exception as e:
                return f"Error uploading image: {e}"



        @function_tool
        def add_background_music(video_path: str, music_prompt: str = None, local_music_path: str = None, volume: float = 0.1) -> str:
            """
            Adds background music to a video. Can generate music (placeholder) or use a local file.
            
            Args:
                video_path: Path to the video.
                music_prompt: Prompt to generate music (if no local path).
                local_music_path: Optional path to an existing music file.
                volume: signal volume (0.0 to 1.0) relative to original audio.
            """
            print(f"[Tool: Music] Adding music to {video_path}...")
            
            music_file = None
            if local_music_path:
                music_file = self.music_service.get_local_music(local_music_path)
            elif music_prompt:
                music_file = self.music_service.generate_music(music_prompt)
            else:
                return "Error: Provide either music_prompt or local_music_path."
            
            if not music_file:
                return "Error: Could not generate or find music."

            import uuid
            output_filename = f"music_added_{uuid.uuid4().hex[:6]}.mp4"
            output_path = os.path.join(os.path.dirname(video_path), output_filename)
            
            script = f"""
import os
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip

video_path = r"{video_path}"
music_path = r"{music_file}"
output_path = r"{output_path}"
volume = {volume}

try:
    video = VideoFileClip(video_path)
    music = AudioFileClip(music_path).with_volume_scaled(volume)
    
    # Loop music if shorter than video, or trim if longer
    if music.duration < video.duration:
        music = music.with_effects([lambda c: c.loop(duration=video.duration)])
    else:
        music = music.subclipped(0, video.duration)
        
    # Mix with original video audio if it exists
    original_audio = video.audio
    if original_audio:
        final_audio = CompositeAudioClip([original_audio, music])
    else:
        final_audio = music
        
    final_video = video.with_audio(final_audio)
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")
    print(f"MUSIC_SUCCESS: {{output_path}}")

except Exception as e:
    print(f"MUSIC_ERROR: {{e}}")
"""
            log = self.moviepy_service.run_script(script, save_name="add_music")
            if "MUSIC_SUCCESS" in log:
                return f"Success! Music added: {output_path}"
            else:
                return f"Failed to add music. Log: {log}"

        @function_tool
        def overlay_text(video_path: str, text: str, position: str = "bottom", color: str = "white", font_size: int = 50) -> str:
            """
            Overlays text on the video.
            
            Args:
                video_path: Path to video.
                text: Text to display.
                position: 'center', 'bottom', 'top'.
                color: Color name (white, yellow, red).
                font_size: Size of font.
            """
            print(f"[Tool: Overlay] Adding text '{text}' to {video_path}...")
            
            import uuid
            output_filename = f"text_overlay_{uuid.uuid4().hex[:6]}.mp4"
            output_path = os.path.join(os.path.dirname(video_path), output_filename)
            
            script = f"""
import os
from moviepy import VideoFileClip, TextClip, CompositeVideoClip

video_path = r"{video_path}"
output_path = r"{output_path}"
text_content = "{text}"
pos = "{position}"
col = "{color}"
fs = {font_size}

try:
    video = VideoFileClip(video_path)
    
    # Create TextClip
    # Note: MoviePy v2 requirements for TextClip can be tricky with fonts.
    # We will try default. If fails, we might need ImageMagick or specific font path.
    # Assuming basic configuration for now.
    
    txt_clip = TextClip(font="Arial", text=text_content, font_size=fs, color=col)
    txt_clip = txt_clip.with_position(pos).with_duration(video.duration)
    
    final_video = CompositeVideoClip([video, txt_clip])
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")
    
    print(f"OVERLAY_SUCCESS: {{output_path}}")

except Exception as e:
    print(f"OVERLAY_ERROR: {{e}}")
"""
            log = self.moviepy_service.run_script(script, save_name="overlay_text")
            if "OVERLAY_SUCCESS" in log:
                return f"Success! Text added: {output_path}"
            else:
                return f"Failed to add text. Log: {log}"

        @function_tool
        def extend_video_segment(video_path: str, prompt: str, mode: str = "normal") -> str:
            """
            Extends a video by taking its last frame and generating a new segment from it.
            
            Args:
                video_path: Path to the existing video file.
                prompt: Prompt for the new segment.
                mode: 'normal' or 'fun'.
            
            Returns:
                Summary with URL of the new segment.
            """
            return self.video_service.extend_segment(video_path, prompt, mode)

        @function_tool
        def advanced_voice_change(video_path: str, voice_id: str = "JBFqnCBsd6RMkjVDRZzb") -> str:
            """
            Advanced Audio Pipeline:
            1. Extracts audio from video.
            2. Uses KIE.AI to strip background noise/music (Isolate Voice).
            3. Uses ElevenLabs to change the voice (Speech-to-Speech) while keeping pacing.
            4. Remarries audio to video.
            
            Args:
                video_path: Path to video file.
                voice_id: ElevenLabs Voice ID (default: 'Nicole').
            """
            print(f"[Tool: Adv.Voice] Starting advanced pipeline for {video_path}...")
            
            # 1. Extract Audio
            import uuid
            audio_name = f"extracted_audio_{uuid.uuid4().hex[:6]}.mp3"
            
            extract_script = f"""
import os
from moviepy import VideoFileClip
video_path = r"{video_path}"
output_path = os.path.join(os.getcwd(), "scorsese", "{audio_name}")
try:
    with VideoFileClip(video_path) as clip:
        if clip.audio:
            clip.audio.write_audiofile(output_path)
            print(f"AUDIO_EXTRACTED: {{output_path}}")
        else:
            print("NO_AUDIO_FOUND")
except Exception as e:
    print(f"EXTRACT_ERROR: {{e}}")
"""
            log = self.moviepy_service.run_script(extract_script)
            extracted_audio_path = os.path.join(os.getcwd(), "scorsese", audio_name)
            
            if not os.path.exists(extracted_audio_path):
                return f"Failed to extract audio. Log: {log}"
            
            try:
                # 2. Upload to Public URL (for KIE)
                # Assuming image_upload_service handles general file uploads via 0x0.st
                print(f"  > Uploading audio for KIE processing...")
                public_url = self.image_upload_service.upload_image(extracted_audio_path)
                print(f"  > Audio URL: {public_url}")
                
                # 3. KIE Audio Isolation
                print(f"  > Submitting KIE Isolation task...")
                task_id = self.kie.isolate_audio(public_url)
                
                print(f"  > Waiting for isolation (Task: {task_id})...")
                status = self.kie.wait_for_task(task_id, timeout=300)
                
                if status.get("state") != "success":
                    return f"KIE Isolation failed: {status.get('failMsg')}"
                
                # KIE returns a resultJson with resultUrls (usually list)
                # Check structure from docs or logs. KIE client parse logic handles json load.
                # 'video_urls' in wait_for_task might be misnamed if we reuse it, but let's check KIEClient.get_task_status
                # It puts 'video_urls' -> res_json.get('resultUrls', [])
                
                cleaned_audio_urls = status.get("video_urls", [])
                if not cleaned_audio_urls:
                    return "KIE Success but no audio URL found."
                
                cleaned_url = cleaned_audio_urls[0]
                print(f"  > Cleaned Audio URL: {cleaned_url}")
                
                # 4. Download Cleaned Audio
                cleaned_local = _download_to_temp(cleaned_url, suffix=".mp3")
                if not cleaned_local:
                    return "Failed to download cleaned audio."
                
                # 5. ElevenLabs Voice Change
                print(f"  > Changing Voice (ID: {voice_id})...")
                final_audio_path = self.elevenlabs_service.change_voice(cleaned_local, voice_id)
                print(f"  > Voice Changed: {final_audio_path}")
                
                # 6. Remarry to Video
                final_video_name = f"final_voice_{uuid.uuid4().hex[:6]}.mp4"
                final_video_path = os.path.join(os.getcwd(), "scorsese", "output", final_video_name)
                os.makedirs(os.path.dirname(final_video_path), exist_ok=True)
                
                merge_script = f"""
import os
from moviepy import VideoFileClip, AudioFileClip
video_path = r"{video_path}"
audio_path = r"{final_audio_path}"
output_path = r"{final_video_path}"

try:
    video = VideoFileClip(video_path)
    audio = AudioFileClip(audio_path)
    
    # Trim audio to video duration if needed
    if audio.duration > video.duration:
        audio = audio.subclipped(0, video.duration)
        
    final = video.with_audio(audio)
    final.write_videofile(output_path, codec="libx264", audio_codec="aac")
    print(f"MERGE_SUCCESS: {{output_path}}")
except Exception as e:
    print(f"MERGE_ERROR: {{e}}")
"""
                merge_log = self.moviepy_service.run_script(merge_script, save_name="merge_voice")
                
                # Cleanup temps
                try: 
                    os.remove(extracted_audio_path)
                    os.remove(cleaned_local)
                    os.remove(final_audio_path)
                except: pass
                
                if "MERGE_SUCCESS" in merge_log:
                    return f"SUCCESS. Video with replaced voice: {final_video_path}"
                else:
                    return f"Failed to merge final video. Log: {merge_log}"

            except Exception as e:
                return f"Advanced Pipeline Error: {e}"

            except Exception as e:
                return f"Advanced Pipeline Error: {e}"

        @function_tool
        def generate_manim_animation(prompt: str) -> str:
            """
            Generates a data visualization or mathematical animation using Manim.
            The agent uses the Creative Writer (Expert Coder) to generate the Manim script.
            Returns the path to the generated MP4 file.
            
            Args:
                prompt: Description of the animation (e.g., "A pie chart showing market share 70% vs 30%").
            """
            print(f"[Tool: Manim] Generating animation for: {prompt}")
            
            # 1. Generate Script via Expert Coder
            sys_prompt = """
            You are an expert Manim (Community Edition) developer.
            Write a complete, runnable Python script for the requested animation.
            
            Key Rules:
            1. IMPORT: `from manim import *`
            2. CLASS: Define a class `GeneratedScene(Scene)`.
            3. CONTENT: Implement `def construct(self):`.
            4. COMPATIBILITY: Use Manim v0.17+ syntax (e.g. `Circle.animate.shift()`).
            5. ONLY CODE: Return ONLY the python code, no markdown backticks or explanation.
            """
            
            try:
                script_code = self.creative_llm.generate_completion(prompt, system_prompt=sys_prompt)
                # Cleanup potential formatting
                script_code = script_code.replace("```python", "").replace("```", "").strip()
                
                # 2. Render
                video_path = self.manim_service.render_scene(script_code, "GeneratedScene", quality="m")
                return f"SUCCESS. Manim Animation generated: {video_path}"
                
            except Exception as e:
                return f"Manim Generation Failed: {e}"

        @function_tool
        def overlay_foreground_video(background_video: str, foreground_video: str, position: str = "center", scale: float = 0.8) -> str:
            """
            Overlays a foreground video (e.g. Manim animation) onto a background video.
            Attempts to key out black background from the foreground video if alpha channel is missing, 
            though Manim usually renders black backgrounds.
            
            Args:
                background_video: Path to main video.
                foreground_video: Path to overlay video.
                position: 'center', 'top', 'bottom', 'left', 'right', or (x,y).
                scale: Scale factor for foreground (0.0 to 1.0).
            """
            print(f"[Tool: Overlay] Overlaying {foreground_video} on {background_video}...")
            import uuid
            output_name = f"overlay_{uuid.uuid4().hex[:6]}.mp4"
            final_path = os.path.join(os.getcwd(), "scorsese", "output", output_name)
            
            script = f"""
import os
from moviepy import VideoFileClip, CompositeVideoClip, vfx

bg_path = r"{background_video}"
fg_path = r"{foreground_video}"
output_path = r"{final_path}"

try:
    bg = VideoFileClip(bg_path)
    fg = VideoFileClip(fg_path)
    
    # Scale foreground
    fg = fg.resized(scale={scale})
    
    # Position
    pos = "{position}"
    # Simple mapping for common strings, or let moviepy handle it
    
    fg = fg.with_position(pos)
    
    # Simple Luma Key for Manim (Black Background -> Transparent)
    # MoviePy 2.0+ mask color handling
    fg = fg.with_effects([vfx.MaskColor(color=[0,0,0], threshold=10, stiffness=5)])
    
    # Loop fg if shorter than bg, or vice versa?
    # Usually we want the animation to play once or loop over the bg.
    # Let's assume we play it once on top of bg.
    
    # If FG is longer than BG, extend BG? No, usually clip FG or extend BG last frame.
    # Simple compositing:
    final = CompositeVideoClip([bg, fg])
    
    final.write_videofile(output_path, codec="libx264", audio_codec="aac")
    print(f"OVERLAY_SUCCESS: {{output_path}}")
    
except Exception as e:
    print(f"OVERLAY_ERROR: {{e}}")
"""
            log = self.moviepy_service.run_script(script, save_name="manim_overlay")
            
            if "OVERLAY_SUCCESS" in log:
                return f"SUCCESS. Overlay video created: {final_path}"
            else:
                return f"Failed to overlay video. Log: {log}"

        @function_tool
        def generate_music_track(prompt: str, instrumental: bool = True) -> str:
            """
            Generates a music track using Suno via KIE.
            Returns the path to the downloaded MP3 file.
            The user should listen to this file before using `add_background_music`.
            
            Args:
                prompt: Description of the music (genre, mood, instruments).
                instrumental: Whether it should be instrumental (default: True).
            """
            return self.music_service.generate_music(prompt, instrumental)

        # --- Agents ---

        self.drafter_agent = Agent(
            name="Drafter",
            model=self.logic_model,
            instructions="""
            ROLE: Proxy for the Expert Writer Tool.
            
            RULES:
            1. You DO NOT write scripts. You DO NOT draft content.
            2. For ANY request regarding a script, video idea, or creative text, you MUST call the `consult_expert_writer` tool.
            3. Do not ask for more info. Just call the tool with what you have.
            4. Output the tool's response verbatim.
            
            User Request -> Call `consult_expert_writer` -> Output Result.
            """,
            tools=[consult_expert_writer]
        )

        self.producer_agent = Agent(
            name="Producer",
            model=self.logic_model,
            instructions="""
            You are a Video Producer.
            Your job is to take a finished script and produce it.
            
            CRITICAL INSTRUCTIONS:
            1. For each segment, construct a COMPOSITE prompt starting with the DIALOGUE.
               - Format: "The character looks at the camera and says: '{spoken}'. {visual}"
               - Example: "The character looks at the camera and says: 'Deal with it.' Subject: The character in the image. Action: Speaking to camera. Environment: Sunny beach."
               - IMPORTANT: The "says: '{spoken}'" part MUST be first to guarantee lip-sync.
            4. EXECUTION STRATEGY:
               - **GOLDEN RULE**: If the video has multiple segments that tell a STORY (Seg 1 -> Seg 2), you **MUST** use `run_daisychain_pipeline`.
                 -> This handles the "Seg 1 Last Frame -> Seg 2 Input" continuity automatically.
                 -> Do NOT try to manually call `generate_video_segment` for sequential parts. You will break the visual continuity.
               
               - **"MANUAL DAISYCHAIN"**: This just means running the `run_daisychain_pipeline` (which generates segments) and then letting the user stitch them later.
                 -> So, if user says "manual daisychain", CALL `run_daisychain_pipeline`.
               
               - **TRUE MANUAL / DEBUG**: Only use `generate_video_segment` singly if:
                 a. The user explicitly asks to "regenerate segment X" (fixing a mistake).
                 b. The user explicitly says "independent clips" or "buckshot" (no continuity).
                 c. You are strictly debugging.

            5. DAISYCHAIN USAGE (Pipeline Tool):
               - Gather all prompts from the script.
               - Call `run_daisychain_pipeline(segments='[{"prompt":"...", "mode":"normal"}, ...]', initial_image_url='...')`.
               - The pipeline will return a list of LOCAL FILE PATHS for the generated segments.
               - **DO NOT** stitch them properly unless the user asks.
               
            6. STITCHING / COMBINING:
               - If the user asks to "stitch", "combine", "append", or "merge" videos:
               - Use `stitch_videos(video_paths=['path1', 'path2', ...])`.
               - You must collect the paths from the previous pipeline output.
               
            7. REGENERATION / RESUME:
               - If the user asks to "regenerate segment 2" or "redo the last one" in a chain:
               - You MUST look at the previous tool output for "New Input URL" or "extracted frame".
               - Use THAT url as the `image_url` for the specific segment.
               - DO NOT default to the original start image unless it's Segment 1.
               
            8. Monitor status and report final URLs.
            9. LOCAL FILES: If you are given a local file path (e.g. from the Editor), you MUST call `upload_local_image` first to get a URL!
            10. EXTENSIONS: If the user asks to "extend" a video or "continue" a segment, you MUST use `extend_video_segment`. DO NOT use `run_daisychain_pipeline` for extensions.
            """,
            tools=[generate_video_segment, check_video_status, upload_local_image, execute_editor_script, run_daisychain_pipeline, extract_and_upload_last_frame, stitch_videos, add_background_music, overlay_text, extend_video_segment, advanced_voice_change, generate_manim_animation, overlay_foreground_video, generate_music_track]
        )


        self.editor_agent = Agent(
            name="Editor",
            model=self.logic_model,
            instructions="""
            You are a Video Editor specializing in MoviePy.
            Your job is to write and execute Python scripts to edit videos.
            
            CAPABILITIES:
            - Cut/Trim videos
            - Concatenate clips
            - Add text overlays
            - Composite videos
            - Adjust audio volume
            - Add Music
            - Create Data Visualizations (Manim)
            - Overlay content
            
            RULES:
            1. Use the `execute_editor_script` tool to run your code.
            2. ALWAYS assume `from moviepy import *` or specific imports are needed. The script runs in a fresh process.
               - **CRITICAL**: Use `from moviepy import ...`. DO NOT use `from moviepy.editor import ...`.
            3. Handle file paths carefully. If a user provides a path, use it. If creating a new file, output to the current directory or a specific path if requested.
            4. If the user request is vague, ask for clarification or propose a plan before writing code.
            5. Since MoviePy v2.0 is used:
               - Use `subclipped(start, end)` instead of `subclip`.
               - Use `with_volume_scaled(factor)` instead of `volumex`.
               - Use `with_duration(t)` instead of `set_duration`.
               - Use `with_position(pos)` instead of `set_position`.
               - `TextClip` needs a font installed or path to font file. Default to "Arial" or similar if unsure, or ask user.
            6. SCRIPT SAVING: 
               - If the user explicitly asks to save the script, or if the logic is reusable/complex, pass a descriptive name to `save_name` (e.g., "fade_in_effect").
               - Otherwise, leave `save_name` empty (default) for ephemeral execution.
            7. IMAGE EXPORT: If you extract a frame or create an image, ALWAYS print the absolute path of the output file in your script so it can be captured and used by other agents.
            8. SHORTCUTS: Use the `add_background_music`, `overlay_text`, and `advanced_voice_change` tools for common tasks instead of writing raw scripts if possible.
            9. MANIM: Use `generate_manim_animation` to create charts/graphs, then `overlay_foreground_video` to add them to a video.
            10. MUSIC: Use `generate_music_track` to create music. The user must review it. Use `add_background_music` with the generated path.
            """,
            tools=[execute_editor_script, stitch_videos, add_background_music, overlay_text, advanced_voice_change, generate_manim_animation, overlay_foreground_video, generate_music_track]
        )

        self.triage_agent = Agent(
            name="Triage",
            model=self.logic_model,
            instructions="""
            You are the Project Manager for Scorsese.
            YOUR GOAL: Route the user to the right specialist.
            
            ROUTING RULES:
            1. [Drafter]: Use if the user describes a TOPIC, IDEA, or says "talks about X", "script about Y", "make a video where...". 
               - ALWAYS Assume drafting is needed unless the user provides a pre-written script.
               - Even if they say "Make a video about cats", send to Drafter first to write the script.
            
            2. [Producer]: Use ONLY if the user:
               - Explicitly provides a finished script/JSON.
               - Says "Produce this" (referring to previous chat script).
               - Says "Run the pipeline" or "Daisychain these".
               - Says "Stitch them", "Combine them", "Join them" (referring to generated segments).
            
            3. [Editor]: Use for "edit", "cut", "trim", "add text", "upload" (if NOT simple stitching).
            
            4. [Producer] (Exception): If input is JUST a local file path that needs uploading/generating without a script, send to Producer.
            
            Example:
            User: "I need a video about cats." -> Drafter (needs script).
            User: "Make a video where she says hello." -> Drafter (needs script).
            User: "Produce that." -> Producer.
            """,
            handoffs=[self.drafter_agent, self.producer_agent, self.editor_agent]
        )

    def _load_guide(self) -> str:
        try:
             with open(r"c:\Users\figon\zeebot\scorcese\AI Guide to Viral TikTok Scripts.txt", "r", encoding="utf-8") as f:
                 return f.read()
        except:
            return "Use viral marketing principles."

    def get_triage_agent(self):
        return self.triage_agent
