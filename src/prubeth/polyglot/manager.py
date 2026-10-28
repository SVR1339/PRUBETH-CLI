"""PRUBETH Polyglot Language Stack Manager.

Coordinates language stack resolution, user preferences, and runtime verification commands.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from prubeth.polyglot.stacks import (
    LanguageStack,
    SUPPORTED_STACKS,
    get_stack_by_id,
    detect_stack_from_workspace
)
from prubeth.config.manager import ConfigManager

class PolyglotLanguageManager:
    """Manages language stack detection, user overrides, and verification bindings."""

    def __init__(self, workspace_root: Optional[Any] = None, config_manager: Optional[ConfigManager] = None):
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else Path.cwd().resolve()
        self.cfg_mgr = config_manager or ConfigManager()

    def get_configured_language(self) -> str:
        """Returns the user's default language setting ('auto' or specific stack id)."""
        cfg = self.cfg_mgr.load_config()
        return str(cfg.get("default_language", "auto")).lower().strip()

    def set_default_language(self, stack_id: str) -> Tuple[bool, str]:
        """Sets the global preferred development language."""
        clean = stack_id.lower().strip()
        if clean in ["auto", "detect", "default"]:
            self.cfg_mgr.set("default_language", "auto")
            return True, "Set language preference to 'auto' (dynamic workspace detection)."

        stack = get_stack_by_id(clean)
        if not stack:
            valid = ", ".join(list(SUPPORTED_STACKS.keys()) + ["auto"])
            return False, f"Unknown language stack '{stack_id}'. Available: {valid}"

        self.cfg_mgr.set("default_language", stack.id)
        return True, f"Successfully set default language stack to '{stack.name}' ({stack.id})."

    def resolve_active_stack(self) -> LanguageStack:
        """Resolves the active stack taking into account user configuration and repository markers."""
        pref = self.get_configured_language()
        if pref != "auto":
            configured_stack = get_stack_by_id(pref)
            if configured_stack:
                return configured_stack

        # Auto-detect from workspace files
        return detect_stack_from_workspace(self.workspace_root)

    def list_all_stacks(self) -> List[Dict[str, Any]]:
        """Returns metadata for all supported language stacks."""
        active = self.resolve_active_stack()
        configured = self.get_configured_language()

        results = []
        for s_id, stack in SUPPORTED_STACKS.items():
            results.append({
                "id": stack.id,
                "name": stack.name,
                "extensions": stack.extensions,
                "test_cmd": stack.default_test_cmd,
                "build_cmd": stack.default_build_cmd,
                "lint_cmd": stack.default_lint_cmd,
                "is_active": (stack.id == active.id),
                "is_configured_default": (stack.id == configured)
            })
        return results
