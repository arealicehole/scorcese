
import os
from moviepy import VideoFileClip, concatenate_videoclips

video_paths = [r"C:\Users\figon\zeebot\scorcese\test_red.mp4", r"C:\Users\figon\zeebot\scorcese\test_blue.mp4"]
clips = []

try:
    for path in video_paths:
        clips.append(VideoFileClip(path))
        
    final_clip = concatenate_videoclips(clips, method="compose")
    
    output_path = os.path.join(os.getcwd(), "test_stitched_final.mp4")
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    
    print(f"STITCH_SUCCESS: {output_path}")

except Exception as e:
    print(f"STITCH_ERROR: {e}")
finally:
    for clip in clips:
        try: clip.close()
        except: pass
