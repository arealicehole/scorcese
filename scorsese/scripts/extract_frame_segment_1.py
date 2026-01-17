from moviepy.editor import VideoFileClip

# Load the video clip
clip = VideoFileClip('6e8942a3-7eaa-4304-ace6-7e71723b05e5/generated_video.mp4')

# Extract the last frame and save it as a separate image
clip.save_frame('frame1.png')
