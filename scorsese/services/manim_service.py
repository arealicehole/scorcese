import os
import subprocess
import uuid

class ManimService:
    def __init__(self, output_dir: str = "scorsese/output"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        # Manim generates media locally, we'll need to find where it puts it.
        # Default: media/videos/{file_name}/{quality}/{scene_name}.mp4

    def render_scene(self, script_code: str, scene_name: str, quality: str = "l") -> str:
        """
        Writes the script to a temp file and runs Manim.
        Quality options: 'l' (480p), 'm' (720p), 'h' (1080p), 'k' (4k).
        Returns the absolute path to the generated MP4 file.
        """
        # 1. Write Script to Temp File
        file_name = f"manim_script_{uuid.uuid4().hex[:6]}"
        script_path = f"{file_name}.py"
        
        # Ensure imports are present in the script if not already
        if "from manim import *" not in script_code and "import manim" not in script_code:
            script_code = "from manim import *\n" + script_code

        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_code)

        print(f"[Manim] Rendering {scene_name} (Quality: {quality})...")

        # 2. Run Manim Command
        # cmd: manim -q{quality} {script_path} {scene_name}
        cmd = ["manim", f"-q{quality}", script_path, scene_name]
        
        try:
            # Capture output to debug if needed
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"[Manim] Error Output:\n{result.stderr}")
                raise Exception(f"Manim render failed: {result.stderr}")
                
            # 3. Locate Output File
            # Manim structure: media/videos/{file_name}/{quality_folder}/{scene_name}.mp4
            quality_folder_map = {
                "l": "480p15",
                "m": "720p30",
                "h": "1080p60",
                "k": "2160p60"
            }
            res = "1080p60" # Default fallback
            if quality in quality_folder_map:
                res = quality_folder_map[quality]
            
            # Manim defaults to creating 'media' in CWD
            output_file = os.path.join("media", "videos", file_name, res, f"{scene_name}.mp4")
            
            if not os.path.exists(output_file):
                 # Try finding it recursively if path guess is wrong
                 for root, dirs, files in os.walk("media"):
                     if f"{scene_name}.mp4" in files:
                         output_file = os.path.join(root, f"{scene_name}.mp4")
                         break
            
            if not os.path.exists(output_file):
                raise FileNotFoundError(f"Could not locate generated Manim video at {output_file}")
                
            # 4. Move to scorsese/output for cleaner access
            final_path = os.path.join(self.output_dir, f"{scene_name}_{uuid.uuid4().hex[:6]}.mp4")
            import shutil
            shutil.copy(output_file, final_path)
            
            return os.path.abspath(final_path)

        finally:
            # Cleanup temp script
            if os.path.exists(script_path):
                os.remove(script_path)
