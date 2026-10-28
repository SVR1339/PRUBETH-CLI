"""Matrix Tests for CrashDebuggerTool across Python, Node.js/TypeScript, Go, and Rust."""

import pytest
from pathlib import Path
from prubeth.tools.domain.crash_debugger import CrashDebuggerTool


@pytest.fixture
def debugger():
    return CrashDebuggerTool()


# =========================================================================
# Matrix: 10 Python Exception Varieties
# =========================================================================

PYTHON_EXCEPTIONS = [
    ("ZeroDivisionError", "division by zero", '  File "src/math.py", line 42, in div\n    return a / b\nZeroDivisionError: division by zero'),
    ("KeyError", "'missing_key'", '  File "src/config.py", line 15, in load\n    return cfg["missing_key"]\nKeyError: \'missing_key\''),
    ("IndexError", "list index out of range", '  File "src/list.py", line 8, in get_item\n    return arr[100]\nIndexError: list index out of range'),
    ("TypeError", "can only concatenate str (not 'int') to str", '  File "src/str.py", line 20, in concat\n    return s + 42\nTypeError: can only concatenate str (not \'int\') to str'),
    ("ValueError", "invalid literal for int() with base 10: 'abc'", '  File "src/parse.py", line 12, in to_int\n    return int("abc")\nValueError: invalid literal for int() with base 10: \'abc\''),
    ("AttributeError", "'NoneType' object has no attribute 'execute'", '  File "src/run.py", line 33, in start\n    db.execute()\nAttributeError: \'NoneType\' object has no attribute \'execute\''),
    ("FileNotFoundError", "[Errno 2] No such file or directory: 'data.txt'", '  File "src/io.py", line 5, in read\n    open("data.txt")\nFileNotFoundError: [Errno 2] No such file or directory: \'data.txt\''),
    ("RecursionError", "maximum recursion depth exceeded", '  File "src/loop.py", line 99, in recurse\n    recurse()\nRecursionError: maximum recursion depth exceeded'),
    ("AssertionError", "Expected 200 OK but got 500", '  File "tests/test_api.py", line 50, in test_req\n    assert status == 200\nAssertionError: Expected 200 OK but got 500'),
    ("PermissionError", "[Errno 13] Permission denied: '/etc/shadow'", '  File "src/sys.py", line 10, in access\n    open("/etc/shadow")\nPermissionError: [Errno 13] Permission denied: \'/etc/shadow\''),
]

@pytest.mark.parametrize("exc_type, exc_msg, tb", PYTHON_EXCEPTIONS)
def test_matrix_python_traceback_parsing(debugger, exc_type, exc_msg, tb):
    full_tb = f"Traceback (most recent call last):\n{tb}"
    res = debugger.execute({"traceback": full_tb})
    assert res.success is True
    assert res.metadata["exception"]["type"] == exc_type
    assert len(res.metadata["frames"]) >= 1
    assert res.metadata["root_frame"] is not None


# =========================================================================
# Matrix: 10 Node.js / JavaScript / TypeScript Stack Traces
# =========================================================================

NODE_TRACEBACKS = [
    ("ReferenceError", "window is not defined", "ReferenceError: window is not defined\n    at renderComponent (/app/src/ui.tsx:24:5)\n    at serverRender (/app/src/server.ts:88:12)"),
    ("TypeError", "Cannot read properties of undefined (reading 'map')", "TypeError: Cannot read properties of undefined (reading 'map')\n    at formatUsers (/app/src/format.ts:14:18)\n    at Object.handler (/app/src/api.ts:45:9)"),
    ("SyntaxError", "Unexpected token < in JSON at position 0", "SyntaxError: Unexpected token < in JSON at position 0\n    at JSON.parse (<anonymous>)\n    at parseResponse (/app/src/client.ts:32:15)"),
    ("RangeError", "Maximum call stack size exceeded", "RangeError: Maximum call stack size exceeded\n    at factorial (/app/src/math.js:10:5)\n    at factorial (/app/src/math.js:10:12)"),
    ("URIError", "URI malformed", "URIError: URI malformed\n    at decodeURI (<anonymous>)\n    at parseRoute (/app/src/router.ts:18:7)"),
]

@pytest.mark.parametrize("exc_type, exc_msg, tb", NODE_TRACEBACKS)
def test_matrix_nodejs_traceback_parsing(debugger, exc_type, exc_msg, tb):
    res = debugger.execute({"traceback": tb})
    assert res.success is True
    assert len(res.metadata["frames"]) >= 1
    root = res.metadata["root_frame"]
    assert root["language"] == "javascript"
    assert root["line"] > 0
