"""PRUBETH 25-Language Polyglot Localization (i18n) Matrix Tests.

Exhaustively verifies translations, locale normalization, RTL detection,
and interpolation across all 25 supported developer languages.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from prubeth.i18n.locales import SUPPORTED_LOCALES, normalize_locale_code
from prubeth.i18n.catalog import TRANSLATION_CATALOG
from prubeth.i18n.translator import I18nEngine, t, set_locale, get_locale


CORE_KEYS = [
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


def test_supported_locales_count():
    # Exactly 25 supported developer locales
    assert len(SUPPORTED_LOCALES) == 25
    assert len(TRANSLATION_CATALOG) == 25


@pytest.mark.parametrize("loc_code", list(SUPPORTED_LOCALES.keys()))
def test_all_25_locales_have_core_keys(loc_code):
    catalog = TRANSLATION_CATALOG[loc_code]
    for key in CORE_KEYS:
        assert key in catalog, f"Locale '{loc_code}' missing translation key '{key}'"
        assert len(catalog[key].strip()) > 0, f"Locale '{loc_code}' has empty value for '{key}'"


@pytest.mark.parametrize("loc_code,expected_rtl", [
    ("en_GB", False),
    ("en_US", False),
    ("es_ES", False),
    ("fr_FR", False),
    ("de_DE", False),
    ("ja_JP", False),
    ("zh_CN", False),
    ("zh_TW", False),
    ("ko_KR", False),
    ("pt_BR", False),
    ("ru_RU", False),
    ("it_IT", False),
    ("nl_NL", False),
    ("pl_PL", False),
    ("tr_TR", False),
    ("ar_SA", True),   # Arabic is RTL
    ("hi_IN", False),
    ("bn_BD", False),
    ("sv_SE", False),
    ("uk_UA", False),
    ("vi_VN", False),
    ("id_ID", False),
    ("el_GR", False),
    ("cs_CZ", False),
    ("he_IL", True),   # Hebrew is RTL
])
def test_locale_script_direction_matrix(loc_code, expected_rtl):
    meta = SUPPORTED_LOCALES[loc_code]
    assert meta.is_rtl == expected_rtl

    engine = I18nEngine(default_locale="en_GB")
    engine.set_locale(loc_code)
    assert engine.is_rtl() == expected_rtl


@pytest.mark.parametrize("raw_input,expected_code", [
    ("en", "en_GB"),
    ("en-GB", "en_GB"),
    ("en_GB.UTF-8", "en_GB"),
    ("en_US", "en_US"),
    ("es", "es_ES"),
    ("es-ES", "es_ES"),
    ("fr", "fr_FR"),
    ("de", "de_DE"),
    ("ja", "ja_JP"),
    ("zh", "zh_CN"),
    ("zh_Hans", "zh_CN"),
    ("zh-TW", "zh_TW"),
    ("ko", "ko_KR"),
    ("pt-BR", "pt_BR"),
    ("ru", "ru_RU"),
    ("it", "it_IT"),
    ("nl", "nl_NL"),
    ("pl", "pl_PL"),
    ("tr", "tr_TR"),
    ("ar", "ar_SA"),
    ("hi", "hi_IN"),
    ("bn", "bn_BD"),
    ("sv", "sv_SE"),
    ("uk", "uk_UA"),
    ("vi", "vi_VN"),
    ("id", "id_ID"),
    ("el", "el_GR"),
    ("cs", "cs_CZ"),
    ("he", "he_IL"),
    ("iw_IL", "he_IL"),
    ("unknown_xyz", "en_GB"),  # Unknown defaults to en_GB
    ("", "en_GB"),
])
def test_locale_code_normalization_matrix(raw_input, expected_code):
    assert normalize_locale_code(raw_input) == expected_code


def test_translation_parameter_interpolation():
    engine = I18nEngine(default_locale="en_GB")
    engine.set_locale("en_GB")

    # Interpolate tool and args
    msg = engine.t("cli.status.executing_tool", tool="read_file", args='{"path": "core.py"}')
    assert "Executing tool 'read_file'" in msg
    assert '{"path": "core.py"}' in msg

    # Interpolate in Spanish
    engine.set_locale("es_ES")
    msg_es = engine.t("cli.status.executing_tool", tool="read_file", args='{"path": "core.py"}')
    assert "Ejecutando herramienta 'read_file'" in msg_es

    # Interpolate in Japanese
    engine.set_locale("ja_JP")
    msg_ja = engine.t("cli.status.executing_tool", tool="read_file", args='{"path": "core.py"}')
    assert "ツール 'read_file' をパラメータで実行中" in msg_ja


def test_missing_key_fallback_to_default_locale():
    engine = I18nEngine(default_locale="en_GB")
    engine.set_locale("ja_JP")

    # Completely unknown key returns key itself
    assert engine.t("completely.nonexistent.key") == "completely.nonexistent.key"


def test_env_var_locale_auto_detection():
    with patch.dict(os.environ, {"PRUBETH_LANG": "fr_FR"}):
        engine = I18nEngine()
        assert engine.get_current_locale() == "fr_FR"
        assert "Environnement d'Exécution" in engine.t("cli.banner.tagline")

    with patch.dict(os.environ, {"PRUBETH_LANG": "", "LANG": "de_DE.UTF-8"}):
        engine = I18nEngine()
        assert engine.get_current_locale() == "de_DE"
        assert "Entwickler-CLI" in engine.t("cli.banner.tagline")
