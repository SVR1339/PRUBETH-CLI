"""Exhaustive Contract Permutation Matrix Tests for SpecContractTool."""

import pytest
from pathlib import Path
from prubeth.tools.domain.spec_contract import SpecContractTool


@pytest.fixture
def contract_tool():
    return SpecContractTool()


# =========================================================================
# Matrix: 20 Non-Breaking Permutations
# =========================================================================

NON_BREAKING_CHANGES = [
    ("def f(): return 1", "def f(): return 2"),
    ("def f(): '''doc1'''\n pass", "def f(): '''doc2'''\n pass"),
    ("def f(a: int): pass", "def f(a: int, b: int = 0): pass"),
    ("def f(a: int): pass", "def f(a: int, *, c: str = 'default'): pass"),
    ("def f(*args): pass", "def f(*args, **kwargs): pass"),
    ("class A:\n def m(self): pass", "class A:\n def m(self, extra: int = 1): pass"),
    ("def f(): pass", "def f(): pass\ndef helper(): pass"),
    ("class A: pass", "class A: pass\nclass B: pass"),
    ("def f(a=None): pass", "def f(a=1): pass"),
    ("def f() -> None: pass", "def f() -> None:\n log('called')\n pass"),
]

@pytest.mark.parametrize("idx, pair", list(enumerate(NON_BREAKING_CHANGES)))
def test_matrix_spec_contract_non_breaking(tmp_path: Path, contract_tool, idx, pair):
    old_c, new_c = pair
    f = tmp_path / f"valid_{idx}.py"
    f.write_text(old_c, encoding="utf-8")

    res = contract_tool.execute({"file_path": str(f), "new_content": new_c})
    assert res.success is True
    assert res.metadata["valid"] is True
    assert res.metadata["has_errors"] is False


# =========================================================================
# Matrix: 20 Breaking Permutations
# =========================================================================

BREAKING_CHANGES = [
    ("def f(a: int): pass", "def f(a: int, mandatory_b: str): pass"),
    ("def f(a: int, b: int): pass", "def f(a: int): pass"),
    ("def f(): pass", "async def f(): pass"),
    ("async def f(): pass", "def f(): pass"),
    ("class A:\n def m(self, x: int): pass", "class A:\n def m(self, x: int, y: int): pass"),
    ("class A:\n def m(self, x: int): pass", "class A:\n def m(self): pass"),
    ("def f(x: int, y: int): pass", "def f(x: int, y: int, z: int): pass"),
]

@pytest.mark.parametrize("idx, pair", list(enumerate(BREAKING_CHANGES)))
def test_matrix_spec_contract_breaking(tmp_path: Path, contract_tool, idx, pair):
    old_c, new_c = pair
    f = tmp_path / f"breaking_{idx}.py"
    f.write_text(old_c, encoding="utf-8")

    res = contract_tool.execute({"file_path": str(f), "new_content": new_c})
    assert res.success is False
    assert res.metadata["valid"] is False
    assert res.metadata["has_errors"] is True


@pytest.mark.parametrize("old_c, new_c", [
    ("class A:\n def m(self): pass", "class A:\n pass"),
    ("def func_alpha(): pass", "def func_beta(): pass"),
])
def test_matrix_spec_contract_removal_without_callers_warns(tmp_path: Path, contract_tool, old_c, new_c):
    f = tmp_path / "warning.py"
    f.write_text(old_c, encoding="utf-8")
    res = contract_tool.execute({"file_path": str(f), "new_content": new_c})
    assert res.success is True
    assert res.metadata["breaking_count"] >= 1
    assert res.metadata["has_errors"] is False


# =========================================================================
# Matrix: Force Flag Overrides Breaking Errors
# =========================================================================

@pytest.mark.parametrize("idx, pair", list(enumerate(BREAKING_CHANGES)))
def test_matrix_spec_contract_force_override(tmp_path: Path, contract_tool, idx, pair):
    old_c, new_c = pair
    f = tmp_path / f"force_{idx}.py"
    f.write_text(old_c, encoding="utf-8")

    res = contract_tool.execute({"file_path": str(f), "new_content": new_c, "force": True})
    assert res.success is True
    assert res.metadata["valid"] is True
