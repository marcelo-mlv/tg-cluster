# AeroSOuDA — Remote Distributed Architecture

Two-component system for distributed aerospace simulation output processing:

```
tg-cluster/
├── cluster/    — Docker Compose cluster (deploy on VM)
│                 13 containers: HDFS (1 namenode + 4 datanodes) + Spark (1 master + 6 workers + history)
└── client/     — Remote CLI (run on analyst's laptop, NO Docker required)
```

## How It Works

1. The **cluster** runs on a remote VM. Simulation CSVs are pre-loaded into HDFS.
2. The **client** connects via SSH, lists available CSVs, sends a YAML scenario config, and triggers the Spark job.
3. Output files (CSV + PNG + JSON summary) are automatically downloaded to the analyst's machine via SFTP.

## Setup

### VM (cluster)

```bash
cd cluster
make fix-perms && make restart
# Load simulation CSVs into HDFS:
docker cp path/to/results/file.csv namenode:/tmp/ && docker exec namenode hdfs dfs -put -f /tmp/results.csv /inputs/
```

### Analyst laptop (client)

```bash
cd client
pip install -r requirements.txt   # Python 3.8.20+, NO Docker
python cli.py                     # Interactive CLI
```

See `cluster/README.md` and `client/README.md` for detailed instructions.
