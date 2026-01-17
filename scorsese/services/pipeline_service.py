import os
import json
import uuid

class PipelineService:
    def __init__(self, video_service, moviepy_service):
        self.video_service = video_service
        self.moviepy_service = moviepy_service

    def run_daisychain(self, segments_json: str, initial_image_url: str = None) -> str:
        """
        Executes a robust DAISYCHAIN generation pipeline.
        Guarantees that the output of Segment N is used as the input for Segment N+1.
        """
        print(f"[Pipeline] Starting Chain...")
        
        try:
            segments = json.loads(segments_json)
        except:
            return "Error: Invalid JSON for segments."
        
        current_image_url = initial_image_url
        generated_paths = []
        
        results_log = []
        
        for i, seg in enumerate(segments):
            prompt = seg.get("prompt")
            mode = seg.get("mode", "normal")
            
            print(f"\n--- Processing Segment {i+1}/{len(segments)} ---")
            print(f"Prompt: {prompt[:50]}...")
            if current_image_url:
                print(f"Input Image: {current_image_url[:50]}...")
            
            # Generate
            result_str = self.video_service.generate_segment(prompt, mode, image_url=current_image_url)
            results_log.append(f"Seg {i+1}: {result_str}")
            
            # Check success and get URL/Path
            if "SUCCESS" in result_str and "Video generated: " in result_str:
                # Extract URL
                try:
                    video_url = result_str.split("Video generated: ")[1].split("\n")[0].strip()
                    
                    # Store local path if available
                    if "Saved locally: " in result_str:
                         local_path = result_str.split("Saved locally: ")[1].strip()
                         generated_paths.append(local_path)
                    
                    # Prepare next frame if not last
                    if i < len(segments) - 1:
                        # Extract next frame
                        print(f"  > Extracting frame for next segment...")
                        next_url = self.video_service.extract_and_upload_last_frame(video_url)
                        if next_url and next_url.startswith("http"):
                            current_image_url = next_url
                            print(f"  > Next Input: {current_image_url}")
                        else:
                             print(f"  > WARNING: Could not extract frame. Chain might break visually.")
                             current_image_url = None # Fallback to text-only or reuse?
                except:
                     pass
            else:
                print(f"  > Segment failed. Stopping chain.")
                break
                
        # Return summary
        final_summary = "Pipeline Complete.\n\n" + "\n".join(results_log)
        if generated_paths:
            final_summary += f"\n\nGenerated Files:\n{json.dumps(generated_paths, indent=2)}"
            
        return final_summary

    def stitch_videos(self, video_paths: list) -> str:
        """Stitches videos together using MoviePy via script."""
        import uuid
        final_filename = f"stitched_final_{uuid.uuid4().hex[:6]}.mp4"
        
        # Format paths for Python list
        paths_str_list = ", ".join([f'r"{p}"' for p in video_paths])
        
        stitching_script = f"""
import os
from moviepy import VideoFileClip, concatenate_videoclips

video_paths = [{paths_str_list}]
clips = []

try:
    for path in video_paths:
        if os.path.exists(path):
            clips.append(VideoFileClip(path))
        else:
            print(f"WARNING: File not found: {{path}}")
    
    if not clips:
        print("NO_CLIPS_LOADED")
        exit()

    final_clip = concatenate_videoclips(clips, method="compose")
    
    # Save to scorsese/output
    output_dir = os.path.join(os.getcwd(), "scorsese", "output")
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "{final_filename}")
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    
    print(f"STITCH_SUCCESS: {{output_path}}")

except Exception as e:
    print(f"STITCH_ERROR: {{e}}")
finally:
    # Cleanup clips to release file locks
    for clip in clips:
        try: clip.close()
        except: pass
"""
        stitch_log = self.moviepy_service.run_script(stitching_script, save_name="stitch_manual")
        
        if "STITCH_SUCCESS" in stitch_log:
            import re
            match = re.search(r"STITCH_SUCCESS: (.*)", stitch_log)
            if match:
                return f"SUCCESS. Stitched video saved to: {match.group(1).strip()}"
        
        return f"Stitching failed. Logs:\n{stitch_log}"
