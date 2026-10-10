from __future__ import annotations

from typing import TypeVar

SUPPORTED_LANGUAGES = frozenset({"fr", "en"})

T = TypeVar("T")


def resolve_language(
    *,
    query_lang: str | None,
    accept_language: str | None,
    default: str = "fr",
) -> str:
    if query_lang:
        code = query_lang.strip().lower()[:2]
        if code in SUPPORTED_LANGUAGES:
            return code

    if accept_language:
        # Ex. "fr-FR,fr;q=0.9,en;q=0.8" → premier code supporté
        for part in accept_language.split(","):
            code = part.strip().split(";")[0].strip().lower()[:2]
            if code in SUPPORTED_LANGUAGES:
                return code

    return default if default in SUPPORTED_LANGUAGES else "fr"


def pick_translation(
    items: list[T],
    lang: str,
    *,
    default: str = "fr",
    attr: str = "language_code",
) -> T | None:
    """Choisit la traduction `lang`, sinon `default`, sinon la première."""
    by_lang = {getattr(item, attr): item for item in items}
    if lang in by_lang:
        return by_lang[lang]
    if default in by_lang:
        return by_lang[default]
    return items[0] if items else None
