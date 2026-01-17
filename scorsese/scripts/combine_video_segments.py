from moviepy.editor import VideoFileClip, concatenate_videoclips

# Load the video segments
segment_1 = VideoFileClip('C:/Users/figon/zeebot/scorcese/scorsese/output/segment_1_ff0a72.mp4')
segment_2 = VideoFileClip('C:/Users/figon/zeebot/scorcese/scorsese/output/segment_2_16a1ce.mp4')

# Combine segments
final_video = concatenate_videoclips([segment_1, segment_2])

# Specify output path
output_path = 'combined_video.mp4'

# Write the final video fileinal_video.write_videofile(output_path, codec='libx264')

# Print the output path
print(f'Final video saved at: {output_path}')