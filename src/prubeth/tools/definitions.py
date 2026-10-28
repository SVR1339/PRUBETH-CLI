"""PRUBETH Native Tool Definitions & Multi-Provider Schema Converters.

Defines the core workspace engineering tool specifications and converts them
into provider-native schemas for Google Gemini, Anthropic Claude, and OpenAI/OpenRouter.
"""

from typing import List, Dict, Any, Optional

RAW_TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read lines from a file in the workspace.",
        "properties": {
            "path": {
                "type": "string",
                "description": "The workspace-relative or absolute file path to read."
            },
            "start_line": {
                "type": "integer",
                "description": "Optional 1-based start line index to begin reading from."
            },
            "end_line": {
                "type": "integer",
                "description": "Optional 1-based end line index to stop reading at."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to return (defaults to 120)."
            }
        },
        "required": ["path"]
    },
    {
        "name": "edit_file",
        "description": "Replace an exact target code block in an existing file with replacement code.",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to edit."
            },
            "target": {
                "type": "string",
                "description": "The exact existing text sequence to be replaced (must match character-for-character)."
            },
            "replacement": {
                "type": "string",
                "description": "The new replacement content to substitute in place of target."
            }
        },
        "required": ["path", "target", "replacement"]
    },
    {
        "name": "write_file",
        "description": "Create a new file or completely overwrite an existing file with the given content.",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to create or overwrite."
            },
            "content": {
                "type": "string",
                "description": "Full UTF-8 content to write to the file."
            }
        },
        "required": ["path", "content"]
    },
    {
        "name": "run_command",
        "description": "Execute a shell command in the persistent subshell (directory changes and environment persist).",
        "properties": {
            "command": {
                "type": "string",
                "description": "The exact shell command line string to execute."
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum seconds to wait before terminating command (default 60)."
            }
        },
        "required": ["command"]
    },
    {
        "name": "grep_search",
        "description": "Search for a regex or text query across files in a directory.",
        "properties": {
            "query": {
                "type": "string",
                "description": "The regex or literal pattern to search for."
            },
            "path": {
                "type": "string",
                "description": "Directory or file path to search within (defaults to current directory)."
            }
        },
        "required": ["query"]
    },
    {
        "name": "find_files",
        "description": "Find files matching a glob pattern in the workspace repository.",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match files (e.g. '**/*.py', 'src/**/config*')."
            }
        },
        "required": ["pattern"]
    },
    {
        "name": "code_search",
        "description": "Fast BM25 semantic search across indexed symbols and code chunks in the repository.",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language or keyword search query (e.g. 'token rate limit', 'database connect')."
            },
            "top_k": {
                "type": "integer",
                "description": "Number of top matching code chunks to return (default 4)."
            }
        },
        "required": ["query"]
    },
    {
        "name": "resolve_symbol",
        "description": "Locate class, function, or method definition anywhere in the workspace index.",
        "properties": {
            "name": {
                "type": "string",
                "description": "The exact name of the symbol (e.g. 'UniversalModelGateway', 'run_fluid_turn')."
            }
        },
        "required": ["name"]
    },
    {
        "name": "git_diff",
        "description": "Show current uncommitted git changes or staged working tree diffs.",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional file path to limit diff to."
            }
        },
        "required": []
    },
    {
        "name": "find_symbol_references",
        "description": "Locate all downstream callers, usages, and references of a symbol across the entire workspace repository using AST analysis.",
        "properties": {
            "name": {
                "type": "string",
                "description": "The exact name of the symbol (function, method, class, or attribute) to find callers for."
            }
        },
        "required": ["name"]
    }
]

def to_google_tools(extra_tools: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Converts tools into Google Gemini v1beta functionDeclarations schema."""
    type_map = {
        "string": "STRING",
        "integer": "INTEGER",
        "number": "NUMBER",
        "boolean": "BOOLEAN",
        "array": "ARRAY",
        "object": "OBJECT"
    }
    
    declarations = []
    for tool in RAW_TOOL_DEFINITIONS:
        props = {}
        for prop_name, prop_meta in tool["properties"].items():
            props[prop_name] = {
                "type": type_map.get(prop_meta.get("type", "string"), "STRING"),
                "description": prop_meta.get("description", "")
            }
        
        declarations.append({
            "name": tool["name"],
            "description": tool["description"],
            "parameters": {
                "type": "OBJECT",
                "properties": props,
                "required": tool.get("required", [])
            }
        })

    if extra_tools:
        for xt in extra_tools:
            schema = xt.get("input_schema", {})
            props = {}
            for p_name, p_meta in schema.get("properties", {}).items():
                p_type = p_meta.get("type", "string") if isinstance(p_meta, dict) else "string"
                p_desc = p_meta.get("description", "") if isinstance(p_meta, dict) else ""
                props[p_name] = {
                    "type": type_map.get(p_type, "STRING"),
                    "description": p_desc
                }
            declarations.append({
                "name": xt["name"],
                "description": xt.get("description", ""),
                "parameters": {
                    "type": "OBJECT",
                    "properties": props,
                    "required": schema.get("required", [])
                }
            })
    
    return [{"function_declarations": declarations}]

def to_anthropic_tools(extra_tools: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Converts tools into Anthropic Claude Messages API schema."""
    tools = []
    for tool in RAW_TOOL_DEFINITIONS:
        tools.append({
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": {
                "type": "object",
                "properties": tool["properties"],
                "required": tool.get("required", [])
            }
        })

    if extra_tools:
        for xt in extra_tools:
            tools.append({
                "name": xt["name"],
                "description": xt.get("description", ""),
                "input_schema": xt.get("input_schema") or {"type": "object", "properties": {}}
            })

    return tools

def to_openai_tools(extra_tools: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Converts tools into OpenAI / OpenRouter function calling schema."""
    tools = []
    for tool in RAW_TOOL_DEFINITIONS:
        tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": {
                    "type": "object",
                    "properties": tool["properties"],
                    "required": tool.get("required", [])
                }
            }
        })

    if extra_tools:
        for xt in extra_tools:
            tools.append({
                "type": "function",
                "function": {
                    "name": xt["name"],
                    "description": xt.get("description", ""),
                    "parameters": xt.get("input_schema") or {"type": "object", "properties": {}}
                }
            })

    return tools
