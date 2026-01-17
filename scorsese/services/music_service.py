import os
import time
import requests
from typing import Optional

class MusicService:
    def __init__(self, kie_client=None):
        self.kie = kie_client

    def generate_music(self, prompt: str, instrumental: bool = True) -> str:
        """
        Generates music via KIE (Suno).
        Waits for completion and downloads the result (first clip).
        Returns path to the downloaded MP3.
        """
        if not self.kie:
            print("[MusicService] No KIE Client provided. Cannot generate music.")
            return None

        print(f"[MusicService] Requesting Suno generation: '{prompt}' (Instrumental: {instrumental})")
        
        try:
            task_id = self.kie.generate_music(prompt, instrumental)
            print(f"  > Task ID: {task_id}. Waiting for completion...")
            
            # Wait for task
            status = self.kie.wait_for_task(task_id, timeout=300)
            
            if status.get("state") != "success":
                raise Exception(f"Music generation failed: {status.get('failMsg')}")
            
            # KIE audio usually returns 'audio_urls' or 'video_urls' in result?
            # Suno usually returns 2 clips.
            # Let's inspect 'video_urls' (standard field) or 'audio_urls' if distinct.
            # KIE generally puts results in 'video_urls' or 'resultUrls'.
            # We'll retrieve the first valid URL.
            
            # KIE audio usually returns 'audio_urls'.
            # We'll retrieve the first valid URL.
            
            urls = status.get("audio_urls", []) or status.get("video_urls", []) or status.get("resultUrls", [])
            
            if not urls:
                # Some APIs nest it differently.
                # Assuming standard KIE response for now.
                print(f"  > DEBUG: Result JSON: {status}")
                if "result" in status:
                     print(f"  > DEBUG: Inner Result: {status['result']}")
                raise Exception("No audio URLs found in response.")
                
            music_url = urls[0]
            print(f"  > Music URL: {music_url}")
            
            # Download
            import uuid
            filename = f"suno_music_{uuid.uuid4().hex[:6]}.mp3"
            output_dir = os.path.join(os.getcwd(), "scorsese", "output")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, filename)
            
            response = requests.get(music_url)
            if response.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                return output_path
            else:
                raise Exception(f"Failed to download music: {response.status_code}")
                
        except Exception as e:
            print(f"[MusicService] Error: {e}")
            return None

    def get_local_music(self, path: str) -> str:
        """
        Validates and returns a local music file path.
        """
        if os.path.exists(path):
            return path
        raise FileNotFoundError(f"Music file not found: {path}")
