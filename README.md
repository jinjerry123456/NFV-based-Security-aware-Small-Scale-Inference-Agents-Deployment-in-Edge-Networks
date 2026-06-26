# NFV-code

This repository contains Python implementations and experiments for Network Function Virtualization (NFV) service placement under security, cost, bandwidth, and compute constraints.

The project compares a custom Sec-MSL based greedy algorithm with several benchmark strategies:

- Cost-first benchmark
- Price-first benchmark
- Security-first benchmark

## Project Structure

```text
NFV-code/
├── algorithms/              # Placement algorithms and benchmark strategies
├── experiments/             # Experiment scripts for comparing algorithms
├── visualization/           # Plotting and network visualization helpers
├── topology_config.py       # Network topology, client, node, and security configuration
└── requirements.txt         # Python dependencies
```

## Requirements

- Python 3.9+
- Dependencies listed in `requirements.txt`

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the main custom algorithm:

```bash
python algorithms/my_algorithm.py
```

Run one of the comparison experiments, for example:

```bash
python experiments/compare_algorithms_by_nodes.py
```

Experiment scripts may generate output files under `results/` or `experiments/results/`. These generated outputs are ignored by git so that the repository stays focused on source code and reproducible configuration.

## Notes

- `topology_config.py` contains the network topology matrices, service node settings, client requirements, and security NF configuration used by the algorithms.
- The experiment scripts compare algorithm performance across dimensions such as node count, client count, node degree, security requirement, and NF instance count.
- This repository is intended for research, coursework, and portfolio demonstration.
