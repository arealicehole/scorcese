import sys
import subprocess
import tempfile
import os
import uuid

class MoviePyService:
    def __init__(self):
        pass

    def run_script(self, script_code: str, save_name: str = None) -> str:
        """
        Executes the provided Python script code.
        If save_name is provided, saves the script to 'scorsese/scripts/{save_name}.py'.
        Otherwise, uses a temporary file and deletes it after execution.
        """
        if save_name:
            if not save_name.endswith(".py"):
                save_name += ".py"
            
            # Ensure safe filename
            save_name = "".join(c for c in save_name if c.isalnum() or c in ('-', '_', '.'))
            
            # Save to scorsese/scripts
            scripts_dir = os.path.join(os.getcwd(), "scorsese", "scripts")
            os.makedirs(scripts_dir, exist_ok=True)
            filepath = os.path.join(scripts_dir, save_name)
            should_cleanup = False
            
            output_header = f"[Script saved to: {filepath}]\n"
        else:
            # Temporary file
            filename = f"temp_moviepy_script_{uuid.uuid4()}.py"
            temp_dir = tempfile.gettempdir()
            filepath = os.path.join(temp_dir, filename)
            should_cleanup = True
            output_header = ""

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(script_code)

            # Execute the script
            result = subprocess.run(
                [sys.executable, filepath],
                capture_output=True,
                text=True,
                timeout=300 
            )
            
            output = f"{output_header}--- STDOUT ---\n{result.stdout}\n\n--- STDERR ---\n{result.stderr}"
            if result.returncode != 0:
                output += f"\n\nEXIT CODE: {result.returncode}"
            
            return output

        except subprocess.TimeoutExpired:
            return "Error: Script execution timed out after 300 seconds."
        except Exception as e:
            return f"Error executing script: {str(e)}"
        finally:
            # Clean up only if it was a temp file
            if should_cleanup and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
