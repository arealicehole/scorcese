import os
import requests
import json
import time
from typing import Optional, List, Dict, Any, Union

class KIEClient:
    BASE_URL = "https://api.kie.ai"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("KIE_API_KEY")
        if not self.api_key:
            raise ValueError("KIE_API_KEY must be provided or set in environment variables.")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = requests.post(url, headers=self.headers, data=json.dumps(payload))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Try to return the error details from the body if available
            try:
                error_data = e.response.json()
                raise Exception(f"KIE API Error: {error_data}") from e
            except:
                raise e

    def _get(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_data = e.response.json()
                raise Exception(f"KIE API Error: {error_data}") from e
            except:
                raise e

    def generate_video_from_text(self, prompt: str, aspect_ratio: str = "2:3", mode: str = "normal", callback_url: Optional[str] = None) -> str:
        """
        Generates a video from a text prompt.
        Returns the taskId.
        """
        if aspect_ratio not in ["2:3", "3:2", "1:1", "16:9", "9:16"]:
            raise ValueError(f"Invalid aspect_ratio: {aspect_ratio}")
        if mode not in ["fun", "normal", "spicy"]:
            raise ValueError(f"Invalid mode: {mode}")

        payload = {
            "model": "grok-imagine/text-to-video",
            "input": {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "mode": mode
            }
        }
        if callback_url:
            payload["callBackUrl"] = callback_url

        response = self._post("/api/v1/jobs/createTask", payload)
        if response.get("code") != 200:
            raise Exception(f"Failed to create task: {response.get('msg')}")
        
        return response["data"]["taskId"]

    def generate_video_from_image(self, image_url: str, prompt: Optional[str] = None, mode: str = "normal", callback_url: Optional[str] = None) -> str:
        """
        Generates a video from an image URL.
        Returns the taskId.
        """
        if mode not in ["fun", "normal"]: # "spicy" is not supported for external images per docs
            raise ValueError(f"Invalid mode for external image: {mode}. 'spicy' is not supported.")

        input_data = {
            "image_urls": [image_url],
            "mode": mode
        }
        if prompt:
            input_data["prompt"] = prompt

        payload = {
            "model": "grok-imagine/image-to-video",
            "input": input_data
        }
        if callback_url:
            payload["callBackUrl"] = callback_url

        response = self._post("/api/v1/jobs/createTask", payload)
        if response.get("code") != 200:
            raise Exception(f"Failed to create task: {response.get('msg')}")
        
        return response["data"]["taskId"]

    def generate_video_from_task_id(self, source_task_id: str, index: int = 0, prompt: Optional[str] = None, mode: str = "normal", callback_url: Optional[str] = None) -> str:
        """
        Generates a video from a previously generated Grok image (by task_id).
        Returns the taskId.
        """
        if mode not in ["fun", "normal", "spicy"]:
            raise ValueError(f"Invalid mode: {mode}")

        input_data = {
            "task_id": source_task_id,
            "index": index,
            "mode": mode
        }
        if prompt:
            input_data["prompt"] = prompt

        payload = {
            "model": "grok-imagine/image-to-video",
            "input": input_data
        }
        if callback_url:
            payload["callBackUrl"] = callback_url

        response = self._post("/api/v1/jobs/createTask", payload)
        if response.get("code") != 200:
            raise Exception(f"Failed to create task: {response.get('msg')}")
        
        return response["data"]["taskId"]

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Queries the status of a task.
        Returns a dictionary with status, result_urls (if success), and other metadata.
        """
        response = self._get("/api/v1/jobs/recordInfo", {"taskId": task_id})
        
        if response.get("code") != 200:
            return {"state": "error", "msg": response.get("msg")}

        data = response.get("data", {})
        state = data.get("state") # waiting, queuing, generating, success, fail
        
        result_info = {
            "state": state,
            "taskId": data.get("taskId"),
            "model": data.get("model"),
            "failMsg": data.get("failMsg")
        }

        if state == "success":
            result_json_str = data.get("resultJson")
            if result_json_str:
                import json
                try:
                    res_json = json.loads(result_json_str)
                    result_info["video_urls"] = res_json.get("resultUrls", [])
                    # Suno/Music models often return 'data' list with objects containing 'audio_url'
                    # or 'audio_urls' list directly.
                    # Let's save the whole parsed 'result' for the caller to inspect.
                    result_info["result"] = res_json
                    
                    # Try to normalize audio urls
                    if "audio_urls" in res_json:
                        result_info["audio_urls"] = res_json["audio_urls"]
                    elif "data" in res_json and isinstance(res_json["data"], list):
                        # Extract audio_url from each item in data list
                        result_info["audio_urls"] = [item.get("audio_url") for item in res_json["data"] if item.get("audio_url")]
                    else:
                        result_info["audio_urls"] = []

                except:
                    result_info["video_urls"] = []
                    result_info["audio_urls"] = []
        
        return result_info

    def wait_for_task(self, task_id: str, poll_interval: int = 5, timeout: int = 120) -> Dict[str, Any]:
        """
        Helper to synchronously wait for a task to complete.
        """
        start_time = time.time()
        while True:
            status = self.get_task_status(task_id)
            state = status.get("state")
            
            if state in ["success", "fail"]:
                return status
            
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Task {task_id} timed out after {timeout} seconds")
            
            time.sleep(poll_interval)

    def isolate_audio(self, audio_url: str, callback_url: Optional[str] = None) -> str:
        """
        Creates a task to isolate/clean audio using the 'elevenlabs/audio-isolation' model.
        Returns the taskId.
        """
        payload = {
            "model": "elevenlabs/audio-isolation",
            "input": {
                "audio_url": audio_url
            }
        }
        if callback_url:
            payload["callBackUrl"] = callback_url
            
        response = self._post("/api/v1/jobs/createTask", payload)
        if response.get("code") != 200:
             raise Exception(f"Failed to create isolation task: {response.get('msg')}")
             
        return response["data"]["taskId"]

    # --- Suno Music-Specific Status Methods ---
    # Suno uses a DIFFERENT endpoint and status format than standard KIE tasks!
    
    def get_music_status(self, task_id: str) -> Dict[str, Any]:
        """
        Queries the status of a SUNO MUSIC task.
        Uses /api/v1/generate/record-info (NOT /api/v1/jobs/recordInfo).
        Suno uses UPPERCASE status: PENDING, TEXT_SUCCESS, FIRST_SUCCESS, SUCCESS, GENERATE_AUDIO_FAILED, etc.
        """
        response = self._get("/api/v1/generate/record-info", {"taskId": task_id})
        
        if response.get("code") != 200:
            return {"status": "ERROR", "msg": response.get("msg")}

        data = response.get("data", {})
        status = data.get("status", "PENDING")  # UPPERCASE: PENDING, SUCCESS, etc.
        
        print(f"[KIEClient] Suno task {task_id} status: {status}")
        
        result_info = {
            "task_id": task_id,
            "status": status,
            "error_code": data.get("errorCode"),
            "error_message": data.get("errorMessage"),
            "audio_urls": []
        }

        # Check for success states
        if status in ["SUCCESS", "FIRST_SUCCESS"]:
            # Audio URLs are nested under response.sunoData[].audioUrl (camelCase!)
            suno_response = data.get("response", {})
            suno_data_list = suno_response.get("sunoData", [])
            
            for item in suno_data_list:
                if item.get("audioUrl"):
                    result_info["audio_urls"].append(item["audioUrl"])
            
            # Also store full response for debugging
            result_info["suno_data"] = suno_data_list
            
        return result_info

    def wait_for_music(self, task_id: str, poll_interval: int = 5, timeout: int = 300) -> Dict[str, Any]:
        """
        Waits for a SUNO MUSIC task to complete.
        Uses the Suno-specific status endpoint.
        """
        start_time = time.time()
        while True:
            status = self.get_music_status(task_id)
            current_status = status.get("status", "PENDING")
            
            # Success states
            if current_status in ["SUCCESS", "FIRST_SUCCESS"]:
                status["state"] = "success"  # Normalize for callers expecting lowercase
                return status
            
            # Failure states
            if current_status in ["CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED", 
                                   "CALLBACK_EXCEPTION", "SENSITIVE_WORD_ERROR", "ERROR"]:
                status["state"] = "fail"
                status["failMsg"] = status.get("error_message") or current_status
                return status
            
            # Timeout
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Suno task {task_id} timed out after {timeout} seconds (status: {current_status})")
            
            time.sleep(poll_interval)

    def generate_music(self, prompt: str, instrumental: bool = True, model: str = "V5") -> str:
        """
        Creates a music generation task using Suno via KIE.
        To ensure instrumental, we use customMode=True and map prompt -> style.
        Returns taskId.
        """
        if instrumental:

            # Custom Mode for Instrumental: style=prompt, prompt(lyrics)=""
            payload = {
                "model": model,
                "customMode": True,
                "instrumental": True,
                "style": prompt[:1000],  # V5 Limit: 1000 chars
                "title": "Scorese Generated Track",
                # callBackUrl is REQUIRED by Suno API - use placeholder (we poll for results anyway)
                "callBackUrl": "https://httpbin.org/post"
            }
        else:
            # Non-Custom Mode for Songs: prompt handles general vibe + auto lyrics
            payload = {
                "model": model,
                "customMode": False,
                "instrumental": False,
                "prompt": prompt[:500],  # Non-custom limit
                # callBackUrl is REQUIRED by Suno API - use placeholder (we poll for results anyway)
                "callBackUrl": "https://httpbin.org/post"
            }

        # Endpoint is /api/v1/generate for Music (not standard createTask?)
        # Double check doc: "post /api/v1/generate"
        response = self._post("/api/v1/generate", payload)
        
        if response.get("code") != 200:
            raise Exception(f"Failed to create music task: {response.get('msg')}")
            
        return response["data"]["taskId"]

    def add_instrumental(self, upload_url: str, tags: str, title: str, negative_tags: str = "", model: str = "V4_5PLUS", **kwargs) -> str:
        """
        Add instrumental accompaniment to an uploaded audio file.
        Returns taskId.
        """
        payload = {
            "model": model,
            "uploadUrl": upload_url,
            "tags": tags[:1000],
            "title": title[:100],
            "negativeTags": negative_tags[:1000],
            "callBackUrl": "https://httpbin.org/post"
        }
        # Add any optional parameters like vocalGender, styleWeight, etc.
        payload.update(kwargs)

        response = self._post("/api/v1/generate/add-instrumental", payload)
        if response.get("code") == 200:
            return response["data"]["taskId"]
        else:
            raise Exception(f"Failed to create add-instrumental task: {response.get('msg')}")
