"""
Rich console singleton and shared UI helpers for the AeroSOuDA CLI.
"""
from __future__ import annotations

import sys
from typing import Any, Iterable, List, Optional, Tuple

import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

custom_style = Style([
    ("pointer", "bg:white fg:black bold"),
    ("highlighted", "bg:white fg:black bold"),
    ("selected", "bg:white fg:black bold"),
])

_printed_select_fallback_notice = False


def safe_select(prompt: str, choices: Iterable[Any]) -> Optional[Any]:
    """
    Ask a select question, with fallback for questionary/prompt_toolkit
    compatibility issues seen in some Python environments.
    """
    question_choices = list(choices)
    normalized: List[Tuple[str, Any]] = []
    for choice in question_choices:
        title = getattr(choice, "title", None)
        value = getattr(choice, "value", None)
        if title is not None:
            normalized.append((str(title), value))
        else:
            normalized.append((str(choice), choice))

    try:
        return questionary.select(
            prompt,
            choices=question_choices,
            style=custom_style,
            instruction="",
        ).ask()
    except AttributeError as exc:
        if "VSplit" not in str(exc):
            raise

        global _printed_select_fallback_notice
        if not _printed_select_fallback_notice:
            console.print(
                "[yellow]⚠ Interface interativa limitada neste ambiente; "
                "usando seleção por número.[/]"
            )
            _printed_select_fallback_notice = True

        for i, (title, _) in enumerate(normalized, start=1):
            console.print(f"  [cyan]{i}.[/] {title}")

        if not sys.stdin.isatty():
            return normalized[0][1]

        while True:
            raw = Prompt.ask(f"{prompt} [1-{len(normalized)}]", default="1").strip()
            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(normalized):
                    return normalized[idx - 1][1]
            console.print("[red]Opção inválida. Informe um número da lista.[/]")


def fatal(message: str) -> None:
    """Print a red error panel and exit with code 1."""
    console.print()
    console.print(Panel(message, title="[bold red]❌ Erro[/]", border_style="red"))
    sys.exit(1)
