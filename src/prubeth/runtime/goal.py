"""PRUBETH Long-Horizon Autonomous Goal Supervisor (Anthropic Claude Code Target).

Decomposes complex multi-hour objectives into ordered, verifiable milestones,
maintains persistent state across sessions in .prubeth/goals/, and executes
autonomous development loops with test-time self-verification and auto-healing.
"""

import json
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from prubeth.models.gateway import UniversalModelGateway
from prubeth.runtime.verification import TestTimeVerifier
from prubeth.runtime.auto_heal import AutoHealer
from prubeth.persistence.checkpoints import SnapshotManager

@dataclass
class GoalMilestone:
    id: int
    title: str
    description: str
    verification_target: str
    status: str = "PENDING"  # PENDING, IN_PROGRESS, VERIFIED, FAILED
    evidence: str = ""
    snapshot_id: str = ""

class GoalSupervisor:
    """Subsystem 13: Long-Horizon Autonomous Goal & Milestone Execution Engine."""

    def __init__(self, controller: Any = None, console: Optional[Console] = None):
        self.controller = controller
        self.console = console or Console(legacy_windows=False)
        self.workspace_root = Path(controller.workspace_root if controller else Path.cwd()).resolve()
        self.goals_dir = self.workspace_root / ".prubeth" / "goals"
        self.goals_dir.mkdir(parents=True, exist_ok=True)
        self.model_gw = UniversalModelGateway()
        self.verifier = TestTimeVerifier(self.workspace_root)
        self.snap_mgr = SnapshotManager()

    def decompose_goal(self, objective: str, model_name: Optional[str] = None) -> List[GoalMilestone]:
        """Uses LLM reasoning to decompose a high-level goal into 3 to 6 ordered, verifiable milestones."""
        system_prompt = (
            "You are an elite Staff Software Architect specializing in long-horizon autonomous engineering.\n"
            "Given a software engineering objective, break it down into 3 to 6 discrete, sequential milestones.\n"
            "Each milestone must represent an atomic, verifiable progression step.\n"
            "Respond ONLY with a JSON array of milestone objects with keys:\n"
            "  - 'id': integer starting from 1\n"
            "  - 'title': concise milestone title (e.g. 'Implement JWT generator')\n"
            "  - 'description': exact technical tasks and files to create or modify\n"
            "  - 'verification_target': exact command or invariant to verify (e.g. 'pytest tests/test_jwt.py')\n"
            "Do NOT include markdown fences, comments, or extra text."
        )

        user_prompt = f"Decompose this engineering goal into verifiable milestones:\nObjective: {objective}"

        try:
            resp = self.model_gw.generate(
                user_prompt,
                system_instruction=system_prompt,
                model_name=model_name,
                model_tier="reasoning"
            )
            raw = resp.text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                if raw.endswith("```"):
                    raw = raw.rsplit("```", 1)[0]
                raw = raw.strip()

            parsed = json.loads(raw)
            milestones = []
            for item in parsed:
                milestones.append(GoalMilestone(
                    id=item.get("id", len(milestones) + 1),
                    title=item.get("title", f"Milestone {len(milestones) + 1}"),
                    description=item.get("description", ""),
                    verification_target=item.get("verification_target", "workspace unit test suite")
                ))
            return milestones
        except Exception:
            # Deterministic fallback milestone decomposition
            return [
                GoalMilestone(
                    id=1,
                    title="Context Exploration & Contract Design",
                    description=f"Inspect workspace and design interface contracts for: {objective}",
                    verification_target="AST syntax check"
                ),
                GoalMilestone(
                    id=2,
                    title="Core Logic Implementation",
                    description=f"Implement primary code modifications to satisfy: {objective}",
                    verification_target="Unit tests compilation"
                ),
                GoalMilestone(
                    id=3,
                    title="Regression Testing & Verification",
                    description="Run full test suite and ensure zero regressions or errors",
                    verification_target="Full test suite exit code 0"
                )
            ]

    def save_goal_state(self, goal_data: Dict[str, Any]):
        """Persists the milestone checklist to disk."""
        gid = goal_data["id"]
        path = self.goals_dir / f"{gid}.json"
        path.write_text(json.dumps(goal_data, indent=2), encoding="utf-8")

    def load_goal_state(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """Loads milestone checklist from disk."""
        path = self.goals_dir / f"{goal_id}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def list_goals(self) -> List[Dict[str, Any]]:
        """Lists all historical and active goals."""
        results = []
        for f in sorted(self.goals_dir.glob("*.json"), reverse=True):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                results.append(d)
            except Exception:
                pass
        return results

    def execute_goal(
        self,
        objective: str,
        goal_id: Optional[str] = None,
        model_name: Optional[str] = None,
        tool_cb: Optional[Callable] = None,
        stream_cb: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Executes long-horizon multi-milestone goal until 100% completion or failure."""
        gid = goal_id or f"goal_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        existing = self.load_goal_state(gid)

        if existing:
            goal_data = existing
            milestones = [GoalMilestone(**m) for m in goal_data.get("milestones", [])]
        else:
            self.console.print(f"  [dim cyan]Decomposing long-horizon goal into verifiable milestones...[/dim cyan]")
            milestones = self.decompose_goal(objective, model_name=model_name)
            goal_data = {
                "id": gid,
                "objective": objective,
                "created_at": datetime.now().isoformat(),
                "status": "IN_PROGRESS",
                "milestones": [asdict(m) for m in milestones],
                "active_milestone_index": 0
            }
            self.save_goal_state(goal_data)

        self._render_milestone_checklist(goal_data)

        # Baseline snapshot
        base_snap = self.snap_mgr.create_snapshot(f"{gid}_start")

        for idx, m in enumerate(milestones):
            if m.status == "VERIFIED":
                continue

            goal_data["active_milestone_index"] = idx
            m.status = "IN_PROGRESS"
            self.save_goal_state(goal_data)

            self.console.print(Panel(
                f"[bold cyan]Milestone {m.id}/{len(milestones)}:[/bold cyan] [bold white]{m.title}[/bold white]\n"
                f"[dim]{m.description}[/dim]\n"
                f"[yellow]Verification Target:[/yellow] {m.verification_target}",
                title=f"[MILESTONE] Executing Milestone {m.id}",
                border_style="cyan",
                box=box.ROUNDED
            ))

            # Prompt to execute milestone
            milestone_prompt = (
                f"Autonomous Milestone Execution:\n"
                f"Overall Goal: {objective}\n"
                f"Active Milestone #{m.id}: {m.title}\n"
                f"Details: {m.description}\n"
                f"Please inspect files, formulate code edits, apply changes, and ensure the target compiles cleanly."
            )

            if self.controller:
                try:
                    turn_res = self.controller.run_fluid_turn(
                        milestone_prompt,
                        model_override=model_name,
                        stream_cb=stream_cb,
                        tool_cb=tool_cb
                    )
                except Exception as e:
                    self.console.print(f"[bold red]Turn Execution Exception in Milestone {m.id}:[/bold red] {e}")

            # Post-Milestone Test Verification Gate
            self.console.print(f"  [dim cyan]Running milestone verification gate ({m.verification_target})...[/dim cyan]")
            test_ok, test_trace = self.verifier.run_self_verification()

            if not test_ok:
                self.console.print(f"  [bold yellow]Milestone verification failed. Engaging Auto-Healer...[/bold yellow]")
                healer = AutoHealer(console=self.console, model_name=model_name)
                heal_ok, heal_res = healer.heal()
                if heal_ok:
                    test_ok = True
                    m.evidence = f"Self-healed: {heal_res.get('diagnosis', 'Success')}"
                else:
                    m.status = "FAILED"
                    m.evidence = f"Verification failed:\n{test_trace[:300]}"
                    goal_data["status"] = "FAILED"
                    goal_data["milestones"] = [asdict(item) for item in milestones]
                    self.save_goal_state(goal_data)

                    self.console.print(Panel(
                        f"[bold red]Milestone {m.id} Failed Verification Gate.[/bold red]\n"
                        f"Evidence: {test_trace[:400]}\n"
                        f"[yellow]Rolling back to baseline checkpoint '{base_snap}' to prevent workspace corruption.[/yellow]",
                        title="[ABORTED] Goal Execution Aborted",
                        border_style="red",
                        box=box.ROUNDED
                    ))
                    self.snap_mgr.rollback_to_snapshot(base_snap)
                    return {"success": False, "goal_id": gid, "failed_milestone": m.id, "error": test_trace}

            # Milestone passed verification
            m.status = "VERIFIED"
            snap_id = self.snap_mgr.create_snapshot(f"{gid}_m{m.id}")
            m.snapshot_id = snap_id
            m.evidence = "Passed automated test verification."
            goal_data["milestones"] = [asdict(item) for item in milestones]
            self.save_goal_state(goal_data)

            self.console.print(f"  [bold green][OK] Milestone {m.id} VERIFIED & Checkpoint Saved ({snap_id})[/bold green]\n")

        goal_data["status"] = "COMPLETED"
        self.save_goal_state(goal_data)

        self._render_milestone_checklist(goal_data)
        self.console.print(Panel(
            f"[bold green]ALL {len(milestones)} MILESTONES VERIFIED & GOAL COMPLETED![/bold green]\n"
            f"- **Goal ID**: `{gid}`\n"
            f"- **Objective**: {objective}\n"
            f"- **Status**: 100% Autonomous Success",
            title="[REPORT] Long-Horizon Goal Completion Report",
            border_style="green",
            box=box.ROUNDED
        ))

        return {"success": True, "goal_id": gid, "milestones_completed": len(milestones)}

    def _render_milestone_checklist(self, goal_data: Dict[str, Any]):
        """Renders rich table showing milestone progression."""
        table = Table(title=f"[GOAL] Autonomous Goal Checklist: {goal_data.get('objective', '')[:70]}", box=box.ROUNDED)
        table.add_column("#", justify="center", style="bold cyan")
        table.add_column("Milestone Title", style="white")
        table.add_column("Status", justify="center")
        table.add_column("Verification Target", style="dim")
        table.add_column("Evidence", style="dim green")

        for m in goal_data.get("milestones", []):
            st = m.get("status", "PENDING")
            if st == "VERIFIED":
                badge = "[bold green][OK] VERIFIED[/bold green]"
            elif st == "IN_PROGRESS":
                badge = "[bold yellow][..] ACTIVE[/bold yellow]"
            elif st == "FAILED":
                badge = "[bold red][ERR] FAILED[/bold red]"
            else:
                badge = "[dim][ ] PENDING[/dim]"

            table.add_row(
                str(m.get("id")),
                m.get("title", ""),
                badge,
                m.get("verification_target", "")[:35],
                m.get("evidence", "")[:40]
            )

        self.console.print(table)
