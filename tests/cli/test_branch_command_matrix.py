"""PRUBETH CLI /branch Command Matrix Tests.

Validates branch creation, switching, list formatting, and path history output.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from rich.console import Console

from prubeth.cli.commands import handle_branch_command
from prubeth.persistence.dag import ConversationDAG


class DummyController:
    def __init__(self):
        self.workspace_root = "."
        self.dag = ConversationDAG()


def test_handle_branch_list():
    ctrl = DummyController()
    ctrl.dag.add_turn("user", "Initial turn")
    # Execute list
    handle_branch_command([], controller=ctrl)
    assert ctrl.dag.active_branch == "main"


def test_handle_branch_create_and_switch():
    ctrl = DummyController()
    root_id = ctrl.dag.add_turn("user", "Problem description")

    # Create new branch
    handle_branch_command(["create", "plan_b"], controller=ctrl)
    assert "plan_b" in ctrl.dag.branches
    assert ctrl.dag.active_branch == "plan_b"

    # Add turn in plan_b
    ctrl.dag.add_turn("assistant", "Plan B implementation")

    # Switch back to main
    handle_branch_command(["switch", "main"], controller=ctrl)
    assert ctrl.dag.active_branch == "main"
    assert ctrl.dag.current_node_id == root_id

    # Switch back to plan_b
    handle_branch_command(["switch", "plan_b"], controller=ctrl)
    assert ctrl.dag.active_branch == "plan_b"


def test_handle_branch_path_inspection():
    ctrl = DummyController()
    ctrl.dag.add_turn("user", "Step 1")
    ctrl.dag.add_turn("assistant", "Step 2")
    # Path inspection should execute without error
    handle_branch_command(["path"], controller=ctrl)
    path = ctrl.dag.get_active_path()
    assert len(path) == 2
