
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
