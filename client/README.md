# AeroSOuDA Client

Remote CLI for submitting distributed analysis jobs to the AeroSOuDA cluster on a VM.

**No Docker required.** The analyst's laptop only needs Python 3.8.20.

## Quick Start

```bash
git clone <repo-url>
cd aerosouda-cluster/client

# Install Python dependencies (no Docker needed)
pip install -r requirements.txt

# Run the interactive CLI
python cli.py
```

The CLI will prompt you for:

1. **VM IP/hostname** — the machine running the AeroSOuDA cluster
2. **SSH credentials** — username + password or SSH key path
3. **Input CSV** — list is fetched automatically from VM's HDFS `/inputs/`
4. **Analysis scenario** — pick a bundled YAML or load your own

Results are downloaded to `client/outputs/`.

## Prerequisites

| Requirement  | Version                                          |
| ------------ | ------------------------------------------------ |
| Python       | 3.8.20+                                          |
| pip packages | see requirements.txt                             |
| SSH access   | to the VM running `aerosouda-cluster/cluster/` |

## Bundled Scenarios (in `scenarios/`)

Ready-to-use analysis configurations:

- **`qr_correlation.yaml`** — radar longitude vs fighter survival time (Pearson r)
- **`damage_analysis.yaml`** — radar longitude vs max fighter damage (Pearson r)

You can also use any custom YAML following the same structure.

## YAML Scenario Format

```yaml
name: "My Analysis"
x_variable:
  name: "independent_variable_name"
  entity_selector:
    side: "red"           # "red" or "blue"
    type_contains: "radar"
  field_path: "state.geo_pos.longitude"
  frame_aggregation: "last"   # max | min | last | first
  scope: "per_experiment"     # per_experiment | per_entity
y_variable:
  name: "metric_name"
  entity_selector:
    side: "blue"
    type_contains: "fighter"
  field_path: "frame"         # "frame" = survival time via max aggregation
  frame_aggregation: "max"
  scope: "per_entity"
batch_aggregation:
  type: "pearson_correlation" # pearson_correlation | mean_y | count_y | scatter_only
```
