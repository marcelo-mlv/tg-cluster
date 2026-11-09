"""
CSV selection from the remote processing server.
"""
from __future__ import annotations

import sys
from typing import Optional

import questionary

from .console import console, fatal, safe_select
from .remote import RemoteCluster


def pick_csv_from_vm(cluster: RemoteCluster) -> str:
    """
    List simulation CSVs on the remote server and let the user pick one.
    Returns the full HDFS URI (hdfs://namenode:9000/inputs/<filename>).
    """
    with console.status("[cyan]Buscando arquivos de simulação disponíveis no servidor...[/]"):
        try:
            hdfs_uris = cluster.list_hdfs_inputs()
        except Exception as exc:
            fatal(
                f"Não foi possível listar os arquivos no servidor:\n  {exc}\n\n"
                "Verifique se o cluster está em execução e acessível."
            )

    if not hdfs_uris:
        fatal(
            "Nenhum arquivo de simulação encontrado no servidor.\n\n"
            "Para adicionar arquivos de resultado ao servidor, peça ao\n"
            "operador do cluster que faça o upload dos arquivos CSV.\n"
        )

    console.print(
        f"[green]✓[/] {len(hdfs_uris)} arquivo(s) de simulação disponível(is) no servidor."
    )
    console.print()

    choices = [
        questionary.Choice(
            title=f"📄  {uri.split('/')[-1]}",
            value=uri,
        )
        for uri in hdfs_uris
    ]

    selected: Optional[str] = safe_select(
        "Selecione o arquivo de dados a processar:",
        choices,
    )

    if selected is None:
        sys.exit(0)

    console.print(f"\n[bold]Arquivo selecionado:[/] {selected.split('/')[-1]}")
    return selected
