"""
Server connection prompt and health check for the remote AeroSOuDA client.
"""
from __future__ import annotations

import sys
from typing import Optional

import questionary
from rich.panel import Panel

from .config import VM_DEFAULT_CLUSTER_DIR, VM_DEFAULT_PORT
from .console import console, fatal, safe_select
from .remote import RemoteCluster


def prompt_vm_connection() -> RemoteCluster:
    """
    Prompt the user for server connection details and return a connected
    RemoteCluster instance.  Uses plain, non-technical language.
    """
    console.print(Panel(
        "[bold]Conexão com o servidor de processamento[/]\n\n"
        "Informe os dados de acesso ao servidor remoto onde\n"
        "o cluster de processamento está em execução.\n\n"
        "[dim]O servidor precisa estar ligado e com o cluster iniciado.[/]",
        border_style="cyan",
        padding=(1, 2),
    ))

    host = questionary.text(
        "Endereço do servidor (IP ou nome):",
        validate=lambda t: len(t.strip()) > 0 or "O endereço não pode ser vazio.",
    ).ask()
    if host is None:
        sys.exit(0)

    user = questionary.text("Nome de usuário no servidor:").ask()
    if user is None:
        sys.exit(0)

    auth_method = safe_select(
        "Como deseja se autenticar?",
        [
            questionary.Choice("Senha", "password"),
            questionary.Choice("Arquivo de chave de acesso (.pem / id_rsa)", "key"),
        ],
    )
    if auth_method is None:
        sys.exit(0)

    password: Optional[str] = None
    key_path: Optional[str] = None

    if auth_method == "password":
        password = questionary.password("Senha de acesso:").ask()
        if password is None:
            sys.exit(0)
    else:
        key_path = questionary.text(
            "Caminho do arquivo de chave de acesso:",
            default="~/.ssh/id_rsa",
        ).ask()
        if key_path is None:
            sys.exit(0)

    port = VM_DEFAULT_PORT
    cluster_dir = VM_DEFAULT_CLUSTER_DIR

    port_str = questionary.text(
        "Porta de acesso:",
        default=str(VM_DEFAULT_PORT),
        validate=lambda t: t.isdigit() or "A porta deve ser um número.",
    ).ask()
    if port_str and port_str.isdigit():
        port = int(port_str)

    cluster_dir = (
        questionary.text(
            "Pasta do cluster no servidor:",
            default=VM_DEFAULT_CLUSTER_DIR,
        ).ask() or VM_DEFAULT_CLUSTER_DIR
    )

    console.print()
    with console.status("[cyan]Conectando ao servidor...[/]"):
        try:
            cluster = RemoteCluster(
                host=host.strip(),
                user=user.strip(),
                password=password,
                key_path=key_path,
                port=port,
                cluster_dir=cluster_dir,
            )
            cluster.connect()
        except Exception as exc:
            fatal(
                f"Não foi possível conectar ao servidor:\n  {exc}\n\n"
                "Verifique:\n"
                "  • Endereço e nome de usuário corretos\n"
                "  • Senha ou chave de acesso válidos\n"
                "  • O servidor está ligado e acessível pela internet\n"
                "  • A porta de acesso (padrão 22) está aberta no servidor"
            )

    # Verify that the processing cluster is running
    console.print("[dim]Verificando o cluster de processamento...[/]")
    try:
        health = cluster.check_cluster()
    except Exception as exc:
        fatal(
            f"Conexão estabelecida, mas não foi possível verificar o cluster:\n  {exc}\n\n"
            "Certifique-se de que o cluster está iniciado no servidor:\n"
            f"  cd {cluster_dir} && make up"
        )

    if not health["spark_master"]:
        fatal(
            "O motor de processamento não está ativo no servidor.\n\n"
            "No servidor, inicie o cluster:\n"
            f"  cd {cluster_dir}\n"
            "  make fix-perms && make up"
        )
    if not health["namenode"]:
        fatal(
            "O sistema de armazenamento de dados não está ativo no servidor.\n\n"
            "No servidor:\n"
            f"  cd {cluster_dir} && make up"
        )

    n_workers = health['workers']
    n_data = health['datanodes']
    if n_data < 1:
        fatal(
            "O cluster foi encontrado, mas nenhum DataNode HDFS está ativo.\n\n"
            "No servidor, verifique o estado dos contêineres e reinicie:\n"
            f"  cd {cluster_dir}\n"
            "  make restart"
        )
    if n_workers < 1:
        fatal(
            "O cluster foi encontrado, mas nenhum Worker Spark está ativo.\n\n"
            "No servidor, verifique o estado dos contêineres e reinicie:\n"
            f"  cd {cluster_dir}\n"
            "  make restart"
        )
    console.print(
        f"[green]✓ Conectado ao servidor[/] [dim]{user}@{host}[/]\n"
        f"  Nós de processamento: [bold]{n_workers}[/]  "
        f"Nós de armazenamento: [bold]{n_data}[/]"
    )
    return cluster
