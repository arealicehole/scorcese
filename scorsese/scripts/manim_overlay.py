
import os
from moviepy import VideoFileClip, CompositeVideoClip, vfx

bg_path = r"C:\Users\figon\zeebot\scorcese\scorsese\output\manual_segment_3fc40e.mp4"
fg_path = r"C:\Users\figon\zeebot\scorcese\scorsese\output\manual_segment_8ad6e5.mp4"
output_path = r"C:\Users\figon\zeebot\scorcese\scorsese\output\overlay_1a7427.mp4"

try:
    bg = VideoFileClip(bg_path)
    fg = VideoFileClip(fg_path)
    
    # Scale foreground
    fg = fg.resized(scale=1.0)
    
    # Position
    pos = "center"
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
    print(f"OVERLAY_SUCCESS: {output_path}")
    
except Exception as e:
    print(f"OVERLAY_ERROR: {e}")
