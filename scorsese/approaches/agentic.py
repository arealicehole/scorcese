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
    def __init__(self, kie_client: KIEClient, logic_model: str = "gpt-4o-mini", creative_model: str = "openai/gpt-4o", session_state=None):
        """
        logic_model: The model used by the Agents themselves (Nano/Mini).
        creative_model: The model used by the consult_expert_writer tool (OpenRouter/Sonnet/etc).
        session_state: Optional SessionState object for tracking runs and approvals.
        """
        self.kie = kie_client
        self.logic_model = logic_model
        self.creative_model = creative_model
        self.session_state = session_state  # Store session state reference
        
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
            3. LIP SYNC MANDATORY: If the character speaks, the Action MUST explicitly say: "The character is speaking to the camera. Mouth moving in sync with speech."
            4. NO NARRATION: Do NOT describe the scene as a "documentary" or "b-roll". The character MUST be present and acting.
            
            Example Visual:
            "Subject: The character in the image. Action: Speaking directly to the camera with an excited expression, leaning in. Mouth moving. Environment: A neon-lit room. Technical: Low angle, 24fps. No text."

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
            
            ⚠️ WARNING: This creates a NEW run. If a run already exists, use `process_pipeline_manifest` instead.
            
            Args:
                segments_json: A JSON string list of dicts. Example:
                               '[{"prompt": "A cat", "mode": "normal"}, {"prompt": "The cat flies", "mode": "fun"}]'
                initial_image_url: Optional starting image URL for the first segment.
            
            Returns:
                Summary of generation with final local paths.
            """
            # SAFEGUARD: Block if a run already exists
            if self.session_state and self.session_state.current_run_id:
                existing_run = self.session_state.current_run_id
                return (f"⛔ BLOCKED: A run already exists (Run ID: {existing_run}). "
                        f"Use `process_pipeline_manifest('{existing_run}', steps=1)` to continue, "
                        f"or `reset_session()` to start fresh.")
            
            result = self.pipeline_service.run_daisychain(segments_json, initial_image_url)
            
            # AUTO-SET: Extract run_id from result and lock it in session
            if self.session_state and result.startswith("RUN_ID:"):
                try:
                    # Parse "RUN_ID: abc123\n..." format
                    run_id = result.split("\n")[0].replace("RUN_ID:", "").strip()
                    self.session_state.current_run_id = run_id
                    print(f"[Session] AUTO-LOCKED Run ID: {run_id}")
                    result += f"\n\n✅ Session AUTO-LOCKED to Run ID: {run_id}"
                except Exception as e:
                    print(f"[Session] Warning: Could not auto-lock run: {e}")
            
            return result

        @function_tool
        def stitch_videos(video_paths: str) -> str:
            """
            Stitches (concatenates) multiple video files into a single video.
            
            Args:
                video_paths: A JSON string list of absolute file paths to the videos. 
                             Example: '["C:/path/to/vid1.mp4", "C:/path/to/vid2.mp4"]'
                             OR: '["C:/path/to/manifest_1234.json"]' to automatically load from a run.
            
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
        def get_pipeline_manifest(run_id_or_path: str) -> str:
            """
            Retrieves the JSON manifest for a specific run.
            Use this to check the status of segments, find file paths, or review generated prompts.
            Args:
                run_id_or_path: The 'run_id' (e.g. 'a1b2c3d4') OR the full path to 'manifest_....json'.
            """
            return self.pipeline_service.get_manifest(run_id_or_path)

        @function_tool
        def update_segment_status(run_id_or_path: str, segment_index: int, status: str, notes: str = None) -> str:
            """
            Updates the status of a segment in the manifest (e.g., 'approved', 'rejected', 'needs_regenerating').
            Args:
                run_id_or_path: Run ID or Manifest Path.
                segment_index: The index of the segment (1-based).
                status: New status string.
                notes: Optional notes (e.g. "Too shaky, need to retry").
            """
            return self.pipeline_service.update_segment_status(run_id_or_path, segment_index, status, notes)

        @function_tool
        def process_pipeline_manifest(run_id_or_path: str, steps: int = 1) -> str:
            """
            Executes or Resumes a video generation pipeline based on its Manifest.
            Use this to:
            1. Retry failed segments.
            2. Resume a stopped job.
            3. Process a manually created manifest.
            4. Approve/Continue to the next segment.
            
            Args:
                run_id_or_path: Run ID (e.g. 'a1b2c3d4') OR Path.
                steps: LIMIT of segments to process. Defaults to 1 (Step-by-Step). Set to 100 for "auto-run".
            """
            return self.pipeline_service.process_manifest(run_id_or_path, limit=steps)

        @function_tool
        def edit_pipeline_manifest(run_id: str, modifications_json: str) -> str:
            """
            Edits an existing pipeline manifest WITHOUT creating a new one.
            Use this to Swap segments, Update prompts, or Delete segments.
            
            Args:
                run_id: The 8-char Run ID (e.g. 'a1b2c3d4').
                modifications_json: JSON string of list of dicts.
                    Examples:
                    '[{"action": "swap", "seg_a": 1, "seg_b": 2}]'
                    '[{"action": "update_prompt", "index": 1, "prompt": "New text..."}]'
                    '[{"action": "delete", "index": 3}]'
            """
            import json
            try:
                mods = json.loads(modifications_json)
                return self.pipeline_service.edit_manifest(run_id, mods)
            except Exception as e:
                return f"Error parsing modifications JSON: {e}"

        # --- Session State Tools ---
        
        @function_tool
        def set_current_run(run_id: str) -> str:
            """
            Sets the active run for this session. All subsequent operations will use this run.
            Call this AFTER creating a new run with run_daisychain_pipeline.
            
            Args:
                run_id: The 8-char Run ID from a previous pipeline creation.
            """
            if self.session_state:
                self.session_state.current_run_id = run_id
                return f"Session active run set to: {run_id}"
            return "Warning: No session state available."

        @function_tool
        def approve_segment(segment_index: int, video_path: str) -> str:
            """
            Marks a segment as APPROVED. Stores its path and updates the manifest.
            Use this when the user says "approved", "looks good", "I like it", etc.
            
            Args:
                segment_index: The segment number (1-based).
                video_path: The local file path of the approved video.
            """
            if self.session_state:
                self.session_state.approved_segments[segment_index] = video_path
                
                # Also update manifest if we have a current run
                if self.session_state.current_run_id:
                    result = self.pipeline_service.update_segment_status(
                        self.session_state.current_run_id, 
                        segment_index, 
                        "approved",
                        notes=f"Approved at session, path: {video_path}"
                    )
                    return f"Segment {segment_index} approved! Path stored: {video_path}\n{result}"
                    
                return f"Segment {segment_index} approved! Path stored: {video_path}"
            return "Warning: No session state available."

        @function_tool
        def lock_script(script_json: str) -> str:
            """
            Locks the current script so retries don't regenerate it.
            Call this after the user approves a script draft (e.g., "I like it", "looks good").
            
            Args:
                script_json: The JSON string of the approved script.
            """
            if self.session_state:
                self.session_state.locked_script = script_json
                return "Script LOCKED. Use edit_script to modify. Retries will use this exact script."
            return "Warning: No session state available."

        @function_tool
        def get_locked_script() -> str:
            """
            Returns the locked script for this session.
            Use this when retrying generation to get the original approved script.
            """
            if self.session_state and self.session_state.locked_script:
                return self.session_state.locked_script
            return "No script locked. Call consult_expert_writer first, then lock_script after approval."

        @function_tool
        def resume_pipeline_run(from_segment: int = None) -> str:
            """
            Resumes the current session's run from a specific segment.
            Optionally resets a segment (and all after) to 'pending' for retry.
            
            Args:
                from_segment: Optional segment index to reset and resume from.
                              If None, just continues from where it left off.
            """
            if self.session_state and self.session_state.current_run_id:
                return self.pipeline_service.resume_run(
                    self.session_state.current_run_id, 
                    from_segment=from_segment
                )
            return "Error: No active run in session. Use set_current_run first."

        @function_tool
        def get_session_status() -> str:
            """
            Returns the current session state including active run, approved segments, and script lock status.
            Use this to check what's been done in this session.
            """
            if self.session_state:
                status = []
                status.append(f"Active Run: {self.session_state.current_run_id or 'None'}")
                status.append(f"Approved Segments: {list(self.session_state.approved_segments.keys()) or 'None'}")
                status.append(f"Script Locked: {'Yes' if self.session_state.locked_script else 'No'}")
                return "\n".join(status)
            return "No session state available."

        @function_tool
        def edit_segment_prompt(segment_index: int, new_prompt: str = None, prompt_edit: str = None) -> str:
            """
            Edits a segment's prompt without regenerating the entire script.
            Use this when the user wants to tweak a specific segment before retrying.
            
            Args:
                segment_index: The segment number (1-based) to edit.
                new_prompt: Optional. Complete replacement prompt.
                prompt_edit: Optional. Instructions for how to modify the existing prompt
                             (e.g., "make it more energetic", "remove the mention of crypto").
            """
            if not self.session_state or not self.session_state.current_run_id:
                return "Error: No active run. Use set_current_run first."
            
            run_id = self.session_state.current_run_id
            
            if new_prompt:
                # Direct replacement
                mods = [{"action": "update_prompt", "index": segment_index, "prompt": new_prompt}]
                result = self.pipeline_service.edit_manifest(run_id, mods)
                return f"Segment {segment_index} prompt replaced.\n{result}"
            elif prompt_edit:
                # Get current prompt and ask LLM to modify it
                manifest = self.pipeline_service.get_manifest(run_id)
                try:
                    data = json.loads(manifest)
                    seg = next((s for s in data["segments"] if s["index"] == segment_index), None)
                    if not seg:
                        return f"Error: Segment {segment_index} not found."
                    
                    current_prompt = seg.get("prompt", "")
                    
                    # Use creative LLM to edit
                    edit_prompt = f"""
                    Edit the following video generation prompt based on the user's instructions.
                    
                    CURRENT PROMPT:
                    {current_prompt}
                    
                    USER'S EDIT REQUEST:
                    {prompt_edit}
                    
                    Return ONLY the edited prompt, nothing else.
                    """
                    
                    edited_prompt = self.creative_llm.generate_completion(edit_prompt)
                    edited_prompt = edited_prompt.strip()
                    
                    mods = [{"action": "update_prompt", "index": segment_index, "prompt": edited_prompt}]
                    result = self.pipeline_service.edit_manifest(run_id, mods)
                    return f"Segment {segment_index} prompt edited.\nNew prompt: {edited_prompt[:100]}...\n{result}"
                    
                except Exception as e:
                    return f"Error editing prompt: {e}"
            else:
                return "Error: Provide either new_prompt or prompt_edit."

        @function_tool
        def reset_session() -> str:
            """
            Resets the session state completely.
            Use this to start fresh without restarting the CLI.
            """
            if self.session_state:
                self.session_state.reset()
                return "Session reset. Ready for a new video project."
            return "No session state available."


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
        def advanced_voice_change(video_path: str, voice_id: str = "JBFqnCBsd6RMkjVDRZzb", skip_kie: bool = False) -> str:
            """
            Advanced Audio Pipeline:
            1. Extracts audio from video.
            2. Uses KIE.AI to strip background noise/music (Isolate Voice).
            3. Uses ElevenLabs to change the voice (Speech-to-Speech) while keeping pacing.
            4. Remarries audio to video.
            
            Caching: On retry, if KIE was already done for this video, the cleaned audio is reused.
            
            Args:
                video_path: Path to video file.
                voice_id: ElevenLabs Voice ID (default: 'Nicole').
                skip_kie: Force skip KIE isolation (use cached or raw audio).
            """
            print(f"[Tool: Adv.Voice] Starting advanced pipeline for {video_path}...")
            
            import uuid
            cleaned_local = None
            
            # Check session cache for previously cleaned audio for THIS video
            cache_key = os.path.normpath(video_path)
            cached = self.session_state.cleaned_audio_cache.get(cache_key) if self.session_state else None
            
            if cached and os.path.exists(cached.get("local", "")):
                print(f"  > Using CACHED cleaned audio (KIE skip): {cached['local']}")
                cleaned_local = cached["local"]
            else:
                # Full pipeline: Extract -> Upload -> KIE -> Download
                
                # 1. Extract Audio
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
                    
                    cleaned_audio_urls = status.get("video_urls", [])
                    if not cleaned_audio_urls:
                        return "KIE Success but no audio URL found."
                    
                    cleaned_url = cleaned_audio_urls[0]
                    print(f"  > Cleaned Audio URL: {cleaned_url}")
                    
                    # 4. Download Cleaned Audio
                    cleaned_local = _download_to_temp(cleaned_url, suffix=".mp3")
                    if not cleaned_local:
                        return "Failed to download cleaned audio."
                    
                    # Cache the cleaned audio for potential retries
                    if self.session_state:
                        self.session_state.cleaned_audio_cache[cache_key] = {
                            "url": cleaned_url,
                            "local": cleaned_local
                        }
                        print(f"  > Cleaned audio CACHED for retry")
                    
                    # Cleanup extracted (raw) audio
                    try:
                        os.remove(extracted_audio_path)
                    except:
                        pass
                        
                except Exception as e:
                    return f"KIE Pipeline Error: {e}"
            
            try:
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
                
                # Cleanup voice-changed audio (but keep cached cleaned audio for potential re-retries)
                try: 
                    os.remove(final_audio_path)
                except: pass
                
                if "MERGE_SUCCESS" in merge_log:
                    # Clear cache on success (full pipeline done)
                    if self.session_state and cache_key in self.session_state.cleaned_audio_cache:
                        try:
                            cached_path = self.session_state.cleaned_audio_cache[cache_key].get("local")
                            if cached_path and os.path.exists(cached_path):
                                os.remove(cached_path)
                        except: pass
                        del self.session_state.cleaned_audio_cache[cache_key]
                    return f"SUCCESS. Video with replaced voice: {final_video_path}"
                else:
                    return f"Failed to merge final video. Log: {merge_log}"

            except Exception as e:
                return f"ElevenLabs/Merge Error: {e}. Cached cleaned audio preserved for retry."

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
            You are the SCRIPT DEPARTMENT for Martin Scorsese's viral video production studio.
            
            YOUR MISSION: Draft scripts that will become legendary content.
            
            PERSONALITY:
            - You're working for a legendary director who demands excellence
            - Be confident, creative, and efficient
            - After drafting, PUSH the user towards the next step
            
            WORKFLOW:
            1. Call `consult_expert_writer` with the user's idea.
            2. Present the script cleanly.
            3. ALWAYS end with a call to action like:
               "🎬 The script is ready, boss! Say **'approved'** and we'll start rolling cameras on Segment 1."
               OR
               "Ready when you are! Just say **'produce it'** or **'approved'** to begin production."
            
            RULES:
            1. You DO NOT write scripts yourself. Call the tool.
            2. Do not ask for more info - just call the tool with what you have.
            3. ALWAYS suggest the next step after presenting the script.
            """,
            tools=[consult_expert_writer]
        )

        self.producer_agent = Agent(
            name="Producer",
            model=self.logic_model,
            instructions="""
            You are the EXECUTIVE PRODUCER for Scorsese's viral video studio.
            
            🎬 THE VISION: You're making FILMS, not just clips. Every project follows this pipeline:
            
            PRODUCTION PIPELINE:
            1. 📝 SCRIPT → Get approved script from Drafter
            2. 🎥 SEGMENT 1 → Generate, show to director for approval
            3. 🎥 SEGMENT 2 → Generate using last frame continuity
            4. ... (repeat for all segments)
            5. 🎞️ STITCH → Combine all approved segments
            6. 🎬 FINAL CUT → Deliver the masterpiece
            
            YOUR PERSONALITY:
            - You're working for SCORSESE. Mediocrity is not an option.
            - Be PROACTIVE. After each step, suggest the next one.
            - Keep momentum. The director wants to see this FINISHED.
            - Celebrate wins: "Segment 1 is looking FIRE 🔥 Ready for Segment 2?"
            
            AFTER EVERY ACTION, suggest next step:
            - After segment generation: "Segment X complete! Say **'approved'** to lock it in, or **'retry'** to try again."
            - After approval: "Locked! Ready to roll on Segment Y? Say **'next'** or **'generate segment Y'**."
            - After final segment: "All segments done! Say **'stitch'** to create the final cut!"
            - After stitching: "🎬 THE FILM IS COMPLETE! Your masterpiece awaits."
            
            ## APPROVAL HANDLING (PRIORITY)
            
            ⚠️ CRITICAL RULE: ONE SEGMENT PER TURN ⚠️
            - After generating ANY segment, you MUST STOP and wait for user approval.
            - NEVER generate Segment 2 immediately after Segment 1 in a single turn.
            - NEVER call `run_daisychain_pipeline` if an active run already exists.
            - ALWAYS ask "Ready for Segment N?" and WAIT for user response.
            
            When user says "approved", "looks good", "I like it", "nice", etc.:
            
            1. FIRST: Call `get_session_status()` to see current state.
            2. IF no active run exists:
               - The user approved a SCRIPT draft from the Drafter.
               - Call `lock_script(script_json)` with the script from the conversation.
               - Then call `run_daisychain_pipeline(...)` to start production (generates Segment 1 ONLY).
               - Immediately call `set_current_run(run_id)` with the returned run_id.
               - ⛔ STOP HERE. Tell them: "🎬 Segment 1 is ready! Say **'approved'** to lock it in and continue to Segment 2."
               - DO NOT auto-generate Segment 2. WAIT for user.
            3. IF an active run exists:
               - The user approved a generated SEGMENT.
               - Call `approve_segment(segment_index, video_path)`.
               - Check if more segments remain:
                 - If YES: Ask "🎬 Locked! Ready to roll on Segment N? Say **'next'** or **'approved'** to generate it."
                 - ⛔ DO NOT auto-generate. WAIT for user to say "next" or "approved" again.
                 - If all done: "🎬 All segments approved! Say **'stitch'** for the final cut!"
            
            When user says "next", "continue", "generate segment N":
            - Call `process_pipeline_manifest(run_id, steps=1)` to generate the NEXT pending segment.
            - ⛔ STOP after generation. Ask for approval again.
            
            When user says "retry", "again", "try again":
            - Call `resume_pipeline_run(from_segment=N)` where N is the segment to retry.
            - Do NOT create a new run!
            
            CRITICAL INSTRUCTIONS:
            1. For each segment, construct a prompt appropriate to the content type:
               - **TALKING HEAD** (character speaks to camera): 
                 Format: "Using the attached image as reference, animate the character speaking. The character says: '{spoken}'. {visual_description}"
               - **ACTION/SCENE** (no dialogue, just motion):
                 Format: "Using the attached image as reference, animate: {action_description}. {visual_details}"
               - **PRODUCT/OBJECT** (showing something):
                 Format: "Using the attached image as reference, animate the scene: {description}"
               - Use descriptive terms that match the content (e.g., "lip-sync" only if there's dialogue).
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
               
             7. REGENERATION / RESUME:
                - If the user asks to "regenerate segment 2" or "redo the last one" in a chain:
                - You MUST look at the previous tool output for "New Input URL" or "extracted frame".
                - Use THAT url as the `image_url` for the specific segment.
                - DO NOT default to the original start image unless it's Segment 1.
                
             8. STEP-BY-STEP APPROVAL (CRITICAL):
                - The user wants to APPROVE every segment.
                - The tool `process_pipeline_manifest` defaults to `steps=1`. USE THIS DEFAULT.
                - DO NOT run the whole chain at once unless explicitly told to "auto-run everything".
                
             9. FORBIDDEN ACTIONS:
                - DO NOT use `generate_video_segment` for ANY task involving more than 1 segment.
                - DO NOT manually loop over segments using `generate_video_segment`. You WILL break continuity.
                - ALWAYS use `run_daisychain_pipeline` for NEW sequences.
                - ALWAYS use `process_pipeline_manifest` for RESUMING/RETRYING sequences.
                
             10. Monitor status and report final URLs.
             13. EDITING PLANS (SINGLE MANIFEST POLICY):
                - **CRITICAL**: Do NOT create a new pipeline (`run_daisychain_pipeline`) if checking, fixing, or modifying an existing job.
                - **ALWAYS** reuse the existing `run_id`.
                - If the user says "Swap segment 1 and 2", "Change the script", or "Use a different first frame":
                  1. Call `edit_pipeline_manifest(run_id, modifications='[...]')`.
                     (Supported actions: 'swap', 'update_prompt', 'delete', 'update_image')
                  2. THEN call `process_pipeline_manifest(run_id)` to execute.
                - **NEVER** leave a litter of "manifest_..." files. Keep it cleaner.
                
             14. URL HANDLING (CRITICAL):
                - NEVER remove query parameters (e.g. `?ex=...`) from image URLs.
                - Discord/CDN links REQUIRE these parameters to work. Treating them as "extra" breaks the link.
                - Pass the FULL URL string exactly as given by the user or tool.
                
             ## SESSION RULES (CRITICAL - PREVENTS RUN MULTIPLICATION)
             
             15. SINGLE RUN PRINCIPLE:
                - After creating a run with `run_daisychain_pipeline`, IMMEDIATELY call `set_current_run(run_id)`.
                - If a run already exists in session (check with `get_session_status`), NEVER call `run_daisychain_pipeline`.
                - Use `process_pipeline_manifest` or `resume_pipeline_run` to continue existing runs.
                
             16. APPROVAL WORKFLOW:
                - After generating a segment, WAIT for user response.
                - If user says "approved", "looks good", "I like it", "nice": Call `approve_segment(index, path)`.
                - If user says "retry", "again", "redo": Call `resume_pipeline_run(from_segment=N)` to retry.
                - NEVER create a new run for retries!
                
             17. SCRIPT LOCKING:
                - When user approves the script draft, call `lock_script(script_json)`.
                - For retries, use `get_locked_script()` instead of calling `consult_expert_writer` again.
                - Only call `consult_expert_writer` if user explicitly asks to "edit script" or "rewrite".
                
             18. LOCAL FILE HANDLING:
                - When user provides a local path (e.g., `c:\\path\\to\\video.mp4`):
                  a. First call `upload_local_image(path)` to get a public URL.
                  b. Then use that URL in subsequent operations.
                - NEVER pass raw local paths to video generation.
             """,
             tools=[generate_video_segment, check_video_status, upload_local_image, execute_editor_script, run_daisychain_pipeline, extract_and_upload_last_frame, stitch_videos, add_background_music, overlay_text, extend_video_segment, advanced_voice_change, generate_manim_animation, overlay_foreground_video, generate_music_track, get_pipeline_manifest, update_segment_status, process_pipeline_manifest, edit_pipeline_manifest, set_current_run, approve_segment, lock_script, get_locked_script, resume_pipeline_run, get_session_status, edit_segment_prompt, reset_session]
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
            You are the PROJECT COORDINATOR for Scorsese's legendary video studio.
            
            🎬 YOUR MISSION: Keep the production moving! Route requests to the right department.
            
            ROUTING RULES (in priority order):
            
            1. [Producer] - APPROVALS & PRODUCTION COMMANDS (HIGHEST PRIORITY):
               Keywords: "approved", "looks good", "I like it", "nice", "good", "perfect", "yes", "ok", "let's go", "do it"
               Keywords: "retry", "again", "redo", "try again", "one more time"
               Keywords: "next", "next segment", "segment 2", "produce", "generate", "roll", "action"
               Keywords: "stitch", "combine", "join", "final cut", "finish it", "wrap it up"
               -> Send to Producer immediately.
            
            2. [Drafter] - NEW IDEAS & SCRIPTS:
               Keywords: "make a video", "create", "I want", "talks about", "script about", "video where"
               -> User has an IDEA that needs a script. Send to Drafter.
               -> Even "Make a video about cats" needs drafting first.
            
            3. [Editor] - POST-PRODUCTION:
               Keywords: "edit", "cut", "trim", "add text", "overlay", "music", "sound"
               -> Technical editing work. Send to Editor.
            
            GOLDEN RULE: When in doubt about approval words, send to Producer.
            
            Examples:
            "approved" -> Producer
            "I like it" -> Producer  
            "next" -> Producer
            "stitch them" -> Producer
            "make a video about crypto" -> Drafter
            "edit the audio" -> Editor
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
