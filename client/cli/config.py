"""Constants and paths for the AeroSOuDA remote client."""
from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List

CLIENT_DIR    = Path(__file__).parent.parent.resolve()
SCENARIOS_DIR = CLIENT_DIR / "scenarios"
OUTPUTS_DIR   = CLIENT_DIR / "outputs"

VM_DEFAULT_PORT         = 22
VM_DEFAULT_CLUSTER_DIR  = "~/tg-cluster/cluster"
HDFS_NAMENODE       = "hdfs://namenode:9000"
HDFS_INPUTS_DIR     = "/inputs"
CONTAINER_TMP_OUT   = "/tmp/aerosouda-outputs"
VM_DL_DIR           = "/tmp/aerosouda_dl"

REQUIRED_COLUMNS: List[str] = [
    "id","frame","execution_id","mixr_type","asa_type",
    "asa_custom_type","payload","sim_time","utc_time",
    "execution_uuid","batch_id","experiment",
]
SKIP_FIELD_FRAGMENTS = {"ecef","_body","height","id."}
FIELD_LABELS: Dict[str,str] = {
    "frame":                   "frame — frame number (max → survival time)",
    "state.damage":            "state.damage — accumulated damage",
    "state.geo_pos.longitude": "state.geo_pos.longitude — geographic longitude",
    "state.geo_pos.latitude":  "state.geo_pos.latitude — geographic latitude",
    "state.geo_pos.altitude":  "state.geo_pos.altitude — altitude",
    "mach":                    "mach — Mach speed",
    "fuel":                    "fuel — remaining fuel",
}
STAGE_RE = re.compile(
    r"\[Stage\s+\d+:\s*[=>. ]+\s*\(\s*(\d+)\s*\+\s*\d+\s*\)\s*/\s*(\d+)\]"
)
