#!/usr/bin/env bash
# AeroSOuDA — Serial (single-executor) Spark job launcher
#
# Identical to run_csv_processor.sh but restricts the job to a single
# executor, single core, and single partition.  This is the benchmark
# baseline for the experimental evaluation in Chapter 7.
#
# Methodological note:
#   Using 1 executor / 1 core / 1 partition produces a "serial" execution
#   within the Spark framework.  The code path is IDENTICAL to the parallel
#   mode; only the resource configuration differs.  This ensures a fair
#   apples-to-apples comparison that isolates the benefit of task-level
#   parallelism from any implementation difference.
#
# Usage:  run_csv_processor_serial.sh <input_csv> <output_dir> [scenario]
#   input_csv may be a local path OR an HDFS URI (hdfs://namenode:9000/...)

set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <input_csv> <output_dir> [scenario_config]"
  exit 1
fi

INPUT_CSV="$1"
OUTPUT_DIR="$2"
SCENARIO_CONFIG="${3:-/opt/spark/scenarios/qr_correlation.yaml}"

SCRIPTS_DIR="$(dirname "$(readlink -f "$0")")"

# Serial configuration overrides
SPARK_EXECUTOR_INSTANCES=1
SPARK_EXECUTOR_MEMORY="${SPARK_EXECUTOR_MEMORY:-512m}"
SPARK_DRIVER_MEMORY="${SPARK_DRIVER_MEMORY:-1g}"
SPARK_SQL_SHUFFLE_PARTITIONS=1
SPARK_CORES_MAX=1
SPARK_EXECUTOR_CORES=1
AGG_PARTITIONS=1  # single RDD partition → sequential mapPartitions

# Validate local path (HDFS URIs are validated by Spark itself)
if [[ "$INPUT_CSV" != hdfs://* ]] && [[ ! -f "$INPUT_CSV" ]]; then
  echo "ERROR: Input CSV not found: $INPUT_CSV"
  exit 1
fi

FS_CONF="--conf spark.hadoop.fs.defaultFS=file:///"
if [[ "$INPUT_CSV" == hdfs://* ]]; then
  FS_CONF="--conf spark.hadoop.fs.defaultFS=hdfs://namenode:9000 --conf spark.hadoop.dfs.client.use.datanode.hostname=false"
fi

echo "INFO: Serial mode — 1 executor, 1 core, 1 partition"

# shellcheck disable=SC2086
/opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --conf "spark.executor.instances=${SPARK_EXECUTOR_INSTANCES}" \
  --conf "spark.executor.memory=${SPARK_EXECUTOR_MEMORY}" \
  --conf "spark.executor.cores=${SPARK_EXECUTOR_CORES}" \
  --conf "spark.cores.max=${SPARK_CORES_MAX}" \
  --conf "spark.driver.memory=${SPARK_DRIVER_MEMORY}" \
  --conf "spark.sql.shuffle.partitions=${SPARK_SQL_SHUFFLE_PARTITIONS}" \
  $FS_CONF \
  "${SCRIPTS_DIR}/csv_processor.py" \
  --input-file "$INPUT_CSV" \
  --output-path "$OUTPUT_DIR" \
  --scenario-config "$SCENARIO_CONFIG" \
  --initial-partitions 1 \
  --agg-partitions "${AGG_PARTITIONS}"
