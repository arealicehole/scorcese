"""
Editor Tools - MoviePy Expert

The Editor agent knows MoviePy deeply and can write scripts for ANY post-production task.
Instead of rigid wrapper tools, it uses one flexible execute_moviepy tool.
"""

import os
import sys
import uuid
import tempfile
import subprocess
from typing import Dict, Any, List, Optional

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


class EditorTools:
    """Flexible post-production tools for Editor agent."""
    
    def __init__(self, moviepy_service=None, music_service=None, elevenlabs_service=None, manim_service=None):
        self.moviepy_service = moviepy_service
        self.music_service = music_service
        self.elevenlabs_service = elevenlabs_service
        self.manim_service = manim_service
    
    # --- Tool 1: edit_video (MoviePy Expert) ---
    def edit_video(self, task: str, script_code: str, save_name: str = None) -> Dict[str, Any]:
        """
        Executes a MoviePy script written by the Editor agent.
        
        The Editor agent should write complete, runnable MoviePy v2 scripts.
        
        Args:
            task: Human-readable description of what the script does.
            script_code: Complete Python script using MoviePy v2 syntax.
                        MUST use: from moviepy import ... (NOT from moviepy.editor)
            save_name: Optional name to save script for reuse.
            
        Returns:
            Dict with stdout, stderr, and output file paths found.
            
        MoviePy v2 Notes (for LLM):
            - Use `subclipped(start, end)` not `subclip`
            - Use `with_volume_scaled(factor)` not `volumex`
            - Use `with_duration(t)` not `set_duration`
            - Use `with_position(pos)` not `set_position`
            - TextClip needs explicit font path or "Arial"
        """
        # Create a temp script file
        temp_script_path = os.path.join(OUTPUT_DIR, f"editor_script_{uuid.uuid4().hex[:6]}.py")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        with open(temp_script_path, 'w') as f:
            f.write(script_code)
        
        # Run the script
        try:
            result = subprocess.run(
                [sys.executable, temp_script_path],
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout
                cwd=OUTPUT_DIR
            )
            
            output = {
                "task": task,
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
            
            # Try to find output files mentioned in stdout
            import re
            paths_found = re.findall(r'[A-Za-z]:\\[^\s"\']+\.(?:mp4|avi|mov|mp3|wav|png|jpg)', result.stdout)
            paths_found += re.findall(r'/[^\s"\']+\.(?:mp4|avi|mov|mp3|wav|png|jpg)', result.stdout)
            if paths_found:
                output["output_files"] = paths_found
            
            # Save script if requested
            if save_name and result.returncode == 0:
                saved_path = os.path.join(OUTPUT_DIR, "saved_scripts", f"{save_name}.py")
                os.makedirs(os.path.dirname(saved_path), exist_ok=True)
                with open(saved_path, 'w') as f:
                    f.write(script_code)
                output["saved_to"] = saved_path
            
            # Cleanup temp script on success
            if result.returncode == 0:
                os.remove(temp_script_path)
            else:
                output["script_path"] = temp_script_path
                output["error_hint"] = "Check stderr for details. Script preserved for debugging."
            
            return output
            
        except subprocess.TimeoutExpired:
            return {
                "task": task,
                "success": False,
                "error": "Script execution timed out (5 minutes)",
                "script_path": temp_script_path
            }
        except Exception as e:
            return {
                "task": task,
                "success": False,
                "error": str(e),
                "script_path": temp_script_path
            }
    
    # --- Tool 2: render_animation (Manim) ---
    def render_animation(self, description: str, script_code: str = None) -> Dict[str, Any]:
        """
        Renders a Manim animation for data visualization.
        
        If script_code is provided, uses that directly.
        Otherwise, expects the Editor LLM to have generated the script.
        
        Args:
            description: What the animation visualizes.
            script_code: Complete Manim script with a Scene class.
            
        Returns:
            Path to the rendered video.
            
        Manim Notes (for LLM):
            - Use: from manim import *
            - Create a class extending Scene with construct() method
            - Common objects: Circle, Square, Text, MathTex, Axes, Graph
            - Animations: Create, Write, Transform, FadeIn, FadeOut
            - Positioning: .next_to(), .shift(), .to_edge()
        """
        if not script_code:
            return {"success": False, "error": "No Manim script provided"}
        
        if self.manim_service:
            # Use existing manim service if available
            try:
                result = self.manim_service.render_scene_from_code(script_code)
                return {
                    "success": True,
                    "description": description,
                    "output_path": result
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        # Fallback: run Manim directly
        temp_script_path = os.path.join(OUTPUT_DIR, f"manim_script_{uuid.uuid4().hex[:6]}.py")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        with open(temp_script_path, 'w') as f:
            f.write(script_code)
        
        # Find the Scene class name
        import re
        scene_match = re.search(r'class\s+(\w+)\s*\(\s*Scene\s*\)', script_code)
        if not scene_match:
            return {"success": False, "error": "No Scene class found in script"}
        
        scene_name = scene_match.group(1)
        
        try:
            result = subprocess.run(
                ["manim", "-ql", temp_script_path, scene_name],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=OUTPUT_DIR
            )
            
            if result.returncode == 0:
                # Find output video
                video_pattern = re.compile(rf'{scene_name}\.mp4')
                for root, dirs, files in os.walk(os.path.join(OUTPUT_DIR, "media")):
                    for f in files:
                        if video_pattern.search(f):
                            video_path = os.path.join(root, f)
                            return {
                                "success": True,
                                "description": description,
                                "output_path": video_path
                            }
                return {"success": True, "description": description, "stdout": result.stdout}
            else:
                return {"success": False, "error": result.stderr}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # --- Tool 3: generate_music (Suno) ---
    def generate_music(self, prompt: str, instrumental: bool = True) -> Dict[str, Any]:
        """
        Generates music using Suno AI.
        
        Args:
            prompt: Description of desired music (genre, mood, instruments).
            instrumental: If True, generates instrumental only.
            
        Returns:
            Path to downloaded MP3.
        """
        if not self.music_service:
            return {"success": False, "error": "Music service not available"}
        
        try:
            path = self.music_service.generate_music(prompt, instrumental)
            if path:
                return {
                    "success": True,
                    "prompt": prompt,
                    "output_path": path,
                    "instrumental": instrumental
                }
            else:
                return {"success": False, "error": "Music generation returned no path"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # --- Tool 4: change_voice (ElevenLabs) ---
    def change_voice(self, video_path: str, voice_id: str = "JBFqnCBsd6RMkjVDRZzb") -> Dict[str, Any]:
        """
        Changes the voice in a video using ElevenLabs Speech-to-Speech.
        
        Args:
            video_path: Path to the video file.
            voice_id: ElevenLabs voice ID (default: George).
            
        Returns:
            Path to the video with changed voice.
            
        Note: ElevenLabs has a ~5min duration limit depending on tier.
        """
        if not self.elevenlabs_service:
            return {"success": False, "error": "ElevenLabs service not available"}
        
        # This would integrate with the advanced_voice_change flow
        # For now, return a placeholder that the implementation will fill
        return {
            "success": False, 
            "error": "change_voice requires integration with existing advanced_voice_change flow"
        }
