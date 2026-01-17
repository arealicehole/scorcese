import os

def load_dotenv():
    """Simple .env loader to avoid dependencies."""
    paths_to_check = [
        ".env",
        os.path.join(os.path.dirname(__file__), "scorsese", ".env"),
        os.path.join(os.getcwd(), ".env")
    ]
    
    print(f"Checking CWD: {os.getcwd()}")
    
    for path in paths_to_check:
        print(f"Checking path: {path} - Exists? {os.path.exists(path)}")
        if os.path.exists(path):
            try:
                # Try UTF-8 first
                encoding = "utf-8"
                with open(path, "r", encoding="utf-8-sig") as f:
                    lines = f.readlines()
            except UnicodeError:
                # Fallback
                encoding = "utf-16"
                with open(path, "r", encoding="utf-16") as f:
                    lines = f.readlines()
            except Exception as e:
                print(f"Error reading {path}: {e}")
                continue

            print(f"Reading from {path} ({encoding})")
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"): continue
                print(f"Found line: {line}")
            return

load_dotenv()
