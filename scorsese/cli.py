import sys
import os
import asyncio
import argparse
from scorsese.services.kie_client import KIEClient
from scorsese.approaches.agentic import AgenticApproach

# Try importing Agents SDK REPL
try:
    from agents import run_demo_loop
except ImportError:
    run_demo_loop = None

def load_dotenv():
    """Simple .env loader to avoid dependencies."""
    paths_to_check = [
        ".env",
        os.path.join(os.path.dirname(__file__), ".env"), # Check scorsese/.env
        os.path.join(os.path.dirname(__file__), "..", ".env"), # Check parent
    ]
    
    for path in paths_to_check:
        if os.path.exists(path):
            try:
                # Try UTF-8 first, then fallback
                with open(path, "r", encoding="utf-8-sig") as f:
                    lines = f.readlines()
            except UnicodeError:
                # Fallback for UTF-16 (Powershell default often)
                with open(path, "r", encoding="utf-16") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Warning: Failed to read {path}: {e}")
                continue

            print(f"Loading environment from: {path}")
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"): continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    # Clean quotes if present
                    val = val.strip().strip("'").strip('"')
                    # Don't overwrite existing
                    if not os.getenv(key.strip()): 
                        os.environ[key.strip()] = val
            break # Load the first valid one found

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Scorsese: AI Viral Video Generator")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    
    args, unknown = parser.parse_known_args()

    # Load Env
    kie_api_key = os.getenv("KIE_API_KEY")
    if not kie_api_key:
        print("Warning: KIE_API_KEY not found in environment.")
    
    # Load Models from Env
    logic_model = os.getenv("LOGIC_MODEL", "gpt-4o-mini")
    creative_model = os.getenv("CREATIVE_MODEL", "gpt-4o")
    
    print(f"Loaded Configuration:\n  Logic Model: {logic_model}\n  Creative Model: {creative_model}")

    kie = KIEClient(api_key=kie_api_key)
    agentic_system = AgenticApproach(
        kie_client=kie,
        logic_model=logic_model, 
        creative_model=creative_model 
    )

    triage_agent = agentic_system.get_triage_agent()

    # Allow CLI to default to interactive if no args or specific flag
    if args.interactive or len(sys.argv) == 1:
        print("\nStarting Scorsese Studio (Manual Mode)...")
        # Explicitly use manual loop to avoid SDK streaming bugs
        asyncio.run(manual_loop(triage_agent))
    else:
        print("Use --interactive to start the studio.")

async def manual_loop(agent):
    print("---------------------------------------------------------")
    print("Type 'exit' to quit. You can paste image URLs directly.")
    print("---------------------------------------------------------")
    
    try:
        from agents import Runner
        # Try to import session management
        try:
           # Adjust import based on installed version if needed, but assuming standard Agents SDK
           from agents import SQLiteSession
           session = SQLiteSession("scorsese_history.db")
           print(f"(Session loaded: scorsese_history.db)")
        except ImportError:
           # Fallback if specific session class not found or different path
           print("(Warning: SQLiteSession not found, using in-memory list context)")
           session = None

    except ImportError:
        print("Error: agents SDK not found.")
        return

    # If session usage requires specific pattern manually:
    # We will use a history list fallback if session is None
    history = [] 

    while True:
        try:
            user_input = input("\n🎥 **You**: ")
            if user_input.lower() in ["exit", "quit"]:
                break
            
            if not user_input.strip():
                continue

            print("... thinking ...")
            
            # Pass session if available, else relying on runner to handle context (which it might not stateless)
            # Actually, standard Runner.run is stateless unless 'thread_id' or 'session' is passed depending on version.
            # If session object isn't supported by this Runner.run signature, use context concatenation?
            # Let's assume modern SDK supports session kwarg.
            
            if session:
                result = await Runner.run(agent, user_input, session=session)
            else:
                # Poor man's context for fallback
                # Note: This is hacky for agents, better to have the session working
                result = await Runner.run(agent, user_input)
            
            print(f"\n🤖 **Scorsese**: {result.final_output}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
