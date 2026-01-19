from moviepy import *

# Load the last frame image
last_frame_path = 'C:/Users/figon/zeebot/scorcese/scorsese/output/last_frame_segment_1.png'

# Create an ImageClip with the last frame
image = ImageClip(last_frame_path) 

# Set the duration and FPS of the video
output_path = 'C:/Users/figon/zeebot/scorcese/scorsese/output/second_segment_final.mp4' 

# Create a video from the image with duration 4 seconds
image = image.with_duration(4).with_fps(24)  # 4 seconds duration for the segment
image.write_videofile(output_path, codec='libx264')

# Clean up
print('Second segment saved at:', output_path)