"""PRUBETH Polyglot Internationalization (i18n) Subsystem."""

from prubeth.i18n.locales import SUPPORTED_LOCALES, LocaleMetadata, normalize_locale_code
from prubeth.i18n.catalog import TRANSLATION_CATALOG
from prubeth.i18n.translator import I18nEngine, t, set_locale, get_locale

__all__ = [
    "SUPPORTED_LOCALES",
    "LocaleMetadata",
    "normalize_locale_code",
    "TRANSLATION_CATALOG",
    "I18nEngine",
    "t",
    "set_locale",
    "get_locale",
]
