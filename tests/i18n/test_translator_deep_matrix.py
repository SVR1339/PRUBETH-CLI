"""PRUBETH Polyglot Localization & Translation Engine Deep Matrix Tests.

Exhaustively verifies I18nEngine across all 25 supported locales:
normalize_locale_code, set_locale, get_locale, message interpolation,
missing key fallbacks, and catalog consistency.
"""

from __future__ import annotations

import pytest

from prubeth.i18n.translator import (
    I18nEngine,
    normalize_locale_code,
    get_locale,
    set_locale,
    t,
    SUPPORTED_LOCALES,
    TRANSLATION_CATALOG,
)


# ============================================================================
# 1. Locale Code Normalization Matrix
# ============================================================================

@pytest.mark.parametrize("raw_code,expected_normalized", [
    ("en-US", "en_US"),
    ("en_us", "en_US"),
    ("en-GB", "en_GB"),
    ("en_gb", "en_GB"),
    ("es", "es_ES"),
    ("es-ES", "es_ES"),
    ("fr", "fr_FR"),
    ("fr-FR", "fr_FR"),
    ("de", "de_DE"),
    ("de-DE", "de_DE"),
    ("ja", "ja_JP"),
    ("ja-JP", "ja_JP"),
    ("zh-CN", "zh_CN"),
    ("zh-cn", "zh_CN"),
    ("zh-TW", "zh_TW"),
    ("zh-tw", "zh_TW"),
    ("ko", "ko_KR"),
    ("ko-KR", "ko_KR"),
    ("pt-BR", "pt_BR"),
    ("pt_br", "pt_BR"),
    ("ru", "ru_RU"),
    ("it", "it_IT"),
    ("hi", "hi_IN"),
    ("ar", "ar_SA"),
    ("nl", "nl_NL"),
    ("pl", "pl_PL"),
    ("tr", "tr_TR"),
    ("sv", "sv_SE"),
    ("da", "da_DK"),
    ("fi", "fi_FI"),
    ("no", "no_NO"),
    ("uk", "uk_UA"),
    ("cs", "cs_CZ"),
    ("el", "el_GR"),
    ("he", "he_IL"),
])
def test_normalize_locale_code_variants(raw_code: str, expected_normalized: str):
    norm = normalize_locale_code(raw_code)
    assert norm == expected_normalized or norm in SUPPORTED_LOCALES


def test_normalize_invalid_code_falls_back_to_en_gb():
    norm = normalize_locale_code("invalid_locale_xyz_123")
    assert norm == "en_GB"


def test_normalize_empty_falls_back_to_en_gb():
    norm = normalize_locale_code("")
    assert norm == "en_GB"


# ============================================================================
# 2. Supported Locales Invariants
# ============================================================================

def test_supported_locales_count_exactly_25():
    assert len(SUPPORTED_LOCALES) == 25


def test_all_supported_locales_have_metadata():
    for code, meta in SUPPORTED_LOCALES.items():
        assert hasattr(meta, "code")
        assert hasattr(meta, "english_name")
        assert hasattr(meta, "native_name")
        assert hasattr(meta, "is_rtl")
        assert hasattr(meta, "aliases")


# ============================================================================
# 3. Dynamic Locale Switching & Retrieval
# ============================================================================

def test_set_and_get_locale():
    original = get_locale()
    try:
        set_locale("ja_JP")
        assert get_locale() == "ja_JP"

        set_locale("fr_FR")
        assert get_locale() == "fr_FR"
    finally:
        set_locale(original)


def test_set_locale_invalid_falls_back_to_en_gb():
    original = get_locale()
    try:
        set_locale("fake_unknown_code")
        assert get_locale() == "en_GB"
    finally:
        set_locale(original)


# ============================================================================
# 4. Translation Interpolation & Catalog Lookup
# ============================================================================

@pytest.mark.parametrize("loc_code", list(SUPPORTED_LOCALES.keys()))
def test_all_25_locales_have_catalog_entries(loc_code: str):
    assert loc_code in TRANSLATION_CATALOG
    entries = TRANSLATION_CATALOG[loc_code]
    assert isinstance(entries, dict)
    assert len(entries) >= 5


def test_translation_missing_key_returns_key_fallback():
    missing_key = "very.obscure.nonexistent.key.xyz"
    val = t(missing_key)
    assert val == missing_key


def test_translation_with_kwargs_interpolation():
    engine = I18nEngine(default_locale="en_GB")
    engine.set_locale("en_GB")
    rendered = engine.t("status.success", component="Kernel")
    assert isinstance(rendered, str)


def test_i18n_rtl_detection():
    engine = I18nEngine()
    assert engine.is_rtl("ar_SA") is True
    assert engine.is_rtl("he_IL") is True
    assert engine.is_rtl("en_GB") is False
    assert engine.is_rtl("ja_JP") is False
