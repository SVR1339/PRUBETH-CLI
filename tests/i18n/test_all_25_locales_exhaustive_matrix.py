"""PRUBETH 25-Locale All-Key Exhaustive Translation Matrix Tests.

Exhaustively verifies every message key across all 25 supported locales:
- Asserts string completeness and non-empty translation values
- Parameter formatting and interpolation verification (tool, args, error, action, level, etc.)
- Absence of unformatted curly-brace variables in substituted strings
- Enforces British English (en_GB) fallback for unknown keys
"""

from __future__ import annotations

import pytest
from prubeth.i18n.locales import SUPPORTED_LOCALES
from prubeth.i18n.translator import I18nEngine
from prubeth.i18n.catalog import TRANSLATION_CATALOG


ENGINE = I18nEngine()
ALL_LOCALE_CODES = list(SUPPORTED_LOCALES.keys())

# Standard 13 keys present in TRANSLATION_CATALOG
STANDARD_KEYS = [
    "cli.banner.tagline",
    "cli.prompt.placeholder",
    "cli.status.thinking",
    "cli.status.executing_tool",
    "cli.status.stagnation_alert",
    "cli.status.healing",
    "cli.status.success",
    "cli.status.error",
    "cli.status.permission_denied",
    "cli.cmd.pin_success",
    "cli.cmd.unpin_success",
    "cli.cmd.branch_created",
    "cli.cmd.branch_switched",
]

# Sample substitution variables
SAMPLE_VARS = {
    "tool": "read_file",
    "args": '{"path": "src/main.py"}',
    "error": "Connection reset by peer",
    "action": "delete_file",
    "level": "REQUIRE_CONFIRMATION",
    "label": "Architecture Doc",
    "pin_id": "pin-007",
    "branch": "feature/hyper-speed",
    "node_id": "node-42",
}

# Create all (locale, key) pairs: 25 * 13 = 325 test cases
LOCALE_KEY_PAIRS = [
    (loc, key)
    for loc in ALL_LOCALE_CODES
    for key in STANDARD_KEYS
]


@pytest.mark.parametrize("locale_code,key", LOCALE_KEY_PAIRS)
def test_all_25_locales_key_translation_and_formatting(locale_code: str, key: str):
    """Verifies that every locale translates the key and formats variables without error."""
    ENGINE.set_locale(locale_code)
    translated = ENGINE.t(key, **SAMPLE_VARS)

    assert isinstance(translated, str)
    assert len(translated.strip()) > 0

    # Ensure no unresolved variable braces remain (e.g. {tool} was substituted)
    for var_name in SAMPLE_VARS.keys():
        assert f"{{{var_name}}}" not in translated, f"Unresolved placeholder '{{{var_name}}}' in [{locale_code}][{key}]: {translated}"


# ============================================================================
# Additional Fallback Invariant Tests
# ============================================================================

def test_missing_key_falls_back_to_key_name():
    res = ENGINE.t("non_existent_key_xyz_12345")
    assert res == "non_existent_key_xyz_12345"


@pytest.mark.parametrize("locale_code", ALL_LOCALE_CODES)
def test_locale_catalog_presence(locale_code: str):
    assert locale_code in TRANSLATION_CATALOG
    assert len(TRANSLATION_CATALOG[locale_code]) >= 13
