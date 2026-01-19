
import os
from moviepy import VideoFileClip, TextClip, CompositeVideoClip

video_path = r"C:\Users\figon\zeebot\scorcese\scorsese\output\stitched_final_6b2958.mp4"
output_path = r"C:\Users\figon\zeebot\scorcese\scorsese\output\text_overlay_49f9a5.mp4"
text_content = "Crypto Party Hacks!"
pos = "top"
col = "green"
fs = 50

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
    
    print(f"OVERLAY_SUCCESS: {output_path}")

except Exception as e:
    print(f"OVERLAY_ERROR: {e}")
