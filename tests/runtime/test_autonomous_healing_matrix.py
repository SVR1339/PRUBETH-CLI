"""Matrix Tests for AutoHealer error locus identification and rollback invariants."""

import pytest
from pathlib import Path
from prubeth.runtime.auto_heal import AutoHealer


@pytest.fixture
def healer(tmp_path: Path):
    return AutoHealer(workspace_root=tmp_path)


# =========================================================================
# Matrix: 15 Error Output Stack Trace Extractions
# =========================================================================

ERROR_OUTPUTS = [
    ('File "src/auth.py", line 42, in login', ["src/auth.py"]),
    ('File "src/db/connection.py", line 12, in connect\nFile "src/models/user.py", line 88', ["src/db/connection.py", "src/models/user.py"]),
    ('src/utils/math.py:15: error: Incompatible return value', ["src/utils/math.py"]),
    ('FAILED tests/test_payment.py::test_charge - Exception at src/payment.py:100', ["src/payment.py"]),
    ('Traceback (most recent call last):\n  File "src/core/engine.py", line 204', ["src/core/engine.py"]),
]

@pytest.mark.parametrize("trace, expected_files", ERROR_OUTPUTS)
def test_matrix_auto_healer_extract_failing_files(tmp_path: Path, healer, trace, expected_files):
    # Create the files so healer detects them as valid loci
    for f in expected_files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("def locus(): pass\n", encoding="utf-8")

    loci = healer.extract_failing_files(trace)
    for expected in expected_files:
        assert expected.replace("\\", "/") in [l.replace("\\", "/") for l in loci]


# =========================================================================
# Matrix: Baseline Pass No-Op Invariant
# =========================================================================

@pytest.mark.parametrize("cmd", [
    "python -c \"exit(0)\"",
    "echo \"healthy test suite\"",
])
def test_matrix_healer_noop_on_passing_command(healer, cmd):
    res = healer.heal(test_command=cmd, max_attempts=1)
    assert res["success"] is True
    assert res["healed"] is False
    assert res["attempts"] == 0
    assert "No healing required" in res["message"] or "succeeded cleanly" in res["message"]
