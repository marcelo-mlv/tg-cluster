"""
Remote job execution: YAML transfer, SSH job submission, SFTP output retrieval.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import questionary
import yaml
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.text import Text

from .config import CONTAINER_TMP_OUT, OUTPUTS_DIR, STAGE_RE, VM_DL_DIR
from .console import console, custom_style, fatal
from .remote import RemoteCluster


def confirm_run(
    csv_name: str,
    yaml_path: Path,
    yaml_data: Dict[str, Any],
    vm_host: str,
) -> None:
    x = yaml_data.get("x_variable", {})
    y = yaml_data.get("y_variable", {})
    agg = yaml_data.get("batch_aggregation", {})
    console.print()
    console.print(Panel(
        Text.from_markup(
            f"[bold]Arquivo de dados:[/]  {csv_name}\n"
            f"[bold]Cenário:[/]           {yaml_data.get('name', yaml_path.name)}\n"
            f"[bold]Servidor:[/]          {vm_host}\n\n"
            f"[bold]Parâmetro X:[/]  {x.get('name','?')} "
            f"(entidade: {x.get('entity_selector',{}).get('type_contains','?')}, "
            f"campo: {x.get('field_path','?')})\n"
            f"[bold]Métrica Y:[/]    {y.get('name','?')} "
            f"(entidade: {y.get('entity_selector',{}).get('type_contains','?')}, "
            f"campo: {y.get('field_path','?')})\n"
            f"[bold]Agregação:[/]    {agg.get('type','?')}\n\n"
            f"[bold]Resultados em:[/] {OUTPUTS_DIR}"
        ),
        title="[bold white]Resumo da análise[/]",
        border_style="green",
    ))
    ok = questionary.confirm("Iniciar o processamento distribuído agora?", default=True).ask()
    if ok is None or not ok:
        console.print("[yellow]Cancelado pelo usuário.[/]")
        sys.exit(0)


def run_remote_job(
    remote: RemoteCluster,
    hdfs_csv_uri: str,
    yaml_path: Path,
    yaml_data: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Full remote job pipeline:
    1. SCP YAML → VM
    2. docker cp YAML into spark-master
    3. Run Spark job via SSH, stream progress
    4. docker cp outputs from container to VM /tmp
    5. SFTP download to local outputs/
    """
    # Step 1: transfer YAML to VM and inject into container
    console.print("[dim]Enviando configuração do cenário para o servidor...[/]")
    try:
        container_yaml = remote.transfer_yaml(yaml_path)
        console.print(f"[green]✓ Configuração do cenário enviada.[/]")
    except Exception as exc:
        fatal(f"Falha ao enviar configuração do cenário:\n{exc}")

    # Step 2: run job with progress
    console.print()

    state: Dict[str, Any] = {
        "status": "Iniciando processamento...",
        "summary": None,
        "all_lines": [],
    }
    json_buf: List[str] = []
    in_json = False
    start = time.time()

    def _collect_output() -> None:
        nonlocal in_json
        for line in remote.run_job(hdfs_csv_uri, container_yaml, CONTAINER_TMP_OUT):
            state["all_lines"].append(line)
            stripped = line.strip()

            # Detect JSON summary block
            if stripped == "{":
                in_json = True
                json_buf.clear()
            if in_json:
                json_buf.append(line)
                if stripped == "}":
                    in_json = False
                    try:
                        state["summary"] = json.loads("\n".join(json_buf))
                    except Exception:
                        pass
                continue

            # Parse Spark stage progress
            m = STAGE_RE.search(line)
            if m:
                done, total = int(m.group(1)), int(m.group(2))
                pct = int(done / total * 100) if total else 0
                state["status"] = f"Processando... {pct}% ({done}/{total} tarefas)"
                continue

            if "INFO: Scenario:" in line:
                state["status"] = "Cenário carregado, iniciando MapReduce..."
            elif "INFO: X variable:" in line:
                state["status"] = "Fase Map: extraindo métricas por partição..."
            elif "ERROR:" in line:
                err = line.split("ERROR:", 1)[-1].strip()
                state["status"] = f"Erro: {err[:60]}"

    t = threading.Thread(target=_collect_output, daemon=True)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(state["status"], total=None)
        t.start()
        while t.is_alive():
            progress.update(task, description=state["status"])
            time.sleep(0.25)
        t.join()
        progress.update(task, description=state["status"])

    elapsed = time.time() - start
    console.print()

    if remote.last_exit_code != 0:
        last = "\n".join(
            ln for ln in state["all_lines"][-20:] if not STAGE_RE.search(ln)
        )
        console.print(Panel(
            f"[red]O processamento falhou (código de saída {remote.last_exit_code}).[/]\n\n"
            "[dim]Últimas linhas do log:[/]\n" + last,
            title="[bold red]❌ Falha no processamento[/]",
            border_style="red",
        ))
        return None

    console.print(f"[green]✓ Processamento concluído em {elapsed:.1f}s.[/]")

    # Step 3: copy outputs from container to VM tmp, then SFTP to client
    console.print("[dim]Baixando arquivos de resultado...[/]")
    try:
        vm_dl = remote.copy_outputs_to_vm_tmp(CONTAINER_TMP_OUT, VM_DL_DIR)
        n_files = remote.fetch_outputs(OUTPUTS_DIR, vm_dl)
        console.print(f"[green]✓ {n_files} arquivo(s) de resultado salvos em:[/] {OUTPUTS_DIR}")
    except Exception as exc:
        console.print(f"[yellow]⚠  Não foi possível baixar os resultados: {exc}[/]")

    return state["summary"]
