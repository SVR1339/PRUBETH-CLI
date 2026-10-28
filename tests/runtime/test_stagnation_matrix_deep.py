"""Deep Trajectory Simulation Tests for Stagnation Interceptors and Infinite Loops."""

import pytest
from prubeth.runtime.stagnation import (
    StagnationDetector,
    StagnationInterceptor,
    StagnationReport
)


@pytest.fixture
def interceptor():
    return StagnationInterceptor(
        max_consecutive_same=3,
        max_cycle_window=10,
        max_repeated_failures=3,
        similarity_threshold=0.65
    )


# =========================================================================
# Matrix: Cyclic Trajectory Oscillations of Periods 2, 3, 4, 5
# =========================================================================

@pytest.mark.parametrize("period", [2, 3, 4, 5])
def test_matrix_cyclic_trajectory_detection(interceptor, period):
    cycle_tools = [f"tool_step_{i}" for i in range(period)]

    # Repeat the cycle twice
    for cycle_num in range(2):
        for tool in cycle_tools:
            res = interceptor.intercept_execution(tool, {"step": tool})

    assert res.is_stalled is True
    assert res.cycle_length == period
    assert res.suggested_action == "inject_feedback"


# =========================================================================
# Matrix: Multi-File Ping-Pong Oscillations
# =========================================================================

@pytest.mark.parametrize("file_idx", range(5))
def test_matrix_concurrent_file_ping_pong_detection(interceptor, file_idx):
    target_f = f"src/module_{file_idx}.py"
    v_a = f"def run(): return {file_idx} * 10"
    v_b = f"def run(): return {file_idx} * 20"

    # Ping-pong 4 times
    interceptor.intercept_execution("write_file", {"path": target_f, "replacement": v_a})
    interceptor.intercept_execution("write_file", {"path": target_f, "replacement": v_b})
    interceptor.intercept_execution("write_file", {"path": target_f, "replacement": v_a})
    res = interceptor.intercept_execution("write_file", {"path": target_f, "replacement": v_b})

    assert res.is_stalled is True
    assert target_f in res.reason


# =========================================================================
# Matrix: Repeated Failure Cascades
# =========================================================================

@pytest.mark.parametrize("streak_threshold", [2, 3, 4, 5])
def test_matrix_failure_streak_thresholds(streak_threshold):
    interceptor = StagnationInterceptor(max_repeated_failures=streak_threshold)

    for i in range(streak_threshold - 1):
        res = interceptor.intercept_execution("run_shell", {"command": f"cargo test --test={i}"}, success=False)
        assert res.is_stalled is False

    # The failing step that reaches the threshold
    res_final = interceptor.intercept_execution("run_shell", {"command": "cargo test --final"}, success=False)
    assert res_final.is_stalled is True
    assert f"failed {streak_threshold} consecutive times" in res_final.reason


# =========================================================================
# Matrix: Safe Trajectories with Interleaved Benign Operations
# =========================================================================

@pytest.mark.parametrize("trajectory_length", [5, 10, 15, 20])
def test_matrix_healthy_exploratory_trajectories_do_not_stall(interceptor, trajectory_length):
    for i in range(trajectory_length):
        # Healthy developer trajectory: read -> edit -> test -> git status
        tool_name = ["read_file", "edit_file", "test_runner", "git_status"][i % 4]
        res = interceptor.intercept_execution(
            tool_name=tool_name,
            args={"path": f"src/file_{i}.py", "index": i},
            success=True
        )
        assert res.is_stalled is False
