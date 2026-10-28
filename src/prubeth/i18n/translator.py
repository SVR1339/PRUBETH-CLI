"""PRUBETH Internationalization (i18n) Translator Engine.

Provides zero-overhead localization across 25 developer languages.
Auto-detects host system locale, handles variable interpolations,
and defaults strictly to British English (en_GB) for missing keys.
"""

from __future__ import annotations

import locale
import os
import sys
from typing import Dict, Any, Optional

from prubeth.i18n.locales import SUPPORTED_LOCALES, LocaleMetadata, normalize_locale_code
from prubeth.i18n.catalog import TRANSLATION_CATALOG


class I18nEngine:
    """Manages active locale, message translation lookups, and parameter substitution."""

    def __init__(self, default_locale: str = "en_GB"):
        self.default_locale = default_locale
        self.active_locale = self.detect_system_locale()

    def detect_system_locale(self) -> str:
        """Determines the appropriate locale from environment variables or OS runtime."""
        # 1. PRUBETH explicit override
        env_pref = os.environ.get("PRUBETH_LANG")
        if env_pref:
            return normalize_locale_code(env_pref)

        # 2. Standard POSIX environment variables
        for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
            val = os.environ.get(var)
            if val:
                return normalize_locale_code(val)

        # 3. Python standard locale detection
        try:
            loc_tuple = locale.getlocale()
            if loc_tuple and loc_tuple[0]:
                return normalize_locale_code(loc_tuple[0])
        except Exception:
            pass

        # 4. Windows API fallback if on NT
        if sys.platform == "win32":
            try:
                import ctypes
                lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
                # Common Windows LANGIDs
                lang_id_map = {
                    0x0809: "en_GB",
                    0x0409: "en_US",
                    0x0C0A: "es_ES",
                    0x040C: "fr_FR",
                    0x0407: "de_DE",
                    0x0411: "ja_JP",
                    0x0804: "zh_CN",
                    0x0404: "zh_TW",
                    0x0412: "ko_KR",
                    0x0416: "pt_BR",
                    0x0419: "ru_RU",
                    0x0410: "it_IT",
                    0x0413: "nl_NL",
                    0x0415: "pl_PL",
                    0x041F: "tr_TR",
                    0x0401: "ar_SA",
                    0x0439: "hi_IN",
                    0x0445: "bn_BD",
                    0x041D: "sv_SE",
                    0x0422: "uk_UA",
                    0x042A: "vi_VN",
                    0x0421: "id_ID",
                    0x0408: "el_GR",
                    0x0405: "cs_CZ",
                    0x040D: "he_IL",
                }
                if lang_id in lang_id_map:
                    return lang_id_map[lang_id]
            except Exception:
                pass

        return self.default_locale

    def set_locale(self, locale_code: str) -> str:
        """Sets the active translation locale."""
        canonical = normalize_locale_code(locale_code)
        self.active_locale = canonical
        return canonical

    def get_current_locale(self) -> str:
        """Returns the canonical code of the currently active locale."""
        return self.active_locale

    def get_metadata(self, locale_code: Optional[str] = None) -> LocaleMetadata:
        """Retrieves metadata for specified or active locale."""
        code = locale_code or self.active_locale
        return SUPPORTED_LOCALES.get(code, SUPPORTED_LOCALES[self.default_locale])

    def is_rtl(self, locale_code: Optional[str] = None) -> bool:
        """Returns True if the locale uses Right-to-Left script (e.g. Arabic, Hebrew)."""
        return self.get_metadata(locale_code).is_rtl

    def t(self, key: str, **kwargs: Any) -> str:
        """Translates a message key into the active locale with parameter substitution."""
        # Check active locale catalog
        template = TRANSLATION_CATALOG.get(self.active_locale, {}).get(key)

        # Fallback to default locale (en_GB) if missing
        if template is None:
            template = TRANSLATION_CATALOG.get(self.default_locale, {}).get(key)

        # If key is completely absent from all catalogs, return key itself
        if template is None:
            return key

        if kwargs:
            try:
                return template.format(**kwargs)
            except KeyError:
                # Return unformatted if keys mismatch
                return template

        return template


# Global singleton instance
_engine = I18nEngine()

def t(key: str, **kwargs: Any) -> str:
    """Convenience translation function."""
    return _engine.t(key, **kwargs)

def set_locale(code: str) -> str:
    """Convenience locale setter."""
    return _engine.set_locale(code)

def get_locale() -> str:
    """Convenience locale getter."""
    return _engine.get_current_locale()
