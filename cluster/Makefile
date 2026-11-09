# AeroSOuDA Cluster — VM deployment targets
COMPOSE ?= $(shell \
	if docker compose version >/dev/null 2>&1; then \
		echo "docker compose"; \
	elif docker-compose version >/dev/null 2>&1; then \
		echo "docker-compose"; \
	fi \
)
ifeq ($(strip $(COMPOSE)),)
	$(error Neither "docker compose" nor "docker-compose" was found in PATH)
endif

MIN_GB  = 12

.PHONY: help up down restart status logs fix-perms hdfs-usage clean-hdfs check-space

help:
	@echo "AeroSOuDA Cluster (VM deployment)"
	@echo ""
	@echo "  make check-space  — Verify enough disk space (min $(MIN_GB) GB)"
	@echo "  make up           — Start all 13 containers (HDFS + Spark)"
	@echo "  make down         — Stop containers (preserves HDFS volumes)"
	@echo "  make down-v       — Stop containers AND delete HDFS data"
	@echo "  make restart      — Full down → up cycle (clears stale workers)"
	@echo "  make status       — Show container status"
	@echo "  make logs         — Follow spark-master logs"
	@echo "  make fix-perms    — Fix bind-mount permissions for Spark UID 185"
	@echo "  make hdfs-usage   — Show HDFS disk usage"
	@echo "  make clean-hdfs   — Delete all files in HDFS /inputs and /outputs"
	@echo ""
	@echo "Setup: git clone <repo> && cd cluster && make fix-perms && make up"

check-space:
	@echo "=== Disk space check ===" && \
	DOCKER_ROOT=$$(docker info --format '{{.DockerRootDir}}' 2>/dev/null); \
	AVAIL=$$(df --output=avail -BG "$$DOCKER_ROOT" 2>/dev/null | tail -1 | tr -d 'G '); \
	echo "  Available: $${AVAIL} GB  |  Required: $(MIN_GB) GB"; \
	[ "$$AVAIL" -ge "$(MIN_GB)" ] && echo "  Status: OK" || (echo "  ERROR: insufficient space" && exit 1)

fix-perms:
	@echo "Setting permissions for Spark UID 185..."
	chmod 777 events inputs outputs scenarios
	@echo "Done."

up: check-space fix-perms
	$(COMPOSE) up -d
	@echo "\nCluster started (detached mode)."
	@echo "Use the AeroSOuDA client over SSH to submit jobs and fetch outputs."

down:
	$(COMPOSE) down

down-v:
	$(COMPOSE) down -v
	@echo "WARNING: HDFS volumes deleted. All data is lost."

restart: down up

status:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f spark-master

hdfs-usage:
	@docker exec namenode hdfs dfs -du -s -h / 2>/dev/null || echo "HDFS not running"
	@docker exec namenode hdfs dfs -du -h / 2>/dev/null || true

clean-hdfs:
	@echo "WARNING: Deleting all HDFS /inputs and /outputs"
	@read -p "Continue? [y/N] " ans && [ "$$ans" = "y" ] || exit 1
	@docker exec namenode hdfs dfs -rm -r -skipTrash /inputs/* 2>/dev/null || true
	@docker exec namenode hdfs dfs -rm -r -skipTrash /outputs/* 2>/dev/null || true
	@docker exec namenode hdfs dfs -expunge 2>/dev/null || true
