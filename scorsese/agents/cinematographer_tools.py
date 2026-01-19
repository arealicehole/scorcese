"""
Cinematographer Tools - Video Generation

The Cinematographer (DP) handles all video generation through KIE.AI.
Focused tools for shooting segments and managing footage.
"""

import os
from typing import Dict, Any, Optional

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


class CinematographerTools:
    """Video generation tools for Cinematographer agent."""
    
    def __init__(self, video_service=None, image_upload_service=None):
        self.video_service = video_service
        self.image_upload_service = image_upload_service
    
    # --- Tool 1: shoot_segment ---
    def shoot_segment(self, prompt: str, mode: str = "normal", image_url: str = None) -> Dict[str, Any]:
        """
        Generates a video segment using KIE.AI (Grok).
        
        Args:
            prompt: Detailed visual description with structural prompting.
                   Format: "Subject: [who]. Action: [what]. Environment: [where]. Technical: [camera]."
            mode: "normal" or "fun"
            image_url: Optional reference image URL
            
        Returns:
            Task ID for polling status.
        """
        if not self.video_service:
            return {"success": False, "error": "Video service not available"}
        
        try:
            result = self.video_service.generate_segment(prompt, mode, image_url)
            return {
                "success": True,
                "task_id": result.get("task_id") if isinstance(result, dict) else result,
                "prompt": prompt[:100] + "..." if len(prompt) > 100 else prompt,
                "mode": mode,
                "has_reference_image": image_url is not None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # --- Tool 2: check_footage ---
    def check_footage(self, task_id: str) -> Dict[str, Any]:
        """
        Checks the status of a video generation task.
        
        Args:
            task_id: The task ID from shoot_segment.
            
        Returns:
            Status, URL if complete, and local path if downloaded.
        """
        if not self.video_service:
            return {"success": False, "error": "Video service not available"}
        
        try:
            result = self.video_service.check_status(task_id)
            if isinstance(result, str):
                # Parse string result
                return {"success": True, "raw": result}
            return {
                "success": True,
                "status": result.get("state") or result.get("status"),
                "video_url": result.get("video_url"),
                "video_path": result.get("video_path"),
                "task_id": task_id
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # --- Tool 3: extend_shot ---
    def extend_shot(self, video_path: str, prompt: str, mode: str = "normal") -> Dict[str, Any]:
        """
        Extends a video by using its last frame as input for a new segment.
        
        Args:
            video_path: Path to the existing video.
            prompt: Prompt for the continuation.
            mode: "normal" or "fun"
            
        Returns:
            Task ID for the new segment.
        """
        if not self.video_service:
            return {"success": False, "error": "Video service not available"}
        
        try:
            # Extract last frame
            from scorsese.services.moviepy_service import MoviePyService
            moviepy = MoviePyService()
            frame_path = moviepy.extract_last_frame(video_path)
            
            # Upload frame
            if self.image_upload_service:
                frame_url = self.image_upload_service.upload(frame_path)
            else:
                return {"success": False, "error": "Image upload service not available"}
            
            # Generate new segment
            result = self.video_service.generate_segment(prompt, mode, frame_url)
            
            return {
                "success": True,
                "task_id": result.get("task_id") if isinstance(result, dict) else result,
                "source_video": video_path,
                "frame_url": frame_url,
                "prompt": prompt[:100] + "..."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # --- Tool 4: get_last_frame ---
    def get_last_frame(self, video_path_or_url: str) -> Dict[str, Any]:
        """
        Extracts the last frame from a video and uploads it for continuity.
        
        Args:
            video_path_or_url: Local path or URL to video.
            
        Returns:
            URL of the uploaded frame.
        """
        import tempfile
        import requests
        
        # Download if URL
        if video_path_or_url.startswith("http"):
            temp_path = os.path.join(OUTPUT_DIR, f"temp_dl_{os.urandom(3).hex()}.mp4")
            response = requests.get(video_path_or_url)
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            video_path = temp_path
        else:
            video_path = video_path_or_url
        
        try:
            # Extract frame
            from scorsese.services.moviepy_service import MoviePyService
            moviepy = MoviePyService()
            frame_path = moviepy.extract_last_frame(video_path)
            
            # Upload
            if self.image_upload_service:
                frame_url = self.image_upload_service.upload(frame_path)
                return {
                    "success": True,
                    "frame_path": frame_path,
                    "frame_url": frame_url
                }
            else:
                return {
                    "success": True,
                    "frame_path": frame_path,
                    "frame_url": None,
                    "note": "Image upload not available, use local path"
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # --- Tool 5: upload_image ---
    def upload_image(self, file_path: str) -> Dict[str, Any]:
        """
        Uploads a local image to get a public URL.
        
        Args:
            file_path: Absolute path to the image file.
            
        Returns:
            Public URL for the image.
        """
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}
        
        if self.image_upload_service:
            try:
                url = self.image_upload_service.upload(file_path)
                return {"success": True, "url": url, "local_path": file_path}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": "Image upload service not available"}
