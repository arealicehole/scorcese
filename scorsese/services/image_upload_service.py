import requests
import os

class ImageUploadService:
    def __init__(self):
        # Uguu.se (Primary), file.io (Fallback)
        self.upload_url = "https://uguu.se/upload.php"

    def upload_image(self, file_path: str) -> str:
        """
        Uploads a local file to Uguu.se and returns the public URL.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Try Uguu.se
        try:
            with open(file_path, 'rb') as f:
                # Uguu requires 'files[]' key
                files = {'files[]': f}
                response = requests.post(self.upload_url, files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        return data["files"][0]["url"]
                    else:
                        raise Exception(f"Uguu error: {data}")
                else:
                    raise Exception(f"Uguu status: {response.status_code}")
                    
        except Exception as e:
            print(f"[ImageUploadService] Uguu failed ({e}). Trying file.io...")
            # Fallback to file.io (using curl if possible or simplistic requests?)
            # We'll stick to requests for potential cross-platform support, 
            # even though it failed in debug, it's better than nothing.
            try:
                with open(file_path, 'rb') as f:
                     # file.io might work if we interpret response as text/html for link?
                     # No, let's just stick to the basic attempt.
                     response = requests.post('https://file.io', files={'file': f})
                     if response.status_code == 200:
                         # Try parsing JSON, otherwise fallback to text?
                         try:
                             return response.json().get('link')
                         except:
                             pass
            except:
                pass
            
            raise Exception(f"All upload providers failed. Primary error: {e}")
