"""
Auto Evaluator - Automatic evaluation of plans from repository

Workflow:
1. Agent generates plan → saves to repository
2. AutoEvaluator automatically reads from repository
3. Generates evaluation report
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from .plan_repository import PlanRepository
from .evaluator import NomadEvaluator


from config import PLANS_DIR, EVALUATIONS_DIR


class AutoEvaluator:
    """Automatically evaluate all or specific plans from repository."""
    
    def __init__(self, plan_repo_dir: str = None, output_dir: str = None):
        """
        Initialize auto evaluator.
        
        Args:
            plan_repo_dir: Directory where plans are stored
            output_dir: Directory to save evaluation reports
        """
        self.repo = PlanRepository(base_dir=plan_repo_dir or PLANS_DIR)
        # Load orchestrator_tasks.json so evaluator uses task-defined expected_tools & constraints
        _tasks_file = Path(__file__).resolve().parent.parent.parent / "benchmark" / "data" / "orchestrator_tasks.json"
        self.evaluator = NomadEvaluator(task_file=str(_tasks_file) if _tasks_file.exists() else None)
        self.output_dir = Path(output_dir or EVALUATIONS_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def evaluate_single_plan(self, task_id: str, 
                           hard_constraints: Optional[List[str]] = None,
                           expected_tools: Optional[List[str]] = None) -> Dict:
        """
        Evaluate a single plan from repository.
        
        Args:
            task_id: Task ID to evaluate
            hard_constraints: Override constraints
            expected_tools: Override expected tools
        
        Returns:
            Evaluation result dict
        """
        print(f"[AutoEvaluator] Evaluating {task_id}...", end=" ", flush=True)
        
        try:
            result = self.evaluator.evaluate_from_repo(
                task_id=task_id,
                plan_repo_dir=str(self.repo.base_dir),
                hard_constraints=hard_constraints,
                expected_tools=expected_tools
            )
            print(f"✓ Score: {result['overall_score']:.1%}")
            return result
        except Exception as e:
            print(f"✗ Error: {e}")
            return {"error": str(e), "task_id": task_id}
    
    def evaluate_all_plans(self, 
                          hard_constraints: Optional[List[str]] = None,
                          expected_tools: Optional[List[str]] = None) -> Dict[str, Dict]:
        """
        Evaluate all plans in repository.
        
        Args:
            hard_constraints: Override constraints for all
            expected_tools: Override expected tools for all
        
        Returns:
            Dict mapping task_id to evaluation results
        """
        all_task_ids = self.repo.get_all_plans()
        
        if not all_task_ids:
            print("[AutoEvaluator] No plans found in repository!")
            return {}
        
        print(f"\n[AutoEvaluator] Evaluating {len(all_task_ids)} plans...")
        print("="*70)
        
        results = {}
        for task_id in all_task_ids:
            result = self.evaluate_single_plan(
                task_id,
                hard_constraints=hard_constraints,
                expected_tools=expected_tools
            )
            results[task_id] = result
        
        return results
    
    def save_evaluation_report(self, results: Dict[str, Dict], 
                             report_name: str = "evaluation_report") -> str:
        """
        Save evaluation results to JSON report.
        
        Args:
            results: Dict of task_id -> evaluation result
            report_name: Name of report file (without .json)
        
        Returns:
            Path to saved report
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "total_plans": len(results),
            "summary": {
                "average_score": 0,
                "best_score": 0,
                "worst_score": 1,
                "excellent_count": 0,
                "acceptable_count": 0,
                "needs_revision_count": 0,
                "fractional_csr_mean": 0,
                "binary_csr_pass_count": 0,
            },
            "results": {}
        }
        
        scores = []
        csr_scores = []
        binary_passes = 0
        for task_id, result in results.items():
            if "error" in result:
                report["results"][task_id] = {"error": result["error"]}
                continue
            
            score = result.get("overall_score", 0)
            csr = result.get("csr_score", 0)
            scores.append(score)
            csr_scores.append(csr)
            
            binary_pass = csr >= 1.0
            if binary_pass:
                binary_passes += 1
            
            # Count ratings
            if score >= 0.8:
                report["summary"]["excellent_count"] += 1
            elif score >= 0.6:
                report["summary"]["acceptable_count"] += 1
            else:
                report["summary"]["needs_revision_count"] += 1
            
            # Store compact result with fractional + binary CSR
            report["results"][task_id] = {
                "overall_score": score,
                "schema_compliance": result.get("schema_compliance", 0),
                "csr_score": result.get("csr_score", 0),
                "csr_binary_pass": binary_pass,
                "tool_accuracy": result.get("tool_accuracy", 0),
                "itinerary_validity": result.get("itinerary_validity", False),
                "has_conflicts": result.get("conflict_report", {}).get("has_conflicts", False),
                "constraint_breakdown": result.get("constraint_breakdown", {}),
                "errors": result.get("conflict_report", {}).get("errors", []),
                "warnings": result.get("conflict_report", {}).get("warnings", [])
            }
        
        # Calculate summary
        if scores:
            report["summary"]["average_score"] = sum(scores) / len(scores)
            report["summary"]["best_score"] = max(scores)
            report["summary"]["worst_score"] = min(scores)
        if csr_scores:
            report["summary"]["fractional_csr_mean"] = sum(csr_scores) / len(csr_scores)
        report["summary"]["binary_csr_pass_count"] = binary_passes
        
        # Save
        report_file = self.output_dir / f"{report_name}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return str(report_file)
    
    def print_summary(self, results: Dict[str, Dict]):
        """Print summary of evaluation results."""
        print("\n" + "="*70)
        print("EVALUATION SUMMARY")
        print("="*70)
        
        if not results:
            print("No results to display.")
            return
        
        scores = []
        excellent = 0
        acceptable = 0
        needs_revision = 0
        errors = 0
        
        for task_id, result in results.items():
            if "error" in result:
                errors += 1
                print(f"  ✗ {task_id}: ERROR - {result['error']}")
                continue
            
            score = result.get("overall_score", 0)
            scores.append(score)
            
            if score >= 0.8:
                excellent += 1
                status = "✓ EXCELLENT"
            elif score >= 0.6:
                acceptable += 1
                status = "~ ACCEPTABLE"
            else:
                needs_revision += 1
                status = "✗ REVISION NEEDED"
            
            print(f"  {status:15} {task_id:20} {score:6.1%}")
        
        print("\n" + "-"*70)
        print(f"{'TOTALS':15} {len(results):20}")
        print(f"  Excellent:     {excellent}")
        print(f"  Acceptable:    {acceptable}")
        print(f"  Needs Revision: {needs_revision}")
        if errors:
            print(f"  Errors:        {errors}")
        
        if scores:
            print(f"\nAverage Score: {sum(scores)/len(scores):.1%}")
            print(f"Best Score:    {max(scores):.1%}")
            print(f"Worst Score:   {min(scores):.1%}")
        print("="*70)
    
    def auto_evaluate_and_report(self, report_name: str = "evaluation_report") -> tuple:
        """
        One-line auto evaluation: read all plans, evaluate, save report.
        
        Returns:
            (results_dict, report_file_path)
        """
        # Evaluate all
        results = self.evaluate_all_plans()
        
        # Print summary
        self.print_summary(results)
        
        # Save report
        report_path = self.save_evaluation_report(results, report_name)
        print(f"\n✓ Report saved: {report_path}")
        
        return results, report_path


# Convenience functions
_auto_evaluator = None

def get_auto_evaluator(plan_repo_dir: str = None, 
                       output_dir: str = None) -> AutoEvaluator:
    """Get or create default auto evaluator instance."""
    global _auto_evaluator
    if _auto_evaluator is None:
        _auto_evaluator = AutoEvaluator(plan_repo_dir, output_dir)
    return _auto_evaluator


def auto_evaluate_all(report_name: str = "evaluation_report") -> tuple:
    """One-line evaluation of all plans."""
    evaluator = get_auto_evaluator()
    return evaluator.auto_evaluate_and_report(report_name)
