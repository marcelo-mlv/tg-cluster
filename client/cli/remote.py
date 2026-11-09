"""
RemoteCluster — SSH/SFTP manager for the AeroSOuDA client.

Connects to a VM running the aerosouda-cluster Docker Compose stack and
provides methods to:
  - List simulation CSVs available on the VM's HDFS
  - Transfer a local YAML scenario to the VM
  - Submit a Spark job and stream its progress
  - Retrieve output files back to the local machine via SFTP

Requirements: paramiko >= 3.4.0
"""
from __future__ import annotations

import stat
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Iterator, List, Optional

import paramiko

# Default SSH port
DEFAULT_SSH_PORT = 22

# HDFS input directory on the VM (inside the Docker network)
HDFS_INPUTS_DIR = "/inputs"

# Remote tmp paths
REMOTE_YAML_PATH = "/tmp/aerosouda_scenario.yaml"
REMOTE_OUTPUT_DIR = "/tmp/aerosouda-outputs"
REMOTE_DL_DIR = "/tmp/aerosouda_dl"


class RemoteCluster:
    """
    Manages SSH and SFTP connections to a remote AeroSOuDA VM cluster.

    Usage::

        cluster = RemoteCluster(host="203.0.113.1", user="ubuntu", password="s3cr3t")
        cluster.connect()
        csvs = cluster.list_hdfs_inputs()
        cluster.transfer_yaml(Path("scenarios/qr_correlation.yaml"))
        for line in cluster.run_job("hdfs://namenode:9000/inputs/data.csv"):
            print(line, end="")
        cluster.fetch_outputs(Path("./outputs"))
        cluster.close()
    """

    def __init__(
        self,
        host: str,
        user: str,
        password: Optional[str] = None,
        key_path: Optional[str] = None,
        port: int = DEFAULT_SSH_PORT,
        cluster_dir: str = "~/aerosouda-cluster/cluster",
    ) -> None:
        self.host = host
        self.user = user
        self.password = password
        self.key_path = key_path
        self.port = port
        self.cluster_dir = cluster_dir  # path to docker-compose.yml on VM

        self._ssh: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None
        self._compose_cmd: Optional[str] = None

    # ── Connection management ─────────────────────────────────────────────────

    def connect(self) -> None:
        """Open SSH (and implicitly SFTP) connection to the remote VM."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs: dict = {
            "hostname": self.host,
            "port": self.port,
            "username": self.user,
            "timeout": 30,
        }

        if self.key_path:
            connect_kwargs["key_filename"] = self.key_path
        elif self.password:
            connect_kwargs["password"] = self.password
        else:
            raise ValueError("Either password or key_path must be provided.")

        client.connect(**connect_kwargs)
        self._ssh = client
        self._sftp = client.open_sftp()
        self._compose_cmd = self._detect_compose_command()

    def close(self) -> None:
        """Close SSH and SFTP connections."""
        if self._sftp:
            self._sftp.close()
        if self._ssh:
            self._ssh.close()
        self._ssh = None
        self._sftp = None
        self._compose_cmd = None

    def _ssh_client(self) -> paramiko.SSHClient:
        if self._ssh is None:
            raise RuntimeError("SSH connection is not open. Call connect() first.")
        return self._ssh

    def _sftp_client(self) -> paramiko.SFTPClient:
        if self._sftp is None:
            raise RuntimeError("SFTP connection is not open. Call connect() first.")
        return self._sftp

    def _detect_compose_command(self) -> str:
        ssh = self._ssh_client()
        detect_cmd = (
            "if docker compose version >/dev/null 2>&1; then "
            "echo 'docker compose'; "
            "elif docker-compose version >/dev/null 2>&1; then "
            "echo 'docker-compose'; "
            "fi"
        )
        _, stdout, _ = ssh.exec_command(detect_cmd, timeout=15)
        compose_cmd = stdout.read().decode().strip()
        if compose_cmd not in {"docker compose", "docker-compose"}:
            raise RuntimeError(
                "Neither 'docker compose' nor 'docker-compose' is available on the remote VM."
            )
        return compose_cmd

    def _compose_command(self) -> str:
        if self._compose_cmd is None:
            self._compose_cmd = self._detect_compose_command()
        return self._compose_cmd

    # ── HDFS helpers ──────────────────────────────────────────────────────────

    def list_hdfs_inputs(self) -> List[str]:
        """
        List CSV files available in HDFS /inputs/ on the VM.

        Returns a list of full HDFS URIs, e.g.:
        ["hdfs://namenode:9000/inputs/results_quickreaction.csv", ...]
        """
        cmd = (
            "docker exec namenode "
            f"hdfs dfs -ls {HDFS_INPUTS_DIR}/ 2>/dev/null | "
            "awk '/\\.csv$/{print $NF}'"
        )
        _, stdout, _ = self._ssh_client().exec_command(cmd, timeout=30)
        lines = stdout.read().decode().strip().splitlines()
        return [f"hdfs://namenode:9000{path.strip()}" for path in lines if path.strip()]

    # ── YAML transfer ─────────────────────────────────────────────────────────

    def transfer_yaml(self, local_yaml: Path) -> str:
        """
        SCP a local YAML scenario file to REMOTE_YAML_PATH on the VM,
        then inject it into the spark-master container via docker cp.

        Returns the container-local path where the YAML was written.
        """
        # Upload to VM filesystem
        self._sftp_client().put(str(local_yaml), REMOTE_YAML_PATH)

        # Inject into spark-master container
        container_yaml = f"/tmp/aerosouda_{local_yaml.stem}.yaml"
        cmd = (
            f"cat {REMOTE_YAML_PATH} | "
            f"docker exec -i spark-master python3 -c "
            f"\"import sys; open('{container_yaml}', 'w').write(sys.stdin.read())\""
        )
        _, _, stderr = self._ssh_client().exec_command(cmd, timeout=30)
        err = stderr.read().decode()
        if err.strip():
            raise RuntimeError(f"Failed to inject YAML into container: {err}")
        return container_yaml

    # ── Job execution ─────────────────────────────────────────────────────────

    def run_job(
        self,
        hdfs_csv: str,
        container_yaml: str,
        output_dir: str = REMOTE_OUTPUT_DIR,
    ) -> Iterator[str]:
        """
        Execute the Spark job on the remote VM and stream combined output lines.

        Yields individual log lines (strings).  The combined stdout+stderr are
        multiplexed via a pseudo-terminal so both streams arrive on stdout.
        The job runs inside the spark-master container via compose exec
        (supports both docker compose and docker-compose).
        """
        script_path = "/opt/spark/scripts/run_csv_processor.sh"
        cmd = (
            f"cd {self.cluster_dir} && "
            f"{self._compose_command()} exec -T spark-master "
            f"{script_path} '{hdfs_csv}' '{output_dir}' '{container_yaml}'"
        )

        transport = self._ssh_client().get_transport()
        if transport is None:
            raise RuntimeError("SSH transport is not available.")
        channel = transport.open_session()
        channel.get_pty()  # allocate pseudo-terminal for real-time output
        channel.exec_command(cmd)

        buf = ""
        while not channel.exit_status_ready():
            if channel.recv_ready():
                data = channel.recv(4096).decode("utf-8", errors="replace")
                buf += data
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    yield line
            time.sleep(0.1)

        # Drain remaining output
        while channel.recv_ready():
            data = channel.recv(4096).decode("utf-8", errors="replace")
            buf += data
        if buf:
            for line in buf.splitlines():
                yield line

        self._last_exit_code = channel.recv_exit_status()
        channel.close()

    @property
    def last_exit_code(self) -> int:
        return getattr(self, "_last_exit_code", -1)

    # ── Output retrieval ──────────────────────────────────────────────────────

    def copy_outputs_to_vm_tmp(
        self,
        container_output_dir: str = REMOTE_OUTPUT_DIR,
        vm_dl_dir: str = REMOTE_DL_DIR,
    ) -> str:
        """
        docker cp results from inside the spark-master container to
        a temporary directory on the VM filesystem.

        Returns the VM-side path where files were copied.
        """
        cmd = (
            f"rm -rf {vm_dl_dir} && "
            f"mkdir -p {vm_dl_dir} && "
            f"docker cp spark-master:{container_output_dir}/. {vm_dl_dir}/"
        )
        _, stdout, stderr = self._ssh_client().exec_command(cmd, timeout=120)
        exit_code = stdout.channel.recv_exit_status()
        if exit_code != 0:
            err = stderr.read().decode()
            raise RuntimeError(f"docker cp from container failed: {err}")
        return vm_dl_dir

    def fetch_outputs(self, local_outputs: Path, vm_dl_dir: str = REMOTE_DL_DIR) -> int:
        local_outputs.mkdir(parents=True, exist_ok=True)
        count = 0
        try:
            entries = self._sftp_client().listdir_attr(vm_dl_dir)
        except FileNotFoundError:
            return 0

        for entry in entries:
            if stat.S_ISREG(entry.st_mode):
                remote_path = f"{vm_dl_dir}/{entry.filename}"
                local_path = local_outputs / entry.filename
                self._sftp_client().get(remote_path, str(local_path))
                count += 1

        return count

    # ── Cluster health check ──────────────────────────────────────────────────

    def check_cluster(self) -> dict:
        """
        Verify that spark-master, namenode, and at least one datanode are
        running on the VM.  Returns a dict with status info.
        """
        cmd = "docker ps --format '{{.Names}}: {{.Status}}'"
        _, stdout, _ = self._ssh_client().exec_command(cmd, timeout=15)
        lines = stdout.read().decode().splitlines()
        status = {line.split(":")[0].strip(): line for line in lines if line.strip()}
        return {
            "spark_master": any("spark-master" in k for k in status),
            "namenode": any("namenode" in k for k in status),
            "datanodes": sum(1 for k in status if "hdfs-datanode" in k),
            "workers": sum(1 for k in status if "spark-worker" in k),
            "all_containers": status,
        }
