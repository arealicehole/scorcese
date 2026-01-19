"""
Marty Agent - The Director

Marty is the orchestrator of the Scorsese video production system.
He manages the manifest, routes work to specialists, and keeps production on track.
"""

import os
import json
from typing import Dict, Any, List, Optional

# Output directory for manifests
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


class MartyTools:
    """Consolidated workflow tools for Marty (Director) agent."""
    
    def __init__(self, session_state=None, video_service=None, pipeline_service=None):
        self.session_state = session_state
        self.video_service = video_service
        self.pipeline_service = pipeline_service
    
    # --- Tool 1: get_status ---
    def get_status(self, run_id: str = None) -> Dict[str, Any]:
        """
        Returns the current project status including manifest and session state.
        
        Args:
            run_id: Optional run ID. If None, uses current session run.
            
        Returns:
            Dict with manifest data, session info, and next recommended action.
        """
        # Determine which run to check
        target_run = run_id
        if not target_run and self.session_state:
            target_run = self.session_state.current_run_id
        
        if not target_run:
            return {
                "status": "no_project",
                "message": "No active project. Start by getting a script from Screenwriter.",
                "next_action": "draft_script"
            }
        
        # Load manifest
        manifest_path = os.path.join(OUTPUT_DIR, f"manifest_{target_run}.json")
        if not os.path.exists(manifest_path):
            return {
                "status": "not_found",
                "message": f"Manifest {target_run} not found.",
                "next_action": "create_project"
            }
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Analyze segments
        segments = manifest.get("segments", [])
        total = len(segments)
        approved = sum(1 for s in segments if s.get("status") == "approved")
        pending = sum(1 for s in segments if s.get("status") == "pending")
        generating = sum(1 for s in segments if s.get("status") == "generating")
        failed = sum(1 for s in segments if s.get("status") == "failed")
        
        # Determine next action
        if pending > 0:
            next_pending_idx = next((i+1 for i, s in enumerate(segments) if s.get("status") == "pending"), None)
            next_action = f"generate_segment_{next_pending_idx}"
        elif generating > 0:
            next_action = "wait_for_generation"
        elif approved == total and total > 0:
            next_action = "stitch_final"
        else:
            next_action = "review_segments"
        
        # Get locked script if any
        locked_script = None
        if self.session_state and self.session_state.locked_script:
            locked_script = self.session_state.locked_script
        
        return {
            "status": "active",
            "run_id": target_run,
            "manifest_path": manifest_path,
            "segments": {
                "total": total,
                "approved": approved,
                "pending": pending,
                "generating": generating,
                "failed": failed
            },
            "segment_details": segments,
            "locked_script": locked_script is not None,
            "next_action": next_action,
            "approved_segments": dict(self.session_state.approved_segments) if self.session_state else {}
        }
    
    # --- Tool 2: update_manifest ---
    def update_manifest(self, run_id: str, modifications: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Modifies the project manifest.
        
        Args:
            run_id: The run ID to modify.
            modifications: List of modification dicts, each with:
                - action: "update_prompt" | "update_image" | "swap" | "delete" | "add" | "set_status"
                - index: Segment index (1-based)
                - ... action-specific fields
                
        Returns:
            Result of the modifications.
        """
        manifest_path = os.path.join(OUTPUT_DIR, f"manifest_{run_id}.json")
        if not os.path.exists(manifest_path):
            return {"success": False, "error": f"Manifest {run_id} not found"}
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        results = []
        segments = manifest.get("segments", [])
        
        for mod in modifications:
            action = mod.get("action")
            idx = mod.get("index", 0) - 1  # Convert to 0-based
            
            if action == "update_prompt":
                if 0 <= idx < len(segments):
                    segments[idx]["prompt"] = mod.get("prompt", segments[idx].get("prompt"))
                    results.append(f"Updated prompt for segment {idx+1}")
                    
            elif action == "update_image":
                if 0 <= idx < len(segments):
                    if "metadata" not in segments[idx]:
                        segments[idx]["metadata"] = {}
                    segments[idx]["metadata"]["input_image"] = mod.get("image_url")
                    results.append(f"Updated input image for segment {idx+1}")
                    
            elif action == "swap":
                idx_a = mod.get("index_a", 0) - 1
                idx_b = mod.get("index_b", 0) - 1
                if 0 <= idx_a < len(segments) and 0 <= idx_b < len(segments):
                    segments[idx_a], segments[idx_b] = segments[idx_b], segments[idx_a]
                    # Update indices
                    segments[idx_a]["index"] = idx_a + 1
                    segments[idx_b]["index"] = idx_b + 1
                    results.append(f"Swapped segments {idx_a+1} and {idx_b+1}")
                    
            elif action == "delete":
                if 0 <= idx < len(segments):
                    deleted = segments.pop(idx)
                    # Re-index remaining
                    for i, seg in enumerate(segments):
                        seg["index"] = i + 1
                    results.append(f"Deleted segment {idx+1}")
                    
            elif action == "set_status":
                if 0 <= idx < len(segments):
                    segments[idx]["status"] = mod.get("status", "pending")
                    if mod.get("notes"):
                        if "metadata" not in segments[idx]:
                            segments[idx]["metadata"] = {}
                        segments[idx]["metadata"]["notes"] = mod.get("notes")
                    results.append(f"Set segment {idx+1} status to {mod.get('status')}")
                    
            elif action == "add":
                new_segment = {
                    "index": len(segments) + 1,
                    "prompt": mod.get("prompt", ""),
                    "status": "pending",
                    "video_path": None,
                    "video_url": None,
                    "metadata": mod.get("metadata", {})
                }
                segments.append(new_segment)
                results.append(f"Added segment {len(segments)}")
        
        # Save updated manifest
        manifest["segments"] = segments
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        return {
            "success": True,
            "run_id": run_id,
            "modifications_applied": results,
            "total_segments": len(segments)
        }
    
    # --- Tool 3: mark_approved ---
    def mark_approved(self, segment_index: int, video_path: str = None) -> Dict[str, Any]:
        """
        Marks a segment as approved and stores the path.
        
        Args:
            segment_index: 1-based segment index
            video_path: Path to the approved video file
            
        Returns:
            Confirmation and next action.
        """
        if not self.session_state:
            return {"success": False, "error": "No session state available"}
        
        run_id = self.session_state.current_run_id
        if not run_id:
            return {"success": False, "error": "No active run"}
        
        # Update session state
        self.session_state.approved_segments[segment_index] = video_path
        
        # Update manifest
        result = self.update_manifest(run_id, [{
            "action": "set_status",
            "index": segment_index,
            "status": "approved",
            "notes": f"Approved at session, path: {video_path}"
        }])
        
        if video_path:
            # Also update video_path in manifest
            manifest_path = os.path.join(OUTPUT_DIR, f"manifest_{run_id}.json")
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            if 0 <= segment_index - 1 < len(manifest["segments"]):
                manifest["segments"][segment_index - 1]["video_path"] = video_path
                with open(manifest_path, 'w') as f:
                    json.dump(manifest, f, indent=2)
        
        # Get status to determine next action
        status = self.get_status(run_id)
        
        return {
            "success": True,
            "segment": segment_index,
            "video_path": video_path,
            "project_status": status["segments"],
            "next_action": status["next_action"]
        }
    
    # --- Tool 4: create_project ---
    def create_project(self, script_json: str, initial_image_url: str = None) -> Dict[str, Any]:
        """
        Creates a new project from an approved script.
        
        Args:
            script_json: JSON string of the approved script (segments with prompts)
            initial_image_url: Optional starting image URL
            
        Returns:
            New run ID and manifest path.
        """
        import uuid
        from datetime import datetime
        
        run_id = uuid.uuid4().hex[:8]
        
        # Parse script
        try:
            script = json.loads(script_json) if isinstance(script_json, str) else script_json
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid script JSON"}
        
        # Build manifest
        segments = []
        if isinstance(script, list):
            segment_list = script
        elif isinstance(script, dict) and "segments" in script:
            segment_list = script["segments"]
        else:
            segment_list = [script]
        
        for i, seg in enumerate(segment_list):
            prompt = seg.get("prompt") or seg.get("visual") or str(seg)
            segments.append({
                "index": i + 1,
                "prompt": prompt,
                "status": "pending",
                "video_path": None,
                "video_url": None,
                "metadata": {
                    "mode": seg.get("mode", "normal"),
                    "input_image": initial_image_url if i == 0 else None
                }
            })
        
        manifest = {
            "run_id": run_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "segments": segments
        }
        
        # Save manifest
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        manifest_path = os.path.join(OUTPUT_DIR, f"manifest_{run_id}.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Update session
        if self.session_state:
            self.session_state.current_run_id = run_id
            self.session_state.locked_script = script_json
        
        return {
            "success": True,
            "run_id": run_id,
            "manifest_path": manifest_path,
            "total_segments": len(segments),
            "next_action": "generate_segment_1"
        }
    
    # --- Tool 5: reset_project ---
    def reset_project(self) -> Dict[str, Any]:
        """Resets the session for a new project."""
        if self.session_state:
            self.session_state.reset()
        return {
            "success": True,
            "message": "Session reset. Ready for a new project.",
            "next_action": "draft_script"
        }
