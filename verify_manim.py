
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from scorsese.services.manim_service import ManimService

def test_manim_render():
    print("Testing Manim Rendering...")
    service = ManimService()
    
    script = """
from manim import *

class TestScene(Scene):
    def construct(self):
        c = Circle(color=RED)
        self.add(c)
        self.wait(1)
"""
    try:
        # Use low quality for speed
        output_path = service.render_scene(script, "TestScene", quality="l")
        print(f"SUCCESS: Rendered video at {output_path}")
        
        if os.path.exists(output_path):
            print("Video file verified on disk.")
        else:
            print("ERROR: Video file reported success but not found on disk.")
            
    except Exception as e:
        print(f"FAILURE: Manim render failed. Details: {e}")
        # Check if it's a latex issue
        if "latex" in str(e).lower():
            print("NOTE: This might be due to missing LaTeX installation. Basic shapes should still work if Text is not used.")

if __name__ == "__main__":
    test_manim_render()
