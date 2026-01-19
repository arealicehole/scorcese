import os
import json
import uuid

class PipelineService:
    def __init__(self, video_service, moviepy_service):
        self.video_service = video_service
        self.moviepy_service = moviepy_service

    def run_daisychain(self, segments_json: str, initial_image_url: str = None) -> str:
        """
        Initializes a new Daisychain Run.
        Creates a Manifest and starts processing (Segment 1 only).
        """
        import json
        import time
        
        try:
            segments_list = json.loads(segments_json)
        except:
            return "Error: segments_json must be a valid JSON string."
            
        if not isinstance(segments_list, list):
            return "Error: segments_json must be a list of dicts."
            
        # Create Run ID
        run_id = uuid.uuid4().hex[:8]
        
        # Build Manifest Data
        manifest_data = {
            "run_id": run_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "segments": []
        }
        
        for i, input_seg in enumerate(segments_list):
            seg_data = {
                "index": i + 1,
                "prompt": input_seg.get("prompt"),
                "status": "pending",
                "video_path": None,
                "video_url": None,
                "metadata": {
                    "mode": input_seg.get("mode", "normal")
                }
            }
            # Inject initial image into first segment
            if i == 0 and initial_image_url:
                seg_data["metadata"]["input_image"] = initial_image_url
                
            manifest_data["segments"].append(seg_data)
            
        # Save Manifest
        manifest_path = os.path.join(os.getcwd(), "scorsese", "output", f"manifest_{run_id}.json")
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        
        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f, indent=2)
            
        print(f"[Pipeline] Created Run {run_id}. Starting Segment 1...")
        
        # Trigger Processing (Limit 1 to allow user approval)
        process_result = self.process_manifest(run_id, limit=1)
        # Prepend run_id for reliable extraction
        return f"RUN_ID: {run_id}\n{process_result}"

    def resume_run(self, run_id_or_path: str, from_segment: int = None) -> str:
        """
        Resumes a paused run from a specific segment.
        If from_segment is provided, resets that segment (and all after) to 'pending'.
        
        Args:
            run_id_or_path: Run ID or path to manifest.
            from_segment: Optional segment index to reset and resume from.
        """
        # 1. Load Manifest
        manifest_content = self.get_manifest(run_id_or_path)
        if manifest_content.startswith("Error"):
            return manifest_content
            
        try:
            manifest_data = json.loads(manifest_content)
        except:
            return "Error: Invalid JSON in manifest."
        
        run_id = manifest_data['run_id']
        manifest_path = os.path.join(os.getcwd(), "scorsese", "output", f"manifest_{run_id}.json")
        
        # 2. Reset segments if from_segment is specified
        if from_segment:
            segments = manifest_data.get("segments", [])
            reset_count = 0
            for seg in segments:
                if seg["index"] >= from_segment:
                    old_status = seg["status"]
                    seg["status"] = "pending"
                    # Clear generated data for these segments
                    seg["video_path"] = None
                    seg["video_url"] = None
                    seg["generated_last_frame"] = None
                    # Clear input_image ONLY for segments > 1 (segment 1 needs its original)
                    # This prevents stale frames from rejected attempts being reused
                    if seg["index"] > 1 and "input_image" in seg.get("metadata", {}):
                        del seg["metadata"]["input_image"]
                        print(f"  > Cleared stale input_image from Segment {seg['index']}")
                    reset_count += 1
                    print(f"  > Reset Segment {seg['index']}: {old_status} -> pending")
            
            # Save updated manifest
            with open(manifest_path, 'w') as f:
                json.dump(manifest_data, f, indent=2)
            
            print(f"[Pipeline] Reset {reset_count} segment(s) starting from Segment {from_segment}.")
        
        # 3. Resume processing
        print(f"[Pipeline] Resuming Run {run_id}...")
        return self.process_manifest(run_id, limit=1)


    def process_manifest(self, run_id_or_path: str, limit: int = None) -> str:
        """
        Executes or Resumes a pipeline based on a Manifest.
        Iterates through segments. If status != 'generated', tries to generate it.
        Maintains continuity by looking at the PREVIOUS segment's 'generated_last_frame'.
        
        Args:
            run_id_or_path: Run ID or path to manifest.
            limit: Optional integer. If set, stops after processing 'limit' NEW segments.
        """
        import json
        import time
        
        # 1. Load Manifest
        manifest_content = self.get_manifest(run_id_or_path)
        if manifest_content.startswith("Error"):
            return manifest_content
            
        try:
            manifest_data = json.loads(manifest_content)
        except:
            return "Error: Invalid JSON in manifest."
            
        manifest_path = os.path.join(os.getcwd(), "scorsese", "output", f"manifest_{manifest_data['run_id']}.json")
        segments = manifest_data.get("segments", [])
        
        print(f"[Pipeline] Processing Manifest: {manifest_data['run_id']} ({len(segments)} segments)")
        if limit:
            print(f"  > Step Limit: {limit} segment(s)")
        
        results_log = []
        processed_count = 0
        
        for i, seg in enumerate(segments):
            # Check Limit
            if limit and processed_count >= limit:
                msg = f"  > Paused: Reached step limit of {limit}."
                print(msg)
                results_log.append(msg)
                break
            # Context
            index = seg.get("index")
            status = seg.get("status")
            prompt = seg.get("prompt")
            mode = seg.get("metadata", {}).get("mode", "normal")
            
            # Determine Input Image
            # If Seg 1, use metadata input. If Seg > 1, use Prev Seg's 'generated_last_frame'
            current_image_url = None
            if i == 0:
                current_image_url = seg.get("metadata", {}).get("input_image")
            else:
                prev_seg = segments[i-1]
                # CRITICAL: We need the *output* frame of the previous segment
                current_image_url = prev_seg.get("generated_last_frame")
                
                # Store input_image in this segment's metadata for visibility/debugging
                if current_image_url:
                    seg.setdefault("metadata", {})["input_image"] = current_image_url
                
                # Verify continuity
                if not current_image_url and prev_seg.get("status") == "generated":
                    # Middle of chain generated but frame missing? Try to recover?
                    # For now, just warn, but usually this means we can't continue visually.
                    print(f"  > WARNING: Segment {index} missing input from Seg {index-1}. Continuity broken.")
            
            # DECISION: Do we generate?
            if status in ["generated", "approved"]:
                print(f"  > Seg {index}: Status '{status}'. Skipping.")
                continue
            
            if i > 0 and not current_image_url:
                 msg = f"  > Seg {index}: Cannot generate. Missing input image from Seg {i}."
                 print(msg)
                 results_log.append(msg)
                 break # STOP. cannot proceed.
                 
            print(f"\n--- Generating Segment {index} ---")
            print(f"Prompt: {prompt[:50]}...")
            if current_image_url:
                print(f"Input Image: {current_image_url[:50]}...")
                
             # EXECUTE GENERATION
            result_str = self.video_service.generate_segment(prompt, mode, image_url=current_image_url)
            results_log.append(f"Seg {index}: {result_str}")
            
            if "SUCCESS" in result_str and "Video generated: " in result_str:
                seg["status"] = "generated"
                processed_count += 1
                
                # Extract URL/Path similar to run_daisychain...
                try:
                    video_url = result_str.split("Video generated: ")[1].split("\n")[0].strip()
                    seg["video_url"] = video_url
                    if "Saved locally: " in result_str:
                         seg["video_path"] = result_str.split("Saved locally: ")[1].strip()
                    
                    # EXTRACT FRAME (The Connector)
                    # Prefer local path over URL for reliability
                    if i < len(segments) - 1:
                        print(f"  > (Step-by-step) Extracting frame to prepare for Segment {index+1}...")
                        video_source = seg.get("video_path") or video_url
                        next_url = self.video_service.extract_and_upload_last_frame(video_source)
                        if next_url and next_url.startswith("http"):
                             seg["generated_last_frame"] = next_url
                        else:
                             print("  > WARNING: Frame extraction failed. Next segment will fail.")
                             
                    # Save State Immediately
                    with open(manifest_path, 'w') as f:
                        json.dump(manifest_data, f, indent=2)
                        
                except Exception as e:
                    print(f"  > Error parsing result: {e}")
                    seg["status"] = "error_postprocessing"
            else:
                seg["status"] = "failed"
                # Parse specific error if possible to show user
                print(f"  > Generation Failed. Reason: {result_str}")
                results_log.append(f"FAILED: {result_str}")
                
            # Save State (failed)
            with open(manifest_path, 'w') as f:
                json.dump(manifest_data, f, indent=2)
            
            # If failed, stop immediately regardless of limit
            if seg["status"] == "failed":
                print("  > Stopping chain due to failure.")
                break
                
        return f"Manifest Step Processing Complete (Processed {processed_count} segments).\nLog:\n" + "\n".join(results_log)

    def edit_manifest(self, run_id_or_path: str, modifications: list) -> str:
        """
        Edits an existing manifest.
        Args:
            modifications: List of dicts, validated via Pydantic.
        """
        from ..models import ManifestEditRequest
        
        # 0. Validate Request via Pydantic
        try:
            request = ManifestEditRequest(modifications=modifications)
        except Exception as e:
            return f"Validation Error: {e}"

        # 1. Load Manifest
        manifest_content = self.get_manifest(run_id_or_path)
        if manifest_content.startswith("Error"):
            return manifest_content
            
        try:
            manifest_data = json.loads(manifest_content)
        except:
            return "Error: Invalid JSON in manifest."
            
        manifest_path = os.path.join(os.getcwd(), "scorsese", "output", f"manifest_{manifest_data['run_id']}.json")
        segments = manifest_data.get("segments", [])
        
        log = []
        
        for mod in request.modifications:
            # Pydantic models, access via attributes
            if mod.action == "swap":
                idx_a = mod.seg_a
                idx_b = mod.seg_b
                
                seg_a_obj = next((s for s in segments if s["index"] == idx_a), None)
                seg_b_obj = next((s for s in segments if s["index"] == idx_b), None)
                
                if seg_a_obj and seg_b_obj:
                    # Swap Prompt
                    seg_a_obj["prompt"], seg_b_obj["prompt"] = seg_b_obj["prompt"], seg_a_obj["prompt"]
                    # Swap Metadata
                    seg_a_obj["metadata"], seg_b_obj["metadata"] = seg_b_obj["metadata"], seg_a_obj["metadata"]
                    
                    # RESET STATUS
                    seg_a_obj["status"] = "pending"
                    seg_b_obj["status"] = "pending"
                    
                    log.append(f"Swapped Segments {idx_a} and {idx_b}.")
                else:
                    log.append(f"Error: Could not find segments {idx_a} or {idx_b} to swap.")
                    
            elif mod.action == "update_prompt":
                idx = mod.index
                new_prompt = mod.prompt
                seg = next((s for s in segments if s["index"] == idx), None)
                if seg:
                    seg["prompt"] = new_prompt
                    seg["status"] = "pending"
                    log.append(f"Updated prompt for Segment {idx}.")
                else:
                    log.append(f"Error: Segment {idx} not found for update.")
                    
            elif mod.action == "delete":
                idx = mod.index
                # Remove from list
                segments = [s for s in segments if s["index"] != idx]
                # Re-index
                for i, s in enumerate(segments):
                    s["index"] = i + 1
                manifest_data["segments"] = segments
                log.append(f"Deleted Segment {idx} and re-indexed.")

            elif mod.action == "update_image":
                idx = mod.index
                new_image = mod.image_url
                seg = next((s for s in segments if s["index"] == idx), None)
                if seg:
                    # Update metadata input_image
                    seg.setdefault("metadata", {})["input_image"] = new_image
                    # Reset status to allow regeneration
                    seg["status"] = "pending"
                    log.append(f"Updated input image for Segment {idx}.")
                else:
                    log.append(f"Error: Segment {idx} not found for image update.")
                
        # Save
        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f, indent=2)
            
        return "Manifest Updated:\n" + "\n".join(log)

    def stitch_videos(self, video_paths: list) -> str:
        """Stitches videos together using MoviePy via script."""
        import uuid
        
        # Manifest/RunID Support
        if len(video_paths) == 1 and isinstance(video_paths[0], str):
            inp = video_paths[0]
            manifest_path = None
            
            # Case A: It's a JSON path
            if inp.endswith(".json") and os.path.exists(inp):
                manifest_path = inp
            # Case B: It's a Run ID (e.g. "unified_restored" or "a1b2c3d4")
            elif "/" not in inp and "\\" not in inp and "." not in inp:
                 candidate = os.path.join(os.getcwd(), "scorsese", "output", f"manifest_{inp}.json")
                 if os.path.exists(candidate):
                     manifest_path = candidate
            
            if manifest_path:
                 try:
                     print(f"Loading paths from Manifest: {manifest_path}")
                     with open(manifest_path, 'r') as f:
                         data = json.load(f)
                         
                     # Handle Rich Manifest (Dict) vs Simple List
                     if isinstance(data, dict) and "segments" in data:
                         # Extract paths from rich segments, ensuring they exist and are valid
                         video_paths = [
                             s["video_path"] for s in data["segments"] 
                             if s.get("status") == "generated" and s.get("video_path")
                         ]
                         print(f"  > Found {len(video_paths)} generated segments in Rich Manifest.")
                     elif isinstance(data, list):
                         video_paths = data
                         print(f"  > Found {len(video_paths)} paths in Simple Manifest.")
                     else:
                         return "Error: Unknown manifest format."
                         
                 except Exception as e:
                     return f"Error loading manifest: {e}"
            else:
                # If it looked like a path but didn't exist, we might fail here, but let logic proceed
                pass

        if not video_paths or len(video_paths) < 2:
            return "Error: Not enough valid video paths found in manifest/input to stitch."

        final_filename = f"stitched_final_{uuid.uuid4().hex[:6]}.mp4"
        
        # Prepare paths for the script
        safe_paths = [p.replace(os.sep, "/") for p in video_paths]
        # Create a string representation of the list of strings for the python script
        paths_str_list = ", ".join([f'"{p}"' for p in safe_paths])
        
        print(f"  > Stitching {len(safe_paths)} clips: {safe_paths}")

        stitching_script = f"""
import os
from moviepy import VideoFileClip, concatenate_videoclips

video_paths = [{paths_str_list}]
clips = []

try:
    for path in video_paths:
        if os.path.exists(path):
            clips.append(VideoFileClip(path))
        else:
            print(f"WARNING: File not found: {{path}}")
    
    if not clips:
        print("NO_CLIPS_LOADED")
        exit()

    final_clip = concatenate_videoclips(clips, method="compose")
    
    # Save to scorsese/output
    output_dir = os.path.join(os.getcwd(), "scorsese", "output")
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "{final_filename}")
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
    
    print(f"STITCH_SUCCESS: {{output_path}}")

except Exception as e:
    print(f"STITCH_ERROR: {{e}}")
finally:
    # Cleanup clips to release file locks
    for clip in clips:
        try: clip.close()
        except: pass
"""
        stitch_log = self.moviepy_service.run_script(stitching_script, save_name="stitch_manual")
        
        if "STITCH_SUCCESS" in stitch_log:
            import re
            match = re.search(r"STITCH_SUCCESS: (.*)", stitch_log)
            if match:
                return f"SUCCESS. Stitched video saved to: {match.group(1).strip()}"
        
        return f"Stitching failed. Logs:\n{stitch_log}"
        
    def get_manifest(self, run_id_or_path: str) -> str:
        """Retrieves the manifest content."""
        # Check if it's a full path
        if os.path.exists(run_id_or_path):
             path = run_id_or_path
        else:
             # Assume ID, look in output
             path = os.path.join(os.getcwd(), "scorsese", "output", f"manifest_{run_id_or_path}.json")
             
        if not os.path.exists(path):
            return "Error: Manifest not found."
            
        try:
            with open(path, 'r') as f:
                return f.read()
        except Exception as e:
            return f"Error reading manifest: {e}"

    def update_segment_status(self, run_id_or_path: str, segment_index: int, status: str, notes: str = None) -> str:
        """Updates the status of a specific segment in the manifest."""
        # Resolve Path
        if os.path.exists(run_id_or_path):
             path = run_id_or_path
        else:
             path = os.path.join(os.getcwd(), "scorsese", "output", f"manifest_{run_id_or_path}.json")
             
        if not os.path.exists(path):
            return "Error: Manifest not found."
            
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            # Find Segment
            found = False
            for seg in data.get("segments", []):
                if seg.get("index") == segment_index:
                    seg["status"] = status
                    if notes:
                        seg.setdefault("metadata", {})["notes"] = notes
                    found = True
                    break
            
            if not found:
                return f"Error: Segment index {segment_index} not found."
            
            # Save
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
                
            return f"Success. Updated Segment {segment_index} to '{status}'."
            
        except Exception as e:
            return f"Error updating manifest: {e}"
        

