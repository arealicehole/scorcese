import os
import json
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel
from openai import OpenAI

class LLMClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL") or "https://openrouter.ai/api/v1"
        self.model = model
        
        # If accessing OpenRouter, we need to ensure the correct base URL is used
        if "openrouter" in self.base_url and not self.api_key:
             raise ValueError("API Key required for OpenRouter/OpenAI.")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers={
                "HTTP-Referer": "https://github.com/scorsese/scorsese", # Optional
                "X-Title": "Scorsese" 
            }
        )

    def generate_completion(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

    def generate_creative_completion(self, prompt: str, system_prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """
        Generates creative content potentially using a different model (e.g. via OpenRouter).
        """
        target_model = model or self.model
        try:
            params = {
                "model": target_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.8, # Default, can be overridden
            }
            params.update(kwargs)
            
            response = self.client.chat.completions.create(**params)
            return response.choices[0].message.content
        except Exception as e:
            return f"Error creating content: {e}"

    def generate_structured(self, prompt: str, response_model: Type[BaseModel], system_prompt: str = "You are a helpful assistant.") -> BaseModel:
        """
        Generates a structured response matching the Pydantic model.
        Note: OpenRouter support for 'response_format' varies by model. 
        If the model is OpenAI (native), this works reliably. 
        For others, we might need prompt engineering + JSON mode fallback.
        """
        try:
            # Try native structured output first (works for latest OpenAI models)
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format=response_model,
            )
            return completion.choices[0].message.parsed
        except Exception as e:
            # Fallback for models that support JSON mode but maybe not the 'beta.parse' helper strictly
            # or standard 'response_format={"type": "json_object"}'
            print(f"Structured parse failed, attempting JSON mode fallback: {e}")
            
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt + "\nReturn valid JSON matching the schema."},
                    {"role": "user", "content": prompt + f"\nJson Schema: {json.dumps(response_model.model_json_schema())}"},
                ],
                response_format={"type": "json_object"}
            )
            content = completion.choices[0].message.content
            return response_model.model_validate_json(content)

    def generate_speech(self, text: str, voice: str = "alloy", output_path: str = None) -> str:
        """
        Generates speech from text using OpenAI's TTS model.
        Returns the path to the saved audio file.
        """
        if not output_path:
            import uuid
            output_path = f"speech_{uuid.uuid4().hex[:6]}.mp3"
        
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )
            
            # Ensure directory exists if path has one
            directory = os.path.dirname(output_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
                
            response.stream_to_file(output_path)
            return output_path
        except Exception as e:
            raise Exception(f"Failed to generate speech: {e}")
