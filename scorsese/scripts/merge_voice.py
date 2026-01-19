
import os
from moviepy import VideoFileClip, AudioFileClip
video_path = r"c:\Users\figon\zeebot\scorcese\scorsese\output\stitched_final_ccdf7d.mp4"
audio_path = r"voice_changed_8a5e29.mp3"
output_path = r"C:\Users\figon\zeebot\scorcese\scorsese\output\final_voice_a4341d.mp4"

try:
    video = VideoFileClip(video_path)
    audio = AudioFileClip(audio_path)
    
    # Trim audio to video duration if needed
    if audio.duration > video.duration:
        audio = audio.subclipped(0, video.duration)
        
    final = video.with_audio(audio)
    final.write_videofile(output_path, codec="libx264", audio_codec="aac")
    print(f"MERGE_SUCCESS: {output_path}")
except Exception as e:
    print(f"MERGE_ERROR: {e}")
