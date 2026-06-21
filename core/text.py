"""Text sanitization for values headed into Postgres.

PostgreSQL text/varchar/json columns reject the NUL byte (0x00). LLMs occasionally
emit a NUL (e.g. where an em-dash should be), which crashes the INSERT with
asyncpg.exceptions.CharacterNotInRepertoireError. Strip NULs from any LLM-authored
text before persisting.
"""


def clean_text(value):
    """Recursively remove NUL bytes from strings, dicts, and lists."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {k: clean_text(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_text(v) for v in value]
    return value
