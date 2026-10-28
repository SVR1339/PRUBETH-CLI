"""PRUBETH Configuration Settings & Schema Exhaustive Matrix.

Exhaustively verifies SETTING_REGISTRY typing, range bounds, choice enums,
boolean representations, MODEL_ALIASES resolution, PROFILES presets,
and ConfigManager mutation/reset lifecycles.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from prubeth.config.schema import (
    SETTING_REGISTRY,
    SettingDefinition,
    validate_setting_value,
    CAT_PERFORMANCE,
    CAT_COGNITIVE,
    CAT_RESILIENCE,
    CAT_SECURITY,
    CAT_DEV_EXP,
)
from prubeth.config.manager import ConfigManager, MODEL_ALIASES, PROFILES


# ============================================================================
# 1. SETTING_REGISTRY Structural Invariants Matrix
# ============================================================================

ALL_SETTING_KEYS = list(SETTING_REGISTRY.keys())
ALLOWED_CATEGORIES = {CAT_PERFORMANCE, CAT_COGNITIVE, CAT_RESILIENCE, CAT_SECURITY, CAT_DEV_EXP}


@pytest.mark.parametrize("key", ALL_SETTING_KEYS)
def test_setting_definition_integrity(key: str):
    defn: SettingDefinition = SETTING_REGISTRY[key]
    assert defn.key == key
    assert defn.category in ALLOWED_CATEGORIES, f"Setting '{key}' has unknown category '{defn.category}'"
    assert defn.label and len(defn.label) > 2
    assert defn.value_type in {"bool", "int", "str", "choice"}
    assert defn.description and len(defn.description) > 10
    assert defn.impact and len(defn.impact) > 5
    assert defn.recommendation and len(defn.recommendation) > 5


@pytest.mark.parametrize("key", ALL_SETTING_KEYS)
def test_setting_default_value_matches_type(key: str):
    defn = SETTING_REGISTRY[key]
    if defn.value_type == "bool":
        assert isinstance(defn.default, bool)
    elif defn.value_type == "int":
        assert isinstance(defn.default, int)
        if defn.range_bounds:
            min_b, max_b = defn.range_bounds
            assert min_b <= defn.default <= max_b
    elif defn.value_type == "choice":
        assert isinstance(defn.default, str)
        assert defn.choices is not None
        assert defn.default in defn.choices
    elif defn.value_type == "str":
        assert isinstance(defn.default, str)


# ============================================================================
# 2. Boolean Settings Validation Permutations
# ============================================================================

BOOL_KEYS = [k for k, v in SETTING_REGISTRY.items() if v.value_type == "bool"]


@pytest.mark.parametrize("key", BOOL_KEYS)
@pytest.mark.parametrize("truthy_input", [True, "true", "True", "1", "yes", "YES", "on", "ON", "enable", "enabled"])
def test_boolean_settings_truthy_values(key: str, truthy_input):
    ok, val, err = validate_setting_value(key, truthy_input)
    assert ok is True, f"Failed for key '{key}' on truthy input '{truthy_input}'"
    assert val is True
    assert err == ""


@pytest.mark.parametrize("key", BOOL_KEYS)
@pytest.mark.parametrize("falsy_input", [False, "false", "False", "0", "no", "NO", "off", "OFF", "disable", "disabled"])
def test_boolean_settings_falsy_values(key: str, falsy_input):
    ok, val, err = validate_setting_value(key, falsy_input)
    assert ok is True, f"Failed for key '{key}' on falsy input '{falsy_input}'"
    assert val is False
    assert err == ""


@pytest.mark.parametrize("key", BOOL_KEYS)
@pytest.mark.parametrize("invalid_bool", ["maybe", "uncertain", "2", "-1", "none", "null", [True], {"k": "v"}])
def test_boolean_settings_invalid_values(key: str, invalid_bool):
    ok, val, err = validate_setting_value(key, invalid_bool)
    assert ok is False
    assert val is None
    assert "expects a boolean" in err


# ============================================================================
# 3. Integer Settings Range Bounds Permutations
# ============================================================================

INT_KEYS = [k for k, v in SETTING_REGISTRY.items() if v.value_type == "int" and v.range_bounds is not None]


@pytest.mark.parametrize("key", INT_KEYS)
def test_integer_settings_valid_range_bounds(key: str):
    defn = SETTING_REGISTRY[key]
    min_b, max_b = defn.range_bounds  # type: ignore

    # Test lower bound
    ok_min, val_min, _ = validate_setting_value(key, min_b)
    assert ok_min and val_min == min_b

    # Test string representation of lower bound
    ok_min_s, val_min_s, _ = validate_setting_value(key, str(min_b))
    assert ok_min_s and val_min_s == min_b

    # Test upper bound
    ok_max, val_max, _ = validate_setting_value(key, max_b)
    assert ok_max and val_max == max_b

    # Test mid point
    mid = (min_b + max_b) // 2
    ok_mid, val_mid, _ = validate_setting_value(key, mid)
    assert ok_mid and val_mid == mid


@pytest.mark.parametrize("key", INT_KEYS)
def test_integer_settings_out_of_bounds_rejection(key: str):
    defn = SETTING_REGISTRY[key]
    min_b, max_b = defn.range_bounds  # type: ignore

    # Below lower bound
    ok_low, _, err_low = validate_setting_value(key, min_b - 1)
    assert ok_low is False
    assert f"must be between {min_b} and {max_b}" in err_low

    # Above upper bound
    ok_high, _, err_high = validate_setting_value(key, max_b + 1)
    assert ok_high is False
    assert f"must be between {min_b} and {max_b}" in err_high


@pytest.mark.parametrize("key", INT_KEYS)
@pytest.mark.parametrize("non_int", ["not_a_number", "12.34abc", None, [10]])
def test_integer_settings_invalid_type_rejection(key: str, non_int):
    ok, val, err = validate_setting_value(key, non_int)
    assert ok is False
    assert "expects an integer" in err


# ============================================================================
# 4. Choice Settings Permutations
# ============================================================================

CHOICE_KEYS = [k for k, v in SETTING_REGISTRY.items() if v.value_type == "choice" and v.choices is not None]


@pytest.mark.parametrize("key", CHOICE_KEYS)
def test_choice_settings_valid_options(key: str):
    defn = SETTING_REGISTRY[key]
    for ch in defn.choices:  # type: ignore
        ok, val, err = validate_setting_value(key, ch)
        assert ok is True
        assert val == ch.lower()
        assert err == ""


@pytest.mark.parametrize("key", CHOICE_KEYS)
def test_choice_settings_invalid_option_rejection(key: str):
    defn = SETTING_REGISTRY[key]
    ok, val, err = validate_setting_value(key, "invalid_choice_999")
    assert ok is False
    assert val is None
    assert "must be one of" in err


# ============================================================================
# 5. Unknown Settings Handling
# ============================================================================

@pytest.mark.parametrize("unknown_key", [
    "nonexistent_setting",
    "cloud_super_admin_pass",
    "enable_telepathy",
    "enterprise_sso_gateway"
])
def test_unknown_setting_rejection(unknown_key: str):
    ok, val, err = validate_setting_value(unknown_key, True)
    assert ok is False
    assert val is None
    assert f"Unknown setting '{unknown_key}'" in err


# ============================================================================
# 6. MODEL_ALIASES Resolution Matrix
# ============================================================================

@pytest.mark.parametrize("alias,expected_target", [
    ("2.5", "gemini-2.5-pro"),
    ("2.5-pro", "gemini-2.5-pro"),
    ("gemini-2.5-flash", "gemini-2.5-flash"),
    ("claude-3.7", "claude-3-7-sonnet-20250219"),
    ("sonnet", "claude-3-7-sonnet-20250219"),
    ("claude-3.5", "claude-3-5-sonnet-20241022"),
    ("o3", "o3-mini"),
    ("gpt-4o", "gpt-4o"),
    ("r1", "deepseek/deepseek-r1:free"),
    ("deepseek-v3", "deepseek-v3"),
    ("local", "qwen2.5-coder:7b"),
    ("ollama", "qwen2.5-coder:7b"),
    ("lmstudio", "local-model"),
])
def test_model_alias_resolution(alias: str, expected_target: str):
    assert alias in MODEL_ALIASES
    assert MODEL_ALIASES[alias] == expected_target


# ============================================================================
# 7. PROFILES Presets Matrix
# ============================================================================

@pytest.mark.parametrize("profile_id", ["builder", "deep-reasoning", "local-airgap", "safe-audit"])
def test_profile_presets_validity(profile_id: str):
    assert profile_id in PROFILES
    profile = PROFILES[profile_id]
    assert "name" in profile
    assert "badge" in profile
    assert "desc" in profile
    assert "settings" in profile

    # Verify every setting specified in the profile is valid according to schema
    for s_key, s_val in profile["settings"].items():
        if s_key in SETTING_REGISTRY:
            ok, coerced, err = validate_setting_value(s_key, s_val)
            assert ok is True, f"Profile '{profile_id}' setting '{s_key}' failed validation: {err}"


# ============================================================================
# 8. ConfigManager Lifecycle Matrix
# ============================================================================

def test_config_manager_set_and_reset_setting(tmp_path: Path):
    cfg_mgr = ConfigManager(config_dir=tmp_path / "cfg")
    
    # 1. Inspect setting
    meta = cfg_mgr.inspect_setting("enable_prompt_caching")
    assert meta is not None
    assert meta["key"] == "enable_prompt_caching"

    # 2. Modify a boolean setting with toggle
    orig = cfg_mgr.get("enable_prompt_caching")
    toggled = cfg_mgr.toggle("enable_prompt_caching")
    assert toggled != orig
    assert cfg_mgr.get("enable_prompt_caching") == toggled

    # 3. Modify an int setting with validation
    cfg_mgr.set("watchdog_timeout_s", 60)
    assert cfg_mgr.get("watchdog_timeout_s") == 60

    # 4. Out-of-bounds int rejection via set
    with pytest.raises(ValueError):
        cfg_mgr.set("watchdog_timeout_s", 999999)

    # 5. Apply a profile
    applied = cfg_mgr.apply_profile("builder")
    assert applied["settings"]["developer_mode"] is True
    assert cfg_mgr.get("developer_mode") is True
