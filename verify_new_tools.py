
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

print("Verifying imports...")

try:
    from scorsese.services.llm_client import LLMClient
    print("MATCH: LLMClient imported successfully.")
    
    # Check for new method
    client = LLMClient(api_key="sk-dummy")
    if hasattr(client, "generate_speech"):
        print("MATCH: LLMClient.generate_speech exists.")
    else:
        print("ERROR: LLMClient.generate_speech missing.")

except Exception as e:
    print(f"ERROR: LLMClient check failed: {e}")

try:
    from scorsese.services.music_service import MusicService
    print("MATCH: MusicService imported successfully.")
    ms = MusicService()
    if hasattr(ms, "generate_music"):
         print("MATCH: MusicService.generate_music exists.")
except Exception as e:
     print(f"ERROR: MusicService check failed: {e}")

try:
    from scorsese.approaches.agentic import AgenticApproach
    print("MATCH: AgenticApproach imported successfully.")
except Exception as e:
    print(f"ERROR: AgenticApproach check failed: {e}")

print("\nVerification Complete.")
