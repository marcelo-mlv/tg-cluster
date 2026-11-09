"""
YAML scenario selection and creation wizard (client-side, no Docker dependency).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import questionary
import yaml
from rich.panel import Panel
from rich.table import Table

from .config import SCENARIOS_DIR
from .console import console, fatal, safe_select


def _preview_yaml(data: Dict[str, Any]) -> None:
    x = data.get("x_variable", {})
    y = data.get("y_variable", {})
    agg = data.get("batch_aggregation", {})
    table = Table(title=f"Cenário: {data.get('name', '?')}", border_style="dim")
    table.add_column("Campo", style="cyan", no_wrap=True)
    table.add_column("Valor")
    for lbl, val in [
        ("Variável X (independente)", x.get("name","?")),
        ("  Seletor de entidade X",   str(x.get("entity_selector",{}))),
        ("  Caminho de campo X",      x.get("field_path","?")),
        ("  Agregação por frame X",   x.get("frame_aggregation","?")),
        ("  Escopo X",                x.get("scope","?")),
        ("Variável Y (métrica)",      y.get("name","?")),
        ("  Seletor de entidade Y",   str(y.get("entity_selector",{}))),
        ("  Caminho de campo Y",      y.get("field_path","?")),
        ("  Agregação por frame Y",   y.get("frame_aggregation","?")),
        ("  Escopo Y",                y.get("scope","?")),
        ("Agregação do lote",         agg.get("type","?")),
    ]:
        table.add_row(lbl, str(val) if val is not None else "[dim]—[/]")
    console.print(); console.print(table); console.print()


def pick_scenario() -> Tuple[Path, Dict[str, Any]]:
    """
    Let the analyst choose a bundled YAML scenario or provide a custom path.
    Returns (yaml_path, yaml_dict).
    """
    console.print(Panel(
        "[bold]Configuração do cenário[/]\n\n"
        "Selecione um cenário de exemplo ou carregue um arquivo YAML local.",
        border_style="blue",
    ))
    bundled = sorted(SCENARIOS_DIR.glob("*.yaml")) + sorted(SCENARIOS_DIR.glob("*.yml"))
    choices = []
    for p in bundled:
        try:
            with open(p, encoding="utf-8") as fh:
                data: Dict[str,Any] = yaml.safe_load(fh) or {}
            label = f"{p.name}  — {data.get('name', p.stem)}"
        except Exception:
            data = {}
            label = p.name
        choices.append(questionary.Choice(title=label, value=(p, data)))
    choices.append(questionary.Choice(title="📁  Carregar YAML personalizado de um caminho local...", value="custom"))

    result = safe_select("Escolha o cenário:", choices)
    if result is None:
        sys.exit(0)

    if result == "custom":
        path_str = questionary.text(
            "Caminho completo do arquivo YAML:",
            validate=lambda t: (Path(t).exists() and t.endswith((".yaml",".yml"))) or "Arquivo não encontrado",
        ).ask()
        if path_str is None:
            sys.exit(0)
        yaml_path = Path(path_str)
        with open(yaml_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    else:
        yaml_path, data = result

    _preview_yaml(data)
    return yaml_path, data
