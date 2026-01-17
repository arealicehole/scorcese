try:
    from agents import SQLiteSession, Runner
    print("Success: SQLiteSession found.")
    
    # Test initialization
    session = SQLiteSession(path="test_db.db")
    print(f"Session created: {session}")
except ImportError as e:
    print(f"Failed to import: {e}")
except Exception as e:
    print(f"Runtime Error: {e}")
