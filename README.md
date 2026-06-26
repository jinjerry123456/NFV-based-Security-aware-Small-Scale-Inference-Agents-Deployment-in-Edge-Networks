# Asymmetric Protection-Based S-SFC Deployment for LLM-Inference-Enabled Networks

This repository contains Python implementations and experiments for secure service function chain (S-SFC) deployment in network function virtualization (NFV) environments. The code models how client workloads can be assigned to service nodes while considering security protection, GPU compute cost, bandwidth cost, topology distance, and node capacity constraints.

The project is designed as a research/experiment codebase. It compares a custom Sec-MSL based greedy deployment algorithm with three baseline strategies across multiple topology and workload dimensions.

## Key Ideas

The deployment problem in this repository is modeled around the following entities:

- Clients are deployed on selected topology nodes and have traffic demand and security requirements.
- Service nodes host security network functions (S-NFs) and provide service to clients.
- Each node has GPU capacity, provider-specific GPU price, client-serving capacity, and existing NF instances.
- A node may need security augmentation if its current protection level does not satisfy a client requirement.
- A selected service node can serve multiple clients as long as its capacity constraint is satisfied.

The custom algorithm uses a Sec-MSL score to choose a node-client pair in each greedy iteration:

```text
Sec-MSL(node, client) = (security cost + compute cost + bandwidth cost) / client quantity
```

At a high level, the algorithm repeatedly evaluates feasible service node and client pairs, performs security augmentation planning when needed, and selects the pair with the lowest Sec-MSL value until all deployed clients are served.

## Algorithms

The repository compares four deployment strategies:

| Algorithm | File | Main selection criterion |
| --- | --- | --- |
| My Algorithm | `algorithms/my_algorithm.py` | Minimize Sec-MSL, which combines security augmentation cost, compute cost, and bandwidth cost per client quantity. |
| Cost-first | `algorithms/benchmark_cost-first.py` | Prioritize lower security augmentation cost per client. |
| Price-first | `algorithms/benchmark_price-first.py` | Prioritize nodes with lower provider-specific GPU unit price. |
| Security-first | `algorithms/benchmark_security-first.py` | Prioritize nodes with higher security protection level. |

Each algorithm returns a result dictionary containing selected service nodes, served clients, node-client mappings, cost breakdowns, execution time, average security level, average client-node hops, and security augmentation statistics.

## Repository Structure

```text
NFV-code/
├── algorithms/
│   ├── my_algorithm.py                  # Sec-MSL greedy deployment algorithm
│   ├── benchmark_cost-first.py          # Cost-oriented baseline
│   ├── benchmark_price-first.py         # GPU-price-oriented baseline
│   └── benchmark_security-first.py      # Security-oriented baseline
├── experiments/
│   ├── compare_algorithms_by_nodes.py
│   ├── compare_algorithms_by_degree.py
│   ├── compare_algorithms_by_clients.py
│   ├── compare_algorithms_by_nf_instances.py
│   ├── compare_algorithms_by_security.py
│   ├── compare_algorithms_by_client_acceptance.py
│   ├── export_all_comparisons_to_excel.py
│   ├── export_all_comparisons_to_excel_parallel.py
│   └── visualization*.py
├── visualization/                       # Placeholder/helper visualization package
├── topology_config.py                   # Topologies, nodes, clients, S-NFs, costs, and graph utilities
├── requirements.txt
├── LICENSE
└── README.md
```

## Core Configuration

Most experiment configuration is centralized in `topology_config.py`. It includes:

- Predefined and generated network topologies for 20, 30, 40, and 50 nodes.
- Node data templates with different numbers of NF instances per node.
- Client demand, client deployment, and security requirement settings.
- Security network function protection matrices for multiple attack types.
- Provider-specific GPU price settings.
- Graph utilities for hop-count and bandwidth-cost calculation.
- Reset utilities used by experiments to restore node and topology state between runs.

The experiment scripts temporarily modify this configuration during each run so that different topology sizes, node degrees, client counts, security requirements, and NF instance counts can be tested.

## Experiment Dimensions

The code supports six major comparison dimensions:

| Script | Compared dimension |
| --- | --- |
| `experiments/compare_algorithms_by_nodes.py` | Number of topology nodes: 20, 30, 40, 50 |
| `experiments/compare_algorithms_by_degree.py` | Topology degree: 2, 3, 4, 5 |
| `experiments/compare_algorithms_by_clients.py` | Number of deployed clients: 3, 5, 8, 10 |
| `experiments/compare_algorithms_by_nf_instances.py` | Number of NF instances per node: 2, 3, 4, 5 |
| `experiments/compare_algorithms_by_security.py` | Security requirement level: 10, 18, 26, 34 |
| `experiments/compare_algorithms_by_client_acceptance.py` | Client acceptance rate under larger client counts |

The exported metrics include overall cost, cost per security level, average security level, bandwidth cost, average hop count, security augmentation cost, augmented NF count, GPU augmentation, node count, client coverage, and execution time.

## Requirements

- Python 3.9+
- Python packages listed in `requirements.txt`

Install the required packages:

```bash
pip install -r requirements.txt
```

The core algorithms and Excel export scripts mainly use the Python standard library and `openpyxl`. Some plotting scripts may additionally require `matplotlib` and `numpy`.

## Quick Start

Run the custom algorithm on the default topology:

```bash
python algorithms/my_algorithm.py
```

This prints the selected service nodes, served clients, node-client mapping, total cost, security augmentation cost, execution time, and security-level statistics.

## Small Smoke Test

For a quick validation without running the full experiment grid, you can run a small one-configuration comparison from the project root:

```bash
python - <<'PY'
import os
from openpyxl import Workbook
import experiments.compare_algorithms_by_nodes as exp

exp.NUM_RUNS = 1
exp.NODE_SIZES = [20]
exp.DEGREES = [2]
exp.CLIENT_COUNTS = [3]
exp.SECURITY_REQUIREMENTS = [10]
exp.NODE_NF_COUNTS = [2]
exp.GENERATED_TOPOLOGIES_PER_COMBO = 1
exp.VERBOSE_PROGRESS = False

all_results = exp.run_all_algorithms_by_nodes()
exp.print_summary(all_results)
summary = exp.aggregate_by_nodes(all_results)

wb = Workbook()
wb.remove(wb.active)
exp.write_nodes_sheet(wb, summary)
os.makedirs("results", exist_ok=True)
wb.save("results/smoke_nodes.xlsx")
print("Saved results/smoke_nodes.xlsx")
PY
```

This generates a small Excel result file at `results/smoke_nodes.xlsx`.

## Running Experiments

Run a single experiment dimension:

```bash
python experiments/compare_algorithms_by_nodes.py
```

Run all six experiment dimensions sequentially and export one combined workbook:

```bash
python experiments/export_all_comparisons_to_excel.py
```

You can also pass custom arguments:

```bash
python experiments/export_all_comparisons_to_excel.py results/summary.xlsx 10 3 0
```

The arguments are:

```text
output_path NUM_RUNS GENERATED_TOPOLOGIES_PER_COMBO VERBOSE_PROGRESS
```

Run all six experiment dimensions in parallel:

```bash
python experiments/export_all_comparisons_to_excel_parallel.py --runs 1 --topo 1 --no-verbose
```

For larger experiments, increase `--runs` and `--topo`:

```bash
python experiments/export_all_comparisons_to_excel_parallel.py --runs 120 --topo 4 --processes 6 --no-verbose
```

Be aware that the full default sweep can be computationally expensive because it evaluates many combinations of node size, topology degree, client count, NF count, security requirement, generated topologies, algorithms, and repeated runs.

## Generated Outputs

Experiment outputs are written under `results/` or `experiments/results/`. These paths are ignored by git to keep the repository focused on source code and reproducible configuration.

Typical outputs include:

- Excel files for individual experiment dimensions.
- A combined Excel workbook for all six dimensions.
- CSV files used by visualization scripts.
- Plot images generated from experiment outputs.

## Visualization

Visualization scripts are located under `experiments/visualization*.py`. They are intended to process generated Excel or CSV results and produce charts for analysis. Some paths in these scripts are configured for existing experiment output folders, so you may need to update the input result directory before running them.

Example:

```bash
python experiments/visualization.py
```

## Reproducibility Notes

- Random topology generation is controlled by seed-related settings in `topology_config.py`.
- Client selection can be random or fixed depending on `USE_RANDOM_CLIENT_SELECTION`.
- The experiment scripts reset topology and node state between runs to avoid state leakage across algorithm comparisons.
- Generated results are intentionally not committed; rerun the experiment scripts to reproduce them.

## License

This project is released under the MIT License. See `LICENSE` for details.
