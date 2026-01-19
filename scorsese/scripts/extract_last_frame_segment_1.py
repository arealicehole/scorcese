from moviepy import *

# Load the first segment video to extract the last frame
video_path = 'C:/Users/figon/zeebot/scorcese/scorsese/output/manual_segment_1e47be.mp4'
video = VideoFileClip(video_path)

# Extract the last frame
last_frame = video.get_frame(video.duration)

# Save the last frame as an image
last_frame_file = 'C:/Users/figon/zeebot/scorcese/scorsese/output/last_frame_segment_1.png'

# Write the image to file
import imageio
imageio.imwrite(last_frame_file, last_frame)

# Print the path of the last frame for reference
print('Last frame saved at:', last_frame_file)

# Close the video
video.close()