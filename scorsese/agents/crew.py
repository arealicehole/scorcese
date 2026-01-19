"""
Scorsese Crew - Agent Definitions

The four agents that make up the Scorsese production crew:
- Marty (Director): Orchestrates production
- Screenwriter: Writes scripts
- Cinematographer: Shoots footage
- Editor: Post-production

The USER is "The Producer" (boss).
"""

import os
from typing import Optional

try:
    from agents import Agent, function_tool
except ImportError:
    class Agent:
        def __init__(self, **kwargs): pass
    def function_tool(f): return f

from .marty_tools import MartyTools
from .editor_tools import EditorTools
from .cinematographer_tools import CinematographerTools


# Load reference docs
def _load_doc(filename: str) -> str:
    """Load a reference doc from the project root."""
    doc_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), filename)
    if os.path.exists(doc_path):
        with open(doc_path, 'r') as f:
            return f.read()
    return ""

MOVIEPY_REFERENCE = _load_doc("movie.py.txt")
MANIM_REFERENCE = _load_doc("manim.txt")


class ScorseseCrew:
    """
    Factory class that creates the Scorsese production crew.
    """
    
    def __init__(self, 
                 kie_client=None,
                 logic_model: str = "gpt-4o-mini",
                 creative_model: str = "openai/gpt-4o",
                 session_state=None,
                 video_service=None,
                 pipeline_service=None,
                 moviepy_service=None,
                 music_service=None,
                 elevenlabs_service=None,
                 manim_service=None,
                 image_upload_service=None,
                 llm_client=None):
        
        self.logic_model = logic_model
        self.creative_model = creative_model
        self.session_state = session_state
        self.llm_client = llm_client
        
        # Initialize tool classes
        self.marty_tools = MartyTools(
            session_state=session_state,
            video_service=video_service,
            pipeline_service=pipeline_service
        )
        
        self.cinematographer_tools = CinematographerTools(
            video_service=video_service,
            image_upload_service=image_upload_service
        )
        
        self.editor_tools = EditorTools(
            moviepy_service=moviepy_service,
            music_service=music_service,
            elevenlabs_service=elevenlabs_service,
            manim_service=manim_service
        )
        
        # Build agents
        self._build_agents()
    
    def _build_agents(self):
        """Create all agents with their tools and instructions."""
        
        # --- SCREENWRITER ---
        @function_tool
        def draft_script(topic: str, audience: str, goal: str, specific_instructions: str = "") -> str:
            """
            Drafts a viral TikTok script.
            Returns JSON with segments, each having: visual, spoken, music, etc.
            """
            if self.llm_client:
                # Use creative LLM for script writing
                system_prompt = """You are a Viral Content Strategist & Video Prompt Engineer.
Write compelling TikTok scripts that will go viral.
Return a JSON array of segments, each with: visual, spoken, music, text_overlay fields.
For 'visual' descriptions, use Structural Prompting: "Subject: [who]. Action: [what]. Environment: [where]. Technical: [camera]."
Keep it punchy, engaging, and scroll-stopping."""

                user_prompt = f"""Write a TikTok script for:
Topic: {topic}
Audience: {audience}  
Goal: {goal}
{f"Special Instructions: {specific_instructions}" if specific_instructions else ""}

Return ONLY the JSON array."""
                
                try:
                    result = self.llm_client.generate_creative_completion(
                        user_prompt, 
                        system_prompt, 
                        temperature=0.7
                    )
                    # Debug print to see what Grok is actually returning
                    print(f"\n[DEBUG] Grok Raw Output:\n{result}\n[END DEBUG]")
                    return result
                except Exception as e:
                    return f"Error generating script: {e}"
            return "Error: No LLM client available for script writing"

        
        self.screenwriter = Agent(
            name="Screenwriter",
            model=self.logic_model,
            instructions="""
            You are the SCREENWRITER for Scorsese's viral video studio.
            
            YOUR JOB: Write scripts that will become legendary TikTok content.
            
            WORKFLOW:
            1. Call `draft_script` with the Producer's idea.
            2. Present the script cleanly.
            3. End with: "🎬 Script ready! Say 'approved' to start production."
            
            RULES:
            - Call the tool. Don't write scripts yourself.
            - For 'visual' descriptions, use Structural Prompting format.
            - Always suggest next step after presenting.
            """,
            tools=[draft_script]
        )
        
        # --- CINEMATOGRAPHER ---
        @function_tool
        def shoot_segment(prompt: str, mode: str = "normal", image_url: str = None) -> str:
            """Generates a video segment. Returns task ID."""
            return str(self.cinematographer_tools.shoot_segment(prompt, mode, image_url))
        
        @function_tool
        def check_footage(task_id: str) -> str:
            """Checks video generation status."""
            return str(self.cinematographer_tools.check_footage(task_id))
        
        @function_tool
        def extend_shot(video_path: str, prompt: str, mode: str = "normal") -> str:
            """Extends a video using its last frame."""
            return str(self.cinematographer_tools.extend_shot(video_path, prompt, mode))
        
        @function_tool
        def get_last_frame(video_path_or_url: str) -> str:
            """Extracts and uploads last frame for continuity."""
            return str(self.cinematographer_tools.get_last_frame(video_path_or_url))
        
        @function_tool
        def upload_image(file_path: str) -> str:
            """Uploads local image to get public URL."""
            return str(self.cinematographer_tools.upload_image(file_path))
        
        self.cinematographer = Agent(
            name="Cinematographer",
            model=self.logic_model,
            instructions="""
            You are the CINEMATOGRAPHER (DP) for Scorsese's studio.
            
            YOUR JOB: Shoot beautiful footage using KIE.AI video generation.
            
            TOOLS:
            - shoot_segment: Generate a video from a prompt
            - check_footage: Poll for completion
            - extend_shot: Continue a video using last frame
            - get_last_frame: Extract frame for continuity
            - upload_image: Get URL for local images
            
            WORKFLOW:
            1. Receive shooting instructions from Marty
            2. Generate the segment
            3. Wait for completion
            4. Report back with the video path/URL
            
            For prompts, use STRUCTURAL format:
            "Subject: [description]. Action: [movement]. Environment: [setting]. Technical: [camera angle, fps]."
            """,
            tools=[shoot_segment, check_footage, extend_shot, get_last_frame, upload_image]
        )
        
        # --- EDITOR ---
        @function_tool
        def edit_video(task: str, script_code: str, save_name: str = None) -> str:
            """
            Executes a MoviePy script for video editing.
            You must write complete Python code using MoviePy v2 syntax.
            """
            return str(self.editor_tools.edit_video(task, script_code, save_name))
        
        @function_tool
        def render_animation(description: str, script_code: str) -> str:
            """Renders a Manim animation. Write complete Manim script with Scene class."""
            return str(self.editor_tools.render_animation(description, script_code))
        
        @function_tool
        def generate_music(prompt: str, instrumental: bool = True) -> str:
            """Generates music via Suno. Returns path to MP3."""
            return str(self.editor_tools.generate_music(prompt, instrumental))
        
        @function_tool
        def change_voice(video_path: str, voice_id: str = "JBFqnCBsd6RMkjVDRZzb") -> str:
            """Changes voice in video via ElevenLabs."""
            return str(self.editor_tools.change_voice(video_path, voice_id))
        
        self.editor = Agent(
            name="Editor",
            model=self.logic_model,
            instructions=f"""
            You are the EDITOR for Scorsese's studio - a MoviePy and Manim expert.
            
            YOUR JOB: Handle ALL post-production using your expert knowledge.
            
            TOOLS:
            - edit_video: Execute MoviePy scripts YOU write
            - render_animation: Execute Manim scripts for data viz
            - generate_music: Create music via Suno
            - change_voice: Change voice via ElevenLabs
            
            CRITICAL: You write the Python scripts yourself using:
            
            **MoviePy v2 Reference:**
            - Import: `from moviepy import *`
            - Subclip: `clip.subclipped(start, end)`
            - Volume: `clip.with_volume_scaled(0.5)`
            - Duration: `clip.with_duration(10)`
            - Position: `clip.with_position('center')`
            - Stitch: `concatenate_videoclips([clip1, clip2])`
            - Composite: `CompositeVideoClip([bg, fg])`
            - Text: `TextClip(font="Arial", text="Hello", font_size=50)`
            - Audio: `AudioFileClip("music.mp3")`
            - Write: `final.write_videofile("output.mp4")`
            
            {f"Full MoviePy Reference: {MOVIEPY_REFERENCE[:3000]}" if MOVIEPY_REFERENCE else ""}
            
            **Manim Reference:**
            - Import: `from manim import *`
            - Class: `class MyScene(Scene):`
            - Shapes: Circle(), Square(), Triangle()
            - Text: Text(), MathTex()
            - Animate: self.play(Create(obj)), self.wait()
            
            WORKFLOW:
            1. Receive editing instructions from Marty
            2. Write the appropriate script
            3. Execute via edit_video or render_animation
            4. Handle errors - fix and retry if needed
            5. Report results back
            
            ERROR HANDLING:
            If a script fails, read the error, fix the code, and try again.
            Common fixes:
            - Wrong import (use `from moviepy import *`)
            - Missing font (use "Arial" or full path)
            - File not found (check paths carefully)
            """,
            tools=[edit_video, render_animation, generate_music, change_voice]
        )
        
        # --- MARTY (Director) ---
        @function_tool
        def get_status(run_id: str = None) -> str:
            """Gets current project status including manifest and next action."""
            return str(self.marty_tools.get_status(run_id))
        
        @function_tool
        def update_manifest(run_id: str, modifications_json: str) -> str:
            """
            Updates the manifest. modifications_json should be a JSON array like:
            '[{"action": "update_prompt", "index": 1, "prompt": "new prompt"}]'
            Actions: update_prompt, update_image, swap, delete, set_status, add
            """
            import json
            mods = json.loads(modifications_json)
            return str(self.marty_tools.update_manifest(run_id, mods))
        
        @function_tool
        def mark_approved(segment_index: int, video_path: str = None) -> str:
            """Marks a segment as approved."""
            return str(self.marty_tools.mark_approved(segment_index, video_path))
        
        @function_tool
        def create_project(script_json: str, initial_image_url: str = None) -> str:
            """Creates a new project from an approved script."""
            return str(self.marty_tools.create_project(script_json, initial_image_url))
        
        @function_tool
        def reset_project() -> str:
            """Resets the session for a new project."""
            return str(self.marty_tools.reset_project())
        
        self.marty = Agent(
            name="Marty",
            model=self.logic_model,
            instructions="""
            You are MARTY, the DIRECTOR of Scorsese's viral video studio.
            The USER is THE PRODUCER (your boss).
            
            YOUR JOB: Keep production on track and deliver the film.
            
            TOOLS (you manage the project):
            - get_status: Check current project state
            - update_manifest: Modify the project
            - mark_approved: Lock in a segment
            - create_project: Start a new project from script
            - reset_project: Start fresh
            
            YOUR CREW (delegate to them):
            - Screenwriter: For new scripts/rewrites
            - Cinematographer: For shooting footage
            - Editor: For post-production
            
            WORKFLOW:
            1. Producer says what they want
            2. You route to the right department:
               - "make a video about..." → Screenwriter
               - Script approved → create_project, then Cinematographer
               - "approved" (segment) → mark_approved, then next segment
               - "edit", "music", "stitch" → Editor
               - "status", "where are we" → get_status
            3. After each step, tell Producer what's next
            
            APPROVAL FLOW:
            - When Producer approves a script → create_project → shoot segment 1
            - When Producer approves a segment → mark_approved → shoot next segment  
            - When all segments done → Editor stitches → DONE
            
            PERSONALITY:
            - You're working for a legendary director (yourself!)
            - Keep momentum. Celebrate wins. Push towards completion.
            - After each step, suggest the next: "🎬 Segment 1 looks great! Say 'approved' to lock it in."
            """,
            tools=[get_status, update_manifest, mark_approved, create_project, reset_project],
            handoffs=[self.screenwriter, self.cinematographer, self.editor]
        )
    
    def get_director(self) -> Agent:
        """Returns Marty (the entry point agent)."""
        return self.marty
