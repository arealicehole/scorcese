
import os
from moviepy import VideoFileClip, concatenate_videoclips

video_paths = [r"C:\Users\figon\zeebot\scorcese\scorsese\output\segment_1_a216ec.mp4", r"C:\Users\figon\zeebot\scorcese\scorsese\output\segment_2_826221.mp4"]
clips = []

try:
    for path in video_paths:
        if os.path.exists(path):
            clips.append(VideoFileClip(path))
        else:
            print(f"WARNING: File not found: {path}")
    
    if not clips:
        print("NO_CLIPS_LOADED")
        exit()

    final_clip = concatenate_videoclips(clips, method="compose")
    
    # Save to scorsese/output
    output_dir = os.path.join(os.getcwd(), "scorsese", "output")
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "stitched_final_f0e46b.mp4")
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    
    print(f"STITCH_SUCCESS: {output_path}")

except Exception as e:
    print(f"STITCH_ERROR: {e}")
finally:
    # Cleanup clips to release file locks
    for clip in clips:
        try: clip.close()
        except: pass
