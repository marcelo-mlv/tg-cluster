# AeroSOuDA Cluster

Distributed Spark + HDFS cluster for processing aerospace simulation outputs.
Deploy on a VM; analysts connect remotely using the **AeroSOuDA Client** CLI.

## Architecture

| Component       | Count        | Role                                 |
| --------------- | ------------ | ------------------------------------ |
| HDFS NameNode   | 1            | Filesystem metadata                  |
| HDFS DataNode   | 4            | Block storage (replication factor 2) |
| Spark Master    | 1            | Job scheduler                        |
| Spark Worker    | 6            | Distributed computation              |
| Spark History   | 1            | Job timeline viewer                  |
| **Total** | **13** | containers                           |

## Prerequisites (VM)

- Linux (Ubuntu 22.04+), Docker Engine 24+ with Compose v2
- At least 12 GB free disk
- SSH access to the VM (**22**). No host port publishing is required for normal operation.

## Quick Start

```bash
git clone <repo-url>
cd aerosouda-cluster/cluster
make fix-perms && make up
```

## Load Simulation CSVs into HDFS

Antes de qualquer `hdfs dfs`, o cluster precisa estar levantado e o NameNode pronto.

```bash
cd /path/to/aerosouda-cluster/cluster
make fix-perms && make up

# Aguarde o NameNode ficar pronto (normalmente 20–60s)
docker ps --format 'table {{.Names}}\t{{.Status}}'
docker exec namenode hdfs dfsadmin -safemode get

# Copie o CSV para dentro do container do NameNode
# (substitua pelo caminho real do arquivo local)
docker cp /path/to/results.csv namenode:/tmp/

docker exec namenode hdfs dfs -mkdir -p /inputs
docker exec namenode hdfs dfs -put -f /tmp/results.csv /inputs/
docker exec namenode hdfs dfs -ls /inputs/   # verify
```

Se o comando falhar com `Connection refused`, normalmente é porque o NameNode ainda não iniciou ou o cluster não foi levantado com `make up`.

Analysts connecting via the AeroSOuDA Client will see the /inputs/ listing automatically.

If you see `BlockMissingException` or `ReplicaNotFoundException` while Spark reads
an input file, recreate HDFS metadata and re-upload the CSV:

```bash
docker compose down -v
make fix-perms && make up
docker exec namenode hdfs dfsadmin -safemode get   # wait until OFF
docker cp /path/to/results.csv namenode:/tmp/
docker exec namenode hdfs dfs -mkdir -p /inputs
docker exec namenode hdfs dfs -put -f /tmp/results.csv /inputs/
docker exec namenode hdfs fsck /inputs/results.csv -files -blocks -locations
```

## Configuration Files

| File                         | Purpose                                    |
| ---------------------------- | ------------------------------------------ |
| `conf/hadoop.env`          | HDFS env vars (replication=2, block=128MB) |
| `conf/core-site.xml`       | fs.defaultFS for Spark Hadoop client       |
| `conf/hdfs-site.xml`       | HDFS daemon config                         |
| `conf/spark-defaults.conf` | Spark tuning + PYTHONPATH for workers      |

## Bundled YAML Scenarios (in scenarios/)

- `qr_correlation.yaml` — Quick-Reaction: radar longitude vs fighter survival time (Pearson)
- `damage_analysis.yaml` — Damage: radar longitude vs max fighter damage (Pearson)

## Headless operation (default)

This deployment is intentionally headless: Spark/HDFS services communicate on the internal Docker network only.
The remote client uses SSH + `docker exec` to submit jobs and collect outputs, so no service ports need to be exposed on the VM host.
