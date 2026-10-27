"""Minimal-i18n: API liefert immer stabile Codes + lokalisierte Texte.
Neue Sprache = neue JSON-Datei mit denselben Keys."""
import json
from functools import lru_cache
from pathlib import Path

DEFAULT_LOCALE = "de"
_DIR = Path(__file__).parent


@lru_cache
def _catalog(locale: str) -> dict:
    path = _DIR / f"{locale}.json"
    if not path.exists():
        path = _DIR / f"{DEFAULT_LOCALE}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def available_locales() -> list[str]:
    return sorted(p.stem for p in _DIR.glob("*.json"))


def resolve_locale(accept_language: str | None) -> str:
    if accept_language:
        for part in accept_language.split(","):
            code = part.split(";")[0].strip()[:2].lower()
            if code in available_locales():
                return code
    return DEFAULT_LOCALE


def t(key: str, locale: str = DEFAULT_LOCALE, **params) -> str:
    node: object = _catalog(locale)
    for part in key.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    if not isinstance(node, str):
        return key
    try:
        return node.format(**params)
    except (KeyError, IndexError):
        return node


def labels(group: str, locale: str = DEFAULT_LOCALE) -> dict[str, str]:
    return _catalog(locale)["labels"][group]
