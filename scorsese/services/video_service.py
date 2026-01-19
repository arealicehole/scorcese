import os
import requests
import uuid
from typing import Optional, Dict, Any

class VideoService:
    def __init__(self, kie_client, image_upload_service, moviepy_service):
        self.kie = kie_client
        self.upload_service = image_upload_service
        self.moviepy_service = moviepy_service
        self.output_dir = os.path.join(os.getcwd(), "scorsese", "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_segment(self, prompt: str, mode: str = "normal", image_url: str = None) -> str:
        """
        Core logic for generating a video segment via KIE.
        Handles checking, waiting, and downloading.
        """
        print(f"[VideoService] Generating video for: {prompt}")
        try:
            if image_url:
                # Validate URL
                if image_url.startswith("file://") or image_url.lower().startswith("c:") or image_url.startswith("/"):
                    return (f"ERROR: KIE.AI cannot access local files ({image_url}). "
                            f"Please upload the image to a public host and provide the HTTP URL.")
                
                print(f"  > Using Image Input: {image_url}")
                task_id = self.kie.generate_video_from_image(image_url, prompt=prompt, mode=mode)
            else:
                task_id = self.kie.generate_video_from_text(prompt, mode=mode)
            
            print(f"  > Task {task_id} started. Waiting for completion...")
            # Auto-wait
            result = self.kie.wait_for_task(task_id, poll_interval=5, timeout=120)
            
            if result.get("state") == "success":
                video_url = result.get("video_urls", [""])[0]
                local_path = self._download_file(video_url)
                return f"SUCCESS. Video generated: {video_url}\nSaved locally: {local_path}"
            else:
                return f"FAILURE. Status: {result.get('state')} - {result.get('failMsg')}"

        except Exception as e:
            return f"Error starting task: {str(e)}"

    def check_status(self, task_id: str) -> str:
        """Checks status and downloads if ready."""
        status = self.kie.get_task_status(task_id)
        if status['state'] == 'success':
            video_url = status.get('video_urls', [''])[0]
            local_path = self._download_file(video_url)
            return f"Success! Video URL: {video_url}\nSaved locally: {local_path}"
        elif status['state'] == 'fail':
            return f"Failed: {status.get('failMsg')}"
        else:
            return f"Status: {status['state']} (Waiting...)"

    def extend_segment(self, video_path: str, prompt: str, mode: str = "normal") -> str:
        """
        Extends a video by extracting the last frame and generating a new segment.
        """
        print(f"[VideoService] Extending {video_path}...")
        
        # 1. Extract Last Frame
        img_name = f"frame_extend_{uuid.uuid4().hex[:6]}.png"
        extraction_script = f"""
import os
from moviepy import VideoFileClip
video_path = r"{video_path}"
output_path = os.path.join(os.getcwd(), "scorsese", "{img_name}")
try:
    with VideoFileClip(video_path) as clip:
        clip.save_frame(output_path, t=clip.duration - 0.1)
    print(f"FRAME_SAVED: {{output_path}}")
except Exception as e:
    print(f"EXTRACTION_ERROR: {{e}}")
"""
        out_log = self.moviepy_service.run_script(extraction_script)
        extracted_path = os.path.join(os.getcwd(), "scorsese", img_name)
        
        if not os.path.exists(extracted_path):
            return f"Error: Frame extraction failed. Log: {out_log}"
        
        try:
            # 2. Upload
            new_image_url = self.upload_service.upload_image(extracted_path)
            print(f"  > Last frame uploaded: {new_image_url}")
            
            # Cleanup frame
            try: os.remove(extracted_path)
            except: pass
            
            # 3. Generate
            return self.generate_segment(prompt=prompt, mode=mode, image_url=new_image_url)
            
        except Exception as e:
            return f"Error extending video: {e}"

    def extract_and_upload_last_frame(self, video_source: str) -> str:
        """Download remote video OR use local path, extract frame, upload."""
        temp_vid = None
        is_temp = False
        
        # Handle local paths first
        if os.path.exists(video_source):
            print(f"  > Using local file: {video_source}")
            temp_vid = video_source
            is_temp = False
        elif video_source.startswith("http"):
            # Download remote video
            temp_vid = self._download_file(video_source, prefix="temp_bridge_")
            is_temp = True
            if not temp_vid: 
                return "Error downloading video."
        else:
            return f"Error: Invalid video source (not a URL or local path): {video_source}"
            
        # Extract (reuse extend logic parts, but returns url)
        img_name = f"frame_bridge_{uuid.uuid4().hex[:6]}.png"
        extraction_script = f"""
import os
from moviepy import VideoFileClip
video_path = r"{temp_vid}"
output_path = os.path.join(os.getcwd(), "scorsese", "{img_name}")
try:
    with VideoFileClip(video_path) as clip:
        clip.save_frame(output_path, t=clip.duration - 0.1)
    print(f"FRAME_SAVED: {{output_path}}")
except Exception as e:
    print(f"EXTRACTION_ERROR: {{e}}")
"""
        self.moviepy_service.run_script(extraction_script)
        extracted_path = os.path.join(os.getcwd(), "scorsese", img_name)
        
        # Cleanup temp video (only if we downloaded it)
        if is_temp and temp_vid:
            try: os.remove(temp_vid)
            except: pass
        
        if os.path.exists(extracted_path):
            url = self.upload_service.upload_image(extracted_path)
            try: os.remove(extracted_path)
            except: pass
            return url
        return "Error extracting frame."

    def _download_file(self, url: str, prefix: str = "manual_segment_") -> Optional[str]:
        fname = f"{prefix}{uuid.uuid4().hex[:6]}.mp4"
        local_path = os.path.join(self.output_dir, fname)
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(local_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return local_path
        except Exception as e:
            print(f"Download Error: {e}")
            return None
