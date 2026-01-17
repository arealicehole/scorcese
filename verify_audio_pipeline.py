
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

print("Verifying Advanced Audio Pipeline imports...")

try:
    from scorsese.services.elevenlabs_service import ElevenLabsService
    print("MATCH: ElevenLabsService imported.")
    svc = ElevenLabsService(api_key="mock_key")
    if hasattr(svc, "change_voice"):
        print("MATCH: ElevenLabsService.change_voice exists.")
except Exception as e:
    print(f"ERROR: ElevenLabsService check failed: {e}")

try:
    from scorsese.services.kie_client import KIEClient
    client = KIEClient(api_key="mock_key")
    if hasattr(client, "isolate_audio"):
        print("MATCH: KIEClient.isolate_audio exists.")
    else:
        print("ERROR: KIEClient.isolate_audio missing.")
except Exception as e:
    print(f"ERROR: KIEClient check failed: {e}")

try:
    from scorsese.approaches.agentic import AgenticApproach
    print("MATCH: AgenticApproach imported.")
    # We can't easily check for the tool existence without instantiating, which might trigger API checks.
    # But import success confirms syntax is okay.
except Exception as e:
    print(f"ERROR: AgenticApproach check failed: {e}")

print("\nVerification Complete.")
