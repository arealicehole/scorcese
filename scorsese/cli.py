import sys
import os
import asyncio
import argparse
from dataclasses import dataclass, field
from typing import Optional
from scorsese.services.kie_client import KIEClient
# New modular agents system
from scorsese.agents import ScorseseCrew
# Keep old approach for fallback if needed
# from scorsese.approaches.agentic import AgenticApproach

# Try importing Agents SDK REPL
try:
    from agents import run_demo_loop
except ImportError:
    run_demo_loop = None


@dataclass
class SessionState:
    """
    Tracks state across conversation messages within a session.
    Prevents run multiplication and enables approval workflow.
    """
    current_run_id: Optional[str] = None
    approved_segments: dict = field(default_factory=dict)  # segment_index -> video_path
    locked_script: Optional[str] = None  # JSON of the approved script
    cleaned_audio_cache: dict = field(default_factory=dict)  # video_path -> {"url": cleaned_url, "local": local_path}
    
    # Default path for session persistence (in scorsese/output/)
    _session_file: str = field(default="scorsese/output/session_state.json", repr=False)
    
    def reset(self):
        """Clears all session state."""
        self.current_run_id = None
        self.approved_segments = {}
        self.locked_script = None
        self.cleaned_audio_cache = {}
        
    def __str__(self):
        return (f"SessionState(run={self.current_run_id}, "
                f"approved={list(self.approved_segments.keys())}, "
                f"script_locked={self.locked_script is not None})")
    
    def save_to_file(self, path: str = None):
        """
        Saves session state to a JSON file for persistence across restarts.
        Enable this for deployment scenarios.
        """
        import json
        save_path = path or self._session_file
        data = {
            "current_run_id": self.current_run_id,
            "approved_segments": self.approved_segments,
            "locked_script": self.locked_script,
            "cleaned_audio_cache": self.cleaned_audio_cache
        }
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'w') as f:
            json.dump(data, f, indent=2)
        return save_path
    
    @classmethod
    def load_from_file(cls, path: str = "scorsese/output/session_state.json"):
        """
        Loads session state from a JSON file.
        Returns a new SessionState with defaults if file doesn't exist.
        """
        import json
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                state = cls(
                    current_run_id=data.get("current_run_id"),
                    approved_segments=data.get("approved_segments", {}),
                    locked_script=data.get("locked_script"),
                    cleaned_audio_cache=data.get("cleaned_audio_cache", {})
                )
                print(f"[Session] Restored from: {path}")
                return state
            except Exception as e:
                print(f"[Session] Failed to load from {path}: {e}")
        return cls()


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
    parser.add_argument("--restore", action="store_true", help="Restore previous session state if available")
    
    args, unknown = parser.parse_known_args()

    # Load Env
    kie_api_key = os.getenv("KIE_API_KEY")
    if not kie_api_key:
        print("Warning: KIE_API_KEY not found in environment.")
    
    # Load Models from Env
    logic_model = os.getenv("LOGIC_MODEL", "gpt-4o-mini")
    creative_model = os.getenv("CREATIVE_MODEL", "gpt-4o")
    
    print(f"Loaded Configuration:\n  Logic Model: {logic_model}\n  Creative Model: {creative_model}")

    # Create or restore Session State
    if args.restore:
        session_state = SessionState.load_from_file()
    else:
        session_state = SessionState()

    kie = KIEClient(api_key=kie_api_key)
    
    # Import services for the crew
    from scorsese.services.moviepy_service import MoviePyService
    from scorsese.services.image_upload_service import ImageUploadService
    from scorsese.services.music_service import MusicService
    from scorsese.services.elevenlabs_service import ElevenLabsService
    from scorsese.services.manim_service import ManimService
    from scorsese.services.video_service import VideoService
    from scorsese.services.pipeline_service import PipelineService
    from scorsese.services.llm_client import LLMClient
    
    # Initialize services
    moviepy_service = MoviePyService()
    image_upload_service = ImageUploadService()
    music_service = MusicService(kie_client=kie)
    elevenlabs_service = ElevenLabsService()
    manim_service = ManimService()
    video_service = VideoService(kie, image_upload_service, moviepy_service)
    pipeline_service = PipelineService(video_service, moviepy_service)
    
    # LLM for creative writing
    or_key = os.getenv("OPENROUTER_API_KEY")
    llm_client = LLMClient(
        model=creative_model,
        api_key=or_key,
        base_url="https://openrouter.ai/api/v1"
    ) if or_key else None
    
    # Create the Scorsese Crew
    crew = ScorseseCrew(
        kie_client=kie,
        logic_model=logic_model,
        creative_model=creative_model,
        session_state=session_state,
        video_service=video_service,
        pipeline_service=pipeline_service,
        moviepy_service=moviepy_service,
        music_service=music_service,
        elevenlabs_service=elevenlabs_service,
        manim_service=manim_service,
        image_upload_service=image_upload_service,
        llm_client=llm_client
    )
    
    # Marty is the Director (entry point)
    marty = crew.get_director()

    # Allow CLI to default to interactive if no args or specific flag
    if args.interactive or len(sys.argv) == 1:
        print("\n🎬 Starting Scorsese Studio...")
        print("   Director: Marty is ready to take your vision.")
        asyncio.run(manual_loop(marty, session_state))
    else:
        print("Use --interactive to start the studio.")

async def manual_loop(agent, session_state: SessionState):
    print("---------------------------------------------------------")
    print("Type 'exit' to quit. Type 'status' to see session state.")
    print("You can paste image URLs directly.")
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
            
            # Built-in commands
            if user_input.lower() == "status":
                print(f"\n📊 Session: {session_state}")
                if session_state.current_run_id:
                    print(f"   Active Run: {session_state.current_run_id}")
                if session_state.approved_segments:
                    print(f"   Approved Segments: {list(session_state.approved_segments.keys())}")
                if session_state.locked_script:
                    print(f"   Script: Locked")
                print("\n   Commands: status, save, reset, exit")
                continue
            
            if user_input.lower() == "save":
                path = session_state.save_to_file()
                print(f"\n💾 Session saved to: {path}")
                print("   Use --restore flag to load on next start.")
                continue
            
            if user_input.lower() == "reset":
                session_state.reset()
                print("\n🔄 Session reset. Ready for new project.")
                continue

            print("... thinking ...")
            
            # Pass session if available, else relying on runner to handle context (which it might not stateless)
            # Actually, standard Runner.run is stateless unless 'thread_id' or 'session' is passed depending on version.
            # If session object isn't supported by this Runner.run signature, use context concatenation?
            # Let's assume modern SDK supports session kwarg.
            
            # Increase max_turns to allow multi-step workflows (default is 10, which is too low)
            if session:
                result = await Runner.run(agent, user_input, session=session, max_turns=25)
            else:
                # Poor man's context for fallback
                # Note: This is hacky for agents, better to have the session working
                result = await Runner.run(agent, user_input, max_turns=25)
            
            print(f"\n🤖 **Scorsese**: {result.final_output}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
