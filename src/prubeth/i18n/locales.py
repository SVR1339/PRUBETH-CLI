"""PRUBETH 25 Worldwide Developer Locales Specification.

Defines locale metadata, native names, script direction, and locale aliases.
British English (en_GB) is the foundational design invariant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class LocaleMetadata:
    code: str
    english_name: str
    native_name: str
    is_rtl: bool = False
    aliases: tuple[str, ...] = ()


SUPPORTED_LOCALES: Dict[str, LocaleMetadata] = {
    "en_GB": LocaleMetadata("en_GB", "English (UK)", "English (UK)", False, ("en", "en-GB", "en_UK", "default")),
    "en_US": LocaleMetadata("en_US", "English (US)", "English (US)", False, ("en-US", "en_USA")),
    "es_ES": LocaleMetadata("es_ES", "Spanish", "Español", False, ("es", "es-ES", "es_MX", "es_AR")),
    "fr_FR": LocaleMetadata("fr_FR", "French", "Français", False, ("fr", "fr-FR", "fr_CA")),
    "de_DE": LocaleMetadata("de_DE", "German", "Deutsch", False, ("de", "de-DE", "de_AT", "de_CH")),
    "ja_JP": LocaleMetadata("ja_JP", "Japanese", "日本語", False, ("ja", "ja-JP", "jp")),
    "zh_CN": LocaleMetadata("zh_CN", "Chinese (Simplified)", "简体中文", False, ("zh", "zh-CN", "zh_Hans")),
    "zh_TW": LocaleMetadata("zh_TW", "Chinese (Traditional)", "繁體中文", False, ("zh-TW", "zh_Hant", "zh_HK")),
    "ko_KR": LocaleMetadata("ko_KR", "Korean", "한국어", False, ("ko", "ko-KR", "kr")),
    "pt_BR": LocaleMetadata("pt_BR", "Portuguese (Brazil)", "Português (Brasil)", False, ("pt", "pt-BR", "pt_PT")),
    "ru_RU": LocaleMetadata("ru_RU", "Russian", "Русский", False, ("ru", "ru-RU")),
    "it_IT": LocaleMetadata("it_IT", "Italian", "Italiano", False, ("it", "it-IT")),
    "nl_NL": LocaleMetadata("nl_NL", "Dutch", "Nederlands", False, ("nl", "nl-NL", "nl_BE")),
    "pl_PL": LocaleMetadata("pl_PL", "Polish", "Polski", False, ("pl", "pl-PL")),
    "tr_TR": LocaleMetadata("tr_TR", "Turkish", "Türkçe", False, ("tr", "tr-TR")),
    "ar_SA": LocaleMetadata("ar_SA", "Arabic", "العربية", True, ("ar", "ar-SA", "ar_EG")),
    "hi_IN": LocaleMetadata("hi_IN", "Hindi", "हिन्दी", False, ("hi", "hi-IN")),
    "bn_BD": LocaleMetadata("bn_BD", "Bengali", "বাংলা", False, ("bn", "bn-BD", "bn_IN")),
    "sv_SE": LocaleMetadata("sv_SE", "Swedish", "Svenska", False, ("sv", "sv-SE")),
    "uk_UA": LocaleMetadata("uk_UA", "Ukrainian", "Українська", False, ("uk", "uk-UA")),
    "vi_VN": LocaleMetadata("vi_VN", "Vietnamese", "Tiếng Việt", False, ("vi", "vi-VN")),
    "id_ID": LocaleMetadata("id_ID", "Indonesian", "Bahasa Indonesia", False, ("id", "id-ID")),
    "el_GR": LocaleMetadata("el_GR", "Greek", "Ελληνικά", False, ("el", "el-GR")),
    "cs_CZ": LocaleMetadata("cs_CZ", "Czech", "Čeština", False, ("cs", "cs-CZ")),
    "he_IL": LocaleMetadata("he_IL", "Hebrew", "עברית", True, ("he", "he-IL", "iw", "iw_IL")),
}


def normalize_locale_code(raw: str) -> str:
    """Normalizes an arbitrary locale string (e.g. 'en_GB.UTF-8', 'es-es', 'FR') to canonical code."""
    if not raw:
        return "en_GB"

    clean = raw.split(".")[0].replace("-", "_").strip()
    if clean in SUPPORTED_LOCALES:
        return clean

    lower = clean.lower()
    for code, meta in SUPPORTED_LOCALES.items():
        if code.lower() == lower:
            return code
        for alias in meta.aliases:
            if alias.lower() == lower:
                return code

    # Match language prefix
    prefix = lower.split("_")[0]
    for code, meta in SUPPORTED_LOCALES.items():
        if code.lower().startswith(prefix):
            return code

    return "en_GB"
