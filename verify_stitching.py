import os
import sys
from scorsese.services.moviepy_service import MoviePyService

def test_stitching():
    print("Test: Generating dummy clips...")
    # 1. Create dummy clips using a script via the service (to ensure env works)
    service = MoviePyService()
    
    setup_script = """
import os
from moviepy import ColorClip

# Create Red Clip
clip1 = ColorClip(size=(640, 360), color=(255, 0, 0), duration=2)
clip1.write_videofile("test_red.mp4", fps=24)

# Create Blue Clip
clip2 = ColorClip(size=(640, 360), color=(0, 0, 255), duration=2)
clip2.write_videofile("test_blue.mp4", fps=24)

print(f"CREATED: {os.path.abspath('test_red.mp4')}")
print(f"CREATED: {os.path.abspath('test_blue.mp4')}")
"""
    output = service.run_script(setup_script, save_name="test_setup")
    print(output)
    
    if "CREATED" not in output:
        print("Failed to create dummy clips.")
        return

    # Extract paths
    import re
    paths = re.findall(r"CREATED: (.*)", output)
    if len(paths) < 2:
        print("Could not find paths.")
        return
        
    path1, path2 = paths[0].strip(), paths[1].strip()
    
    # 2. Run Stitching Logic (mimicking agentic.py)
    print("\nTest: Stitching clips...")
    
    final_filename = "test_stitched_final.mp4"
    # Note: agentic.py uses a list comprehension for paths, mimicking that
    local_video_paths = [path1, path2]
    paths_str_list = ", ".join([f'r"{p}"' for p in local_video_paths])
    
    stitching_script = f"""
import os
from moviepy import VideoFileClip, concatenate_videoclips

video_paths = [{paths_str_list}]
clips = []

try:
    for path in video_paths:
        clips.append(VideoFileClip(path))
        
    final_clip = concatenate_videoclips(clips, method="compose")
    
    output_path = os.path.join(os.getcwd(), "{final_filename}")
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    
    print(f"STITCH_SUCCESS: {{output_path}}")

except Exception as e:
    print(f"STITCH_ERROR: {{e}}")
finally:
    for clip in clips:
        try: clip.close()
        except: pass
"""
    stitch_log = service.run_script(stitching_script, save_name="test_stitch")
    print(stitch_log)
    
    # Cleanup
    try:
        os.remove(path1)
        os.remove(path2)
    except: pass

if __name__ == "__main__":
    test_stitching()
