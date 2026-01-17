from typing import List, Optional
from pydantic import BaseModel, Field

class VisualCue(BaseModel):
    description: str = Field(..., description="Description of valid visual elements")
    camera_movement: Optional[str] = Field(None, description="Camera movement instructions (e.g. 'Zoom in', 'Pan right')")
    text_overlay: Optional[str] = Field(None, description="Text to appear on screen")

class ScriptSegment(BaseModel):
    id: int
    role: str = Field(..., description="Role of this segment (e.g. 'Hook', 'Validation', 'Body', 'CTA')")
    duration_estimate: float = Field(..., description="Estimated duration in seconds")
    audio_text: str = Field(..., description="Spoken audio text")
    visual_cue: VisualCue
    video_url: Optional[str] = Field(None, description="URL of the generated video segment")
    task_id: Optional[str] = Field(None, description="KIE task ID for generation")

class ViralScript(BaseModel):
    topic: str
    target_audience: str
    goal: str
    hook_type: str = Field(..., description="Type of hook used (e.g. 'Negativity Bias', 'Visual Interrupt')")
    segments: List[ScriptSegment]
    
    @property
    def total_duration(self) -> float:
        return sum(s.duration_estimate for s in self.segments)
