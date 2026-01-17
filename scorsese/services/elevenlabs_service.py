import os
import requests
from io import BytesIO
from elevenlabs.client import ElevenLabs
import uuid

class ElevenLabsService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            print("[ElevenLabsService] WARNING: No API Key provided. Voice changing will fail.")
            self.client = None
        else:
            self.client = ElevenLabs(api_key=self.api_key)

    def change_voice(self, audio_file_path: str, voice_id: str = "JBFqnCBsd6RMkjVDRZzb", output_path: str = None) -> str:
        """
        Uses ElevenLabs Speech-to-Speech to change the voice of the input audio file.
        
        Args:
            audio_file_path: Path to the clean audio file.
            voice_id: Target voice ID (default: 'Nicole').
            output_path: Optional path to save the result.
            
        Returns:
            Path to the transformed audio file.
        """
        if not self.client:
            raise ValueError("ElevenLabs API Key missing.")

        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        print(f"[ElevenLabs] Converting voice for {audio_file_path} (VoiceID: {voice_id})...")

        if not output_path:
             output_path = f"voice_changed_{uuid.uuid4().hex[:6]}.mp3"
        
        # Read file
        with open(audio_file_path, "rb") as f:
            audio_data = f.read()

        try:
            # Call STS API
            # Note: The SDK returns a generator (stream)
            audio_stream = self.client.speech_to_speech.convert(
                voice_id=voice_id,
                audio=BytesIO(audio_data), 
                model_id="eleven_multilingual_sts_v2", # Best for STS
                output_format="mp3_44100_128"
            )
            
            # Consume stream and write to file
            with open(output_path, "wb") as f:
                for chunk in audio_stream:
                    if isinstance(chunk, bytes):
                        f.write(chunk)
            
            return output_path

        except Exception as e:
            raise Exception(f"ElevenLabs STS Error: {e}")
