
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from scorsese.services.kie_client import KIEClient
from scorsese.services.music_service import MusicService

def test_music_service_structure():
    print("Verifying MusicService and KIEClient updates...")
    
    # Check KIEClient
    kie = KIEClient(api_key="mock")
    if hasattr(kie, "generate_music"):
        print("MATCH: KIEClient.generate_music exists.")
    else:
        print("ERROR: KIEClient.generate_music missing.")
        
    # Check MusicService
    ms = MusicService(kie_client=kie)
    if hasattr(ms, "generate_music"):
        print("MATCH: MusicService.generate_music exists.")
    else:
        print("ERROR: MusicService.generate_music missing.")

    # Check AgenticApproach linkage (simple check)
    try:
        from scorsese.approaches.agentic import AgenticApproach
        print("MATCH: AgenticApproach imported.")
    except Exception as e:
        print(f"ERROR: AgenticApproach import failed: {e}")

    print("\nVerification Complete.")

if __name__ == "__main__":
    test_music_service_structure()
