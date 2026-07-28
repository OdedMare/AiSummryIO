"""Prompt text, kept as markdown beside the code that sends it.

    from app.bl import prompts
    system = prompts.load("tool_interview")

See [README.md](README.md) for what belongs here and what belongs in the
`agent_content` table instead.
"""

from app.bl.prompts._loader import clear_cache, load

__all__ = ["load", "clear_cache"]
