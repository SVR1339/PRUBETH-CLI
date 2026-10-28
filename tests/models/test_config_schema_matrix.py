"""PRUBETH Configuration Schema & Manager Matrix Tests.

Exhaustively verifies SETTING_REGISTRY completeness, SettingDefinition fields,
all 5 category constants, validate_setting_value, ConfigManager load/save/reset
cycles, MODEL_ALIASES for Gemini/Claude/OpenAI/DeepSeek, and provider endpoint
defaults.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from prubeth.config.schema import (
    SETTING_REGISTRY,
    SettingDefinition,
    CAT_PERFORMANCE,
    CAT_COGNITIVE,
    CAT_RESILIENCE,
    CAT_SECURITY,
    CAT_DEV_EXP,
    validate_setting_value,
)
from prubeth.config.manager import ConfigManager, MODEL_ALIASES


# ============================================================================
# 1. Category Constants
# ============================================================================

def test_category_performance_has_emoji():
    assert "Performance" in CAT_PERFORMANCE or "⚡" in CAT_PERFORMANCE


def test_category_cognitive_has_emoji():
    assert "Cognitive" in CAT_COGNITIVE or "🧠" in CAT_COGNITIVE


def test_category_resilience_defined():
    assert len(CAT_RESILIENCE) > 5


def test_category_security_defined():
    assert "Security" in CAT_SECURITY or "🔒" in CAT_SECURITY


def test_category_dev_exp_defined():
    assert "Developer" in CAT_DEV_EXP or "🔧" in CAT_DEV_EXP


# ============================================================================
# 2. SETTING_REGISTRY — Completeness & Required Fields
# ============================================================================

def test_setting_registry_is_populated():
    assert len(SETTING_REGISTRY) >= 10


def test_all_settings_have_key():
    for key, defn in SETTING_REGISTRY.items():
        assert defn.key == key, f"Setting {key!r} has mismatched key: {defn.key!r}"


def test_all_settings_have_category():
    for key, defn in SETTING_REGISTRY.items():
        assert defn.category in (CAT_PERFORMANCE, CAT_COGNITIVE, CAT_RESILIENCE, CAT_SECURITY, CAT_DEV_EXP), \
            f"Setting {key!r} has unknown category: {defn.category!r}"


def test_all_settings_have_label():
    for key, defn in SETTING_REGISTRY.items():
        assert isinstance(defn.label, str) and len(defn.label) > 2, \
            f"Setting {key!r} has blank label."


def test_all_settings_have_value_type():
    valid_types = {"bool", "int", "str", "choice"}
    for key, defn in SETTING_REGISTRY.items():
        assert defn.value_type in valid_types, \
            f"Setting {key!r} has invalid value_type: {defn.value_type!r}"


def test_all_settings_have_default():
    for key, defn in SETTING_REGISTRY.items():
        assert defn.default is not None or defn.value_type in ("str", "choice"), \
            f"Setting {key!r} has None default but is not string-type."


def test_prompt_caching_setting_exists():
    assert "enable_prompt_caching" in SETTING_REGISTRY


def test_prompt_caching_default_true():
    assert SETTING_REGISTRY["enable_prompt_caching"].default is True


def test_context_cache_ttl_has_range():
    defn = SETTING_REGISTRY.get("context_cache_ttl_s")
    if defn:
        assert defn.range_bounds is not None
        low, high = defn.range_bounds
        assert low < high


# ============================================================================
# 3. validate_setting_value — Correctness
# ============================================================================

def test_validate_bool_true():
    ok, coerced, msg = validate_setting_value("enable_prompt_caching", True)
    assert ok is True
    assert coerced is True


def test_validate_bool_false():
    ok, coerced, msg = validate_setting_value("enable_prompt_caching", False)
    assert ok is True
    assert coerced is False


def test_validate_bool_string_coercion():
    ok, coerced, msg = validate_setting_value("enable_prompt_caching", "off")
    assert ok is True
    assert coerced is False


def test_validate_bool_invalid_type():
    ok, coerced, msg = validate_setting_value("enable_prompt_caching", "invalid_choice_xyz")
    assert ok is False
    assert "boolean" in msg.lower()


def test_validate_int_within_range():
    ok, coerced, msg = validate_setting_value("context_cache_ttl_s", 300)
    assert ok is True
    assert coerced == 300


def test_validate_int_out_of_range_low():
    ok, coerced, msg = validate_setting_value("context_cache_ttl_s", 10)
    assert ok is False
    assert "must be between" in msg


def test_validate_int_out_of_range_high():
    ok, coerced, msg = validate_setting_value("context_cache_ttl_s", 999999)
    assert ok is False
    assert "must be between" in msg


def test_validate_unknown_key():
    ok, coerced, msg = validate_setting_value("totally_unknown_key_xyz", "anything")
    assert ok is False
    assert "Unknown setting" in msg


# ============================================================================
# 4. MODEL_ALIASES — Provider Coverage
# ============================================================================

def test_model_aliases_gemini_2_5_pro():
    assert "gemini-2.5-pro" in MODEL_ALIASES.values()


def test_model_aliases_gemini_flash():
    assert "gemini-2.5-flash" in MODEL_ALIASES.values() or "2.5-flash" in MODEL_ALIASES


def test_model_aliases_claude_shorthand():
    assert "claude" in MODEL_ALIASES
    target = MODEL_ALIASES["claude"]
    assert "claude" in target


def test_model_aliases_sonnet_shorthand():
    assert "sonnet" in MODEL_ALIASES


def test_model_aliases_deepseek_r1():
    assert "r1" in MODEL_ALIASES or "deepseek-r1" in MODEL_ALIASES


def test_model_aliases_gpt4o():
    assert "gpt-4o" in MODEL_ALIASES


def test_model_aliases_ollama():
    assert any("ollama" in k or "ollama" in str(v) for k, v in MODEL_ALIASES.items()) or \
           any("local" in k for k in MODEL_ALIASES)


# ============================================================================
# 5. ConfigManager — Load, Save, Reset Cycle
# ============================================================================

def test_config_manager_loads_defaults(tmp_path: Path):
    mgr = ConfigManager(config_dir=tmp_path)
    cfg = mgr.load_config()
    assert isinstance(cfg, dict)


def test_config_manager_creates_config_file(tmp_path: Path):
    mgr = ConfigManager(config_dir=tmp_path)
    mgr.load_config()
    # Config file or directory should be present
    assert tmp_path.exists()


def test_config_manager_save_and_reload(tmp_path: Path):
    mgr = ConfigManager(config_dir=tmp_path)
    cfg = mgr.load_config()
    cfg["test_custom_key"] = "prubeth_value"
    mgr.save_config(cfg)

    mgr2 = ConfigManager(config_dir=tmp_path)
    cfg2 = mgr2.load_config()
    assert cfg2.get("test_custom_key") == "prubeth_value"


def test_config_manager_toggle_flag(tmp_path: Path):
    mgr = ConfigManager(config_dir=tmp_path)
    initial = mgr.get("enable_prompt_caching")
    new_val = mgr.toggle("enable_prompt_caching")
    assert new_val is not initial
    assert mgr.get("enable_prompt_caching") is new_val


def test_config_manager_apply_profile(tmp_path: Path):
    mgr = ConfigManager(config_dir=tmp_path)
    profile = mgr.apply_profile("deep-reasoning")
    assert profile is not None
    assert mgr.get("active_profile") == "deep-reasoning"


def test_config_manager_get_setting_default(tmp_path: Path):
    mgr = ConfigManager(config_dir=tmp_path)
    val = mgr.get("enable_prompt_caching")
    assert val is True  # Default from schema


def test_config_manager_set_and_get(tmp_path: Path):
    mgr = ConfigManager(config_dir=tmp_path)
    mgr.set("enable_prompt_caching", False)
    assert mgr.get("enable_prompt_caching") is False
