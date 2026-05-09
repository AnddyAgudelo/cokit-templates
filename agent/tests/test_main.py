"""Tests for main.py agent build logic."""
from datetime import date

from src.system_prompt import SYSTEM_PROMPT


def test_system_prompt_contains_today_placeholder() -> None:
    """SYSTEM_PROMPT source must contain the {TODAY} placeholder so substitution works."""
    assert "{TODAY}" in SYSTEM_PROMPT, (
        "SYSTEM_PROMPT must contain the literal string {TODAY} "
        "so _build_agent can replace it with the real date."
    )


def test_today_substitution_replaces_placeholder() -> None:
    """The substitution logic used in _build_agent correctly replaces {TODAY}."""
    today_str = date.today().isoformat()

    # Replicate exactly what _build_agent does
    rendered = SYSTEM_PROMPT.replace("{TODAY}", today_str)

    assert today_str in rendered, (
        f"Expected today's date {today_str!r} in rendered system prompt, "
        f"but it was not found."
    )
    assert "{TODAY}" not in rendered, (
        "The literal placeholder {TODAY} should have been replaced, "
        "but it was still present in the rendered prompt."
    )
    # Spot-check: the current-date section appears in the rendered prompt
    assert "TODAY is " in rendered, (
        "Expected 'TODAY is ' narrative text in rendered prompt."
    )
