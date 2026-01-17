import sys
import os
import requests

sys.path.append(os.getcwd())
from scorsese.services.image_upload_service import ImageUploadService

def test_hosting():
    print("Testing Hosting & Generation...")
    
    # Load API Key safely
    api_key = os.getenv("KIE_API_KEY")
    if not api_key:
        try:
            # Try utf-16 first due to BOM error, then utf-8
            try:
                with open(r"c:\Users\figon\zeebot\scorcese\scorsese\.env", "r", encoding="utf-16") as f:
                    content = f.read()
            except:
                with open(r"c:\Users\figon\zeebot\scorcese\scorsese\.env", "r", encoding="utf-8") as f:
                    content = f.read()
            
            for line in content.splitlines():
                if line.startswith("KIE_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]
                    break
        except Exception as e:
            print(f"Failed to read .env: {e}")
            return

    if not api_key:
        print("No API Key found.")
        return

    # Use a simpler local KIE client mock to avoid complex imports if possible, 
    # but we need the real one.
    from scorsese.services.kie_client import KIEClient
    kie = KIEClient(api_key=api_key)
    uploader = ImageUploadService()

    dummy_path = "debug_test.png"
    print("Downloading test image...")
    try:
        r = requests.get("https://placehold.co/600x400/png")
        with open(dummy_path, 'wb') as f:
            f.write(r.content)
    except Exception as e:
        print(f"Download failed: {e}")
        return
        
    # TEST 1: tmpfiles.org with HTTPS
    try:
        print("\n--- Testing tmpfiles.org (HTTPS) ---")
        with open(dummy_path, 'rb') as f:
            files = {'file': f}
            response = requests.post("https://tmpfiles.org/api/v1/upload", files=files)
            if response.status_code != 200:
                print(f"Upload failed: {response.text}")
            else:
                data = response.json()
                page_url = data['data']['url'] 
                direct_url = page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                direct_url = direct_url.replace("http://", "https://") # Force HTTPS
                print(f"Direct URL: {direct_url}")
                
                print("Requesting Video Gen from KIE...")
                task_id = kie.generate_video_from_image(direct_url, prompt="A cat jumping", mode="normal")
                print(f"Task ID: {task_id}")
                
                print("Waiting for KIE...")
                status = kie.wait_for_task(task_id, poll_interval=2, timeout=60)
                print(f"Final Status: {status}")
                if status.get("state") == "success":
                    print("PASS: KIE accepts tmpfiles.org URLs (HTTPS).")
                else:
                    print("FAIL: KIE rejected or failed.")
    except Exception as e:
        print(f"CRASH (tmpfiles): {e}")

    # TEST 3: file.io with JSON header
    try:
        print("\n--- Testing file.io (JSON Header) ---")
        with open(dummy_path, 'rb') as f:
            files = {'file': f}
            headers = {"Accept": "application/json"}
            response = requests.post("https://file.io", files=files, headers=headers)
            print(f"Status: {response.status_code}")
            print(f"Resp: {response.text[:200]}")
            
            if response.status_code == 200:
                url = response.json().get("link")
                print(f"URL: {url}")
                
                print("Requesting Video Gen from KIE...")
                task_id = kie.generate_video_from_image(url, prompt="A cat jumping", mode="normal")
                print(f"Task ID: {task_id}")
                
                print("Waiting for KIE...")
                status = kie.wait_for_task(task_id, poll_interval=2, timeout=60)
                print(f"Final Status: {status}")
                if status.get("state") == "success":
                    print("PASS: KIE accepts file.io URLs.")
                else:
                    print("FAIL: KIE rejected or failed.")
    except Exception as e:
        print(f"CRASH (file.io): {e}")

    # TEST 5: Uguu.se
    try:
        print("\n--- Testing Uguu.se ---")
        with open(dummy_path, 'rb') as f:
            files = {'files[]': f}
            response = requests.post("https://uguu.se/upload.php", files=files)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                # Response is JSON: {"success": true, "files": [{"url": "..."}]}
                data = response.json()
                if data.get("success"):
                    url = data["files"][0]["url"]
                    print(f"URL: {url}")
                    
                    print("Requesting Video Gen from KIE...")
                    task_id = kie.generate_video_from_image(url, prompt="A cat jumping", mode="normal")
                    print(f"Task ID: {task_id}")
                    
                    print("Waiting for KIE...")
                    status = kie.wait_for_task(task_id, poll_interval=2, timeout=60)
                    print(f"Final Status: {status}")
                    if status.get("state") == "success":
                        print("PASS: KIE accepts Uguu.se URLs.")
                    else:
                        print("FAIL: KIE rejected or failed.")
    except Exception as e:
        print(f"CRASH (uguu.se): {e}")

    # TEST 6: Curl to file.io
    try:
        print("\n--- Testing Curl to file.io ---")
        import subprocess
        # curl -F "file=@debug_test.png" https://file.io
        cmd = ["curl", "-F", f"file=@{dummy_path}", "https://file.io"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"Curl Output: {result.stdout}")
        
        import json
        try:
            data = json.loads(result.stdout)
            if data.get("success"):
                url = data.get("link")
                print(f"URL: {url}")
                # Test KIE?
                # ...
        except:
            print("Curl didn't return JSON")
            
    except Exception as e:
        print(f"CRASH (curl): {e}")
            
    except Exception as e:
        print(f"CRASH: {e}")
    finally:
        if os.path.exists(dummy_path):
            os.remove(dummy_path)

if __name__ == "__main__":
    test_hosting()
