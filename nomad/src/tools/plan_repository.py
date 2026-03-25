"""
Plan Repository - Manage saving and loading verified plans as JSON

Provides:
- save_plan(): Save verified itinerary to JSON by task_id
- load_plan(): Load verified itinerary from JSON by task_id  
- get_all_plans(): List all saved plans
- delete_plan(): Remove a saved plan
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List


class PlanRepository:
    """Manages verified plans in JSON storage."""
    
    def __init__(self, base_dir="plans"):
        """
        Initialize repository.
        
        Args:
            base_dir (str): Base directory to store plans. 
                Creates directory structure: plans/{task_id}/plan.json
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def save_plan(self, plan: Dict, task_id: str, save_metadata: bool = True) -> str:
        """
        Save a verified plan to JSON file.
        
        Args:
            plan (dict): Verified itinerary dict (from Verifier)
            task_id (str): Task identifier
            save_metadata (bool): Whether to add timestamp and metadata
        
        Returns:
            str: Path to saved file
        """
        # Create task directory
        task_dir = self.base_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Add metadata if requested
        if save_metadata:
            plan_with_meta = {
                "metadata": {
                    "task_id": task_id,
                    "saved_at": datetime.now().isoformat(),
                    "schema_version": "1.0"
                },
                "plan": plan
            }
        else:
            plan_with_meta = plan
        
        # Save to JSON
        plan_file = task_dir / "plan.json"
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump(plan_with_meta, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Plan saved: {plan_file}")
        return str(plan_file)
    
    def load_plan(self, task_id: str) -> Optional[Dict]:
        """
        Load a verified plan from JSON file.
        
        Args:
            task_id (str): Task identifier
        
        Returns:
            dict: Plan data, or None if not found
            
        Raises:
            FileNotFoundError: If plan file doesn't exist
        """
        plan_file = self.base_dir / task_id / "plan.json"
        
        if not plan_file.exists():
            raise FileNotFoundError(f"Plan not found for task_id: {task_id}")
        
        with open(plan_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Extract plan if it has metadata
        if "metadata" in data and "plan" in data:
            return data["plan"]
        
        return data
    
    def load_plan_with_metadata(self, task_id: str) -> Dict:
        """
        Load a plan with its metadata.
        
        Args:
            task_id (str): Task identifier
        
        Returns:
            dict: {"metadata": {...}, "plan": {...}}
        """
        plan_file = self.base_dir / task_id / "plan.json"
        
        if not plan_file.exists():
            raise FileNotFoundError(f"Plan not found for task_id: {task_id}")
        
        with open(plan_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return data
    
    def get_all_plans(self) -> List[str]:
        """
        Get all task_ids with saved plans.
        
        Returns:
            List of task_id strings
        """
        if not self.base_dir.exists():
            return []
        
        task_ids = []
        for item in self.base_dir.iterdir():
            if item.is_dir() and (item / "plan.json").exists():
                task_ids.append(item.name)
        
        return sorted(task_ids)
    
    def plan_exists(self, task_id: str) -> bool:
        """Check if a plan exists for task_id."""
        plan_file = self.base_dir / task_id / "plan.json"
        return plan_file.exists()
    
    def delete_plan(self, task_id: str) -> bool:
        """
        Delete a saved plan.
        
        Args:
            task_id (str): Task identifier
        
        Returns:
            bool: True if deleted, False if not found
        """
        plan_file = self.base_dir / task_id / "plan.json"
        
        if not plan_file.exists():
            return False
        
        plan_file.unlink()
        
        # Try to remove empty directory
        task_dir = plan_file.parent
        if not any(task_dir.iterdir()):
            task_dir.rmdir()
        
        print(f"✓ Plan deleted: {plan_file}")
        return True
    
    def export_plans_summary(self, output_file: str = "plans_summary.json") -> str:
        """
        Export summary of all saved plans.
        
        Args:
            output_file (str): Output filename
        
        Returns:
            str: Path to summary file
        """
        summary = {
            "generated_at": datetime.now().isoformat(),
            "total_plans": 0,
            "plans": {}
        }
        
        for task_id in self.get_all_plans():
            try:
                data = self.load_plan_with_metadata(task_id)
                plan = data.get("plan", {})
                metadata = data.get("metadata", {})
                
                summary["plans"][task_id] = {
                    "saved_at": metadata.get("saved_at"),
                    "destination": plan.get("itinerary", {}).get("trip_summary", {}).get("destination"),
                    "origin": plan.get("itinerary", {}).get("trip_summary", {}).get("origin"),
                    "duration_nights": plan.get("itinerary", {}).get("trip_summary", {}).get("duration_nights"),
                    "total_cost": plan.get("itinerary", {}).get("cost_breakdown", {}).get("total_estimated"),
                    "is_valid": plan.get("is_valid")
                }
                summary["total_plans"] += 1
            except Exception as e:
                print(f"Warning: Could not summarize {task_id}: {e}")
        
        summary_path = Path(output_file)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Summary exported: {summary_path}")
        return str(summary_path)


# Convenience functions
_default_repo = None

def get_repo(base_dir="plans") -> PlanRepository:
    """Get or create default repository instance."""
    global _default_repo
    if _default_repo is None:
        _default_repo = PlanRepository(base_dir)
    return _default_repo


def save_plan(plan: Dict, task_id: str) -> str:
    """Save plan to default repository."""
    return get_repo().save_plan(plan, task_id)


def load_plan(task_id: str) -> Dict:
    """Load plan from default repository."""
    return get_repo().load_plan(task_id)


def list_all_plans() -> List[str]:
    """List all saved plans."""
    return get_repo().get_all_plans()
