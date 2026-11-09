"""
AeroSOuDA Remote Client — main pipeline.
"""
from __future__ import annotations

import sys

from rich.panel import Panel
from rich.text import Text

from .console import console
from .connection import prompt_vm_connection
from .csv_source import pick_csv_from_vm
from .scenario import pick_scenario
from .job import confirm_run, run_remote_job
from .results import show_results


def _welcome() -> None:
    console.print()
    console.print(Panel(
        Text.from_markup(
            "[bold cyan][italic]AeroSOuDA — Análise Distribuída de Simulações[/]\n\n"
            "Pipeline de análise remota com Apache Spark.\n"
            "O cluster de processamento fica em um servidor remoto;\n"
            "este programa se conecta a ele automaticamente.\n\n"
            "  [green]1.[/] Conectar ao servidor de processamento\n"
            "  [green]2.[/] Selecionar arquivo de dados de simulação\n"
            "  [green]3.[/] Selecionar ou criar cenário de análise\n"
            "  [green]4.[/] Enviar para processamento — acompanhar progresso — receber resultados\n\n"
        ),
        title="[bold white]Bem-vindo — AeroSOuDA Client[/]",
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()


def main() -> None:
    try:
        console.clear()
        _welcome()

        # 1. Conectar ao servidor remoto
        remote = prompt_vm_connection()

        try:
            # 2. Listar arquivos de dados disponíveis no servidor
            console.print()
            hdfs_uri = pick_csv_from_vm(remote)
            csv_name = hdfs_uri.split("/")[-1]

            # 3. Selecionar cenário de análise (YAML local ou padrão)
            yaml_path, yaml_data = pick_scenario()

            # 4. Confirmar e enviar para processamento
            confirm_run(csv_name, yaml_path, yaml_data, remote.host)

            summary = run_remote_job(remote, hdfs_uri, yaml_path, yaml_data)

            # 5. Exibir resultados
            show_results(summary, csv_name)

        finally:
            remote.close()

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelado pelo usuário (Ctrl+C).[/]")
        sys.exit(0)
