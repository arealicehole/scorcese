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

# --- Manifest Models ---
from enum import Enum
from typing import Union, Literal

class ManifestMetadata(BaseModel):
    mode: str = "normal"
    input_image: Optional[str] = None
    notes: Optional[str] = None

class ManifestSegment(BaseModel):
    index: int
    prompt: str
    status: str = "pending" # pending, generated, failed, error_postprocessing
    video_path: Optional[str] = None
    video_url: Optional[str] = None
    metadata: ManifestMetadata = Field(default_factory=ManifestMetadata)
    generated_last_frame: Optional[str] = None

class Manifest(BaseModel):
    run_id: str
    timestamp: str
    segments: List[ManifestSegment]

# --- Edit Action Models ---

class SwapAction(BaseModel):
    action: Literal["swap"]
    seg_a: int = Field(..., description="Index of first segment")
    seg_b: int = Field(..., description="Index of second segment")

class UpdatePromptAction(BaseModel):
    action: Literal["update_prompt"]
    index: int = Field(..., description="Index of segment to update")
    prompt: str = Field(..., description="New prompt text")

class DeleteAction(BaseModel):
    action: Literal["delete"]
    index: int = Field(..., description="Index of segment to delete")

class UpdateImageAction(BaseModel):
    action: Literal["update_image"]
    index: int = Field(..., description="Index of segment to update")
    image_url: str = Field(..., description="New input image URL")

class ManifestEditRequest(BaseModel):
    modifications: List[Union[SwapAction, UpdatePromptAction, DeleteAction, UpdateImageAction]]
