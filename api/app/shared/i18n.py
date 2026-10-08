SUPPORTED_LANGUAGES = frozenset({"fr", "en"})


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
