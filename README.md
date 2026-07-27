# Fly-in: Multi-Drone Capacity-Constrained Fleet Navigator

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Code Style](https://img.shields.io/badge/code%20style-flake8-green.svg)](https://github.com/PyCQA/flake8)
[![Type Checking](https://img.shields.io/badge/type%20checking-mypy-brightgreen.svg)](http://mypy-lang.org/)
[![Tests](https://img.shields.io/badge/tests-pytest-blue.svg)](https://docs.pytest.org/)
[![CI](https://github.com/haysamad/my_fly_in/actions/workflows/ci.yml/badge.svg)](https://github.com/haysamad/my_fly_in/actions)

An enterprise-grade, high-performance multi-drone routing and discrete-time simulation system developed as part of the **42 School curriculum**. **Fly-in** models complex aerial transport networks, navigating an autonomous fleet of drones from a starting hub to an end hub while guaranteeing zero collisions, strict capacity adherence, and optimal total turn execution.

---

## Table of Contents
1. [Executive Summary](#-executive-summary)
2. [Problem Statement & Constraints](#-problem-statement--constraints)
3. [System Architecture & Design Patterns](#-system-architecture--design-patterns)
4. [Project Structure](#-project-structure)
5. [In-Depth File & Module Breakdown](#-in-depth-file--module-breakdown)
6. [Map Syntax & File Specification](#-map-syntax--file-specification)
7. [Installation & Setup](#-installation--setup)
8. [Usage & CLI Options](#-usage--cli-options)
9. [Graphical User Interface (Pygame GUI)](#-graphical-user-interface-pygame-gui)
10. [Quality Assurance (Linting, Typing & Testing)](#-quality-assurance-linting-typing--testing)
11. [CI/CD Pipeline](#-cicd-pipeline)
12. [42 School Norm Compliance](#-42-school-norm-compliance)

---

## Executive Summary

The primary objective of **Fly-in** is to navigate a fleet of $N$ autonomous drones from a designated origin (`start_hub`) to a final destination (`end_hub`) through an arbitrary graph of interconnected zones in the **minimum total number of discrete simulation turns**.

Every movement step must strictly comply with zone hosting capacities, connection line traversal limits, zone transit delays, and safety rules without causing deadlocks or race conditions.

---

## ⚡ Problem Statement & Constraints

Modeling real-world multi-agent drone traffic introduces strict operational constraints:

### 1. Capacity Limits
* **Zone Node Capacity (`max_drones`)**: Each zone can host at most a pre-defined number of stationary or arriving drones during any given simulation turn step.
* **Connection Link Capacity (`max_link_capacity`)**: Each edge connecting two zones restricts how many drones can traverse the link simultaneously.

### 2. Zone Taxonomy & Cost Dynamics
* **`NORMAL`**: Standard hub. Cost = 1 turn step. Capacity = `max_drones` (default: 1).
* **`RESTRICTED`**: High-security or narrow zone. Introduces a mandatory inspection delay. Cost = 2 turn steps (requires an intermediate transition state `ENTER_CONNECTION`).
* **`PRIORITY`**: Preferred flight corridors. Cost = 1 turn step, but selected over normal zones during pathfinding tie-breaking.
* **`BLOCKED`**: Impassable zones. Drones are strictly forbidden from entering or routing through blocked nodes.

### 3. Safety & Deadlock Avoidance
* **No Collisions**: Drones must never exceed link or node capacities during state updates.
* **Batch Scheduling**: Movements planned for a given turn are evaluated as an atomic batch to prevent over-subscription before state execution.

---

## System Architecture & Design Patterns

The project follows a clean, decoupled **Layered Object-Oriented Architecture**:
```
+-------------------------------------------------------+
|                    CLI & Execution                    |
|             (src/cli.py, src/main.py)                 |
+---------------------------+---------------------------+
|
+---------------------------v---------------------------+
|                   Map Parsing Layer                   |
|              (src/parser/map_parser.py)               |
+---------------------------+---------------------------+
|
+---------------------------v---------------------------+
|                Pathfinding Router Layer               |
|            (src/algorithms/dijkstra.py)               |
+---------------------------+---------------------------+
|
+---------------------------v---------------------------+
|             Discrete Simulation Engine                |
|             (src/simulation/engine.py)                |
+---------------------------+---------------------------+
|
+---------------------------v---------------------------+
|                  Visualization Layer                  |
|    (Terminal Rich UI  |  Pygame Cyberpunk GUI)        |
+-------------------------------------------------------+
```
---

## Project Structure

```text
fly_in/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI pipeline configuration
├── assets/
│   ├── image-from-rawpixel-id-6482170-png.png # Drone graphic sprite
│   └── travel.png              # Hub base graphic sprite
├── data/
│   └── map.txt                 # Example network graph map file
├── src/
│   ├── __main__.py             # Main entry point and reset loop orchestrator
│   ├── cli.py                  # Command line argument parser
│   ├── algorithms/
│   │   └── dijkstra.py         # Modified Dijkstra shortest-path router
│   ├── core/
│   │   ├── enums.py            # Domain state enums (ZoneType, DroneStatus, ActionType)
│   │   ├── exceptions.py       # Custom exception hierarchy
│   │   └── models.py           # Domain models (Zone, Connection, Drone, Map)
│   ├── parser/
│   │   └── map_parser.py       # Syntax parser and BFS graph validator
│   ├── simulation/
│   │   └── engine.py           # Turn step batch scheduler and simulation engine
│   └── visualizers/
│       ├── pygame_gui.py       # Glassmorphism Pygame GUI visualizer
│       └── terminal_rich.py    # Rich CLI colored terminal output formatter
├── tests/
│   ├── test_parser.py          # Unit tests for map parsing & validation
│   ├── test_pathfinding.py     # Unit tests for Dijkstra path calculation
│   └── test_simulation.py      # Unit tests for simulation execution
├── .gitignore
├── Makefile                    # Phony targets for running, testing, and linting
├── pyproject.toml              # UV dependency management & pytest settings
└── uv.lock                     # Locked deterministic dependency versions
```

---

## In-Depth File & Module Breakdown

### 1. Core Domain Layer (`src/core/`)
* **`enums.py`**: Strong type definitions for system states:
  - `ZoneType`: `NORMAL`, `RESTRICTED`, `PRIORITY`, `BLOCKED`.
  - `DroneStatus`: `IDLE`, `MOVING`, `WAITING`, `ARRIVED`.
  - `ActionType`: `MOVE`, `ENTER_CONNECTION`, `ARRIVE`, `ARRIVE_FINAL`.
* **`exceptions.py`**: Extends `FlyInError` into specific domain faults (`MapParseError`, `MapValidationError`, `PathfindingError`, `SimulationError`).
* **`models.py`**: Encapsulated state entities:
  - `Zone`: Graph node holding coordinates, capacity limits, and active drones.
  - `Connection`: Edge link tracking directional/bidirectional flow capacity.
  - `Drone`: Autonomous agent managing step pointers and status.
  - `Map`: Container managing graph lookup operations (`find_zone`, `neighbors`).

### 2. Parser Layer (`src/parser/map_parser.py`)
* **`MapParser`**:
  - Handles line tokenization, comment stripping (`#`), and metadata bracket parsing (`[...]`).
  - Enforces topology sanity checks: exactly one origin (`start_hub`) and destination (`end_hub`).
  - Executes Breadth-First Search (BFS) graph reachability to ensure a valid route exists prior to simulation execution.

### 3. Pathfinding Router (`src/algorithms/dijkstra.py`)
* **`DijkstraRouter`**:
  - Calculates cost-optimal trajectories using a min-heap priority queue (`heapq`).
  - Applies a tuple cost metric `(turn_cost, priority_score)` to prioritize `PRIORITY` zones when turn costs are tied.
  - Expands path arrays into step-indexed simulation actions (`build_indexed_actions`).

### 4. Simulation Engine (`src/simulation/engine.py`)
* **`SimulationEngine`**:
  - Executes turn steps sequentially.
  - Collects desired movement intents for all active drones.
  - Runs capacity reservation safety checks before updating drone positions.
  - Formats output logs matching the standard format (`D1-zoneA D2-zoneB`).

### 5. Visualizer Layer (`src/visualizers/`)
* **`pygame_gui.py`**:
  - Interactive graphical visualizer built with Pygame-CE.
  - Features real-time LERP flight path interpolation.
  - Dynamic canvas panning (left-click drag) and zooming (mouse wheel).
  - Responsive window resizing (`pygame.RESIZABLE`).
* **`terminal_rich.py`**:
  - Pretty-prints simulation logs to stdout using `rich` panels and tables.

---

## Map Syntax & File Specification

Map files use a plain-text declarative syntax:

```text
# Number of drones to route
nb_drones: 5

# Node declarations: hub/start_hub/end_hub: <name> <x> <y> [metadata]
start_hub: start 0 0 [max_drones=5]
end_hub: goal 10 0 [max_drones=5]
hub: corridorA 3 0 [zone=priority]
hub: tunnelB 7 0 [zone=restricted max_drones=2]

# Edge declarations: connection: <from>-<to> [metadata]
connection: start-corridorA [max_link_capacity=2]
connection: corridorA-tunnelB [max_link_capacity=1]
connection: tunnelB-goal [max_link_capacity=2]
```

---

## Installation & Setup

This project uses **`uv`**, an extremely fast Python package and project manager.

### 1. Clone Repository
```bash
git clone https://github.com/haysamad/my_fly_in.git
cd my_fly_in
```

### 2. Install Virtual Environment & Dependencies
```bash
uv sync
```

---

## Usage & CLI Options

Run the simulation using `make` shortcuts or direct `uv` execution commands:

### Makefile Commands
```bash
# Run CLI terminal simulation with Rich output
make run

# Run graphical Pygame visualizer
make run-gui

# Run code style & type checkers
make lint

# Run unit tests
make test
```

### Command Line Flags
```bash
# Terminal visualization mode
uv run python -m src data/map.txt --viz terminal

# Graphical UI mode
uv run python -m src data/map.txt --viz gui

# Raw stdout mode (for pipe scripting)
uv run python -m src data/map.txt --viz none
```

---

## Graphical User Interface (Pygame GUI)

The Pygame visualizer provides an intuitive desktop simulation interface:

| Control | Action / Gesture |
| :--- | :--- |
| **Canvas Pan** | Click and hold **Left Mouse Button** anywhere on the canvas to drag |
| **Canvas Zoom** | Scroll **Mouse Wheel Up / Down** to zoom in or out |
| **Single Turn Step** | Press `SPACE` on keyboard to trigger a single simulation step |
| **Auto-Play Flight** | Click `AUTO >>` button for continuous automated simulation |
| **Flight Speed Toggle** | Click `Speed: 1x / 2x / 4x` button to accelerate flight animations |
| **Reset Simulation** | Click `RESET` button to reset all drones to `start_hub` |
| **Resize Window** | Drag window borders or maximize for responsive layout adaptation |

---

## Quality Assurance (Linting, Typing & Testing)

Strict quality standards are enforced across the codebase:

### Code Formatting & Type Safety
```bash
make lint
```
Executes `flake8` for PEP8 compliance (line length ≤ 79 chars) and `mypy` for strict type annotation checking across all source modules.

### Unit Tests
```bash
make test
```
Executes `pytest` over test modules covering parser validation, pathfinding correctness, and simulation engine execution.

---

## CI/CD Pipeline

Automated checks are executed on GitHub Actions (`.github/workflows/ci.yml`) on every `push` and `pull_request`:

* Sets up Python 3.10 environment.
* Installs `uv` and synchronizes dependencies.
* Executes `flake8` and `mypy`.
* Runs all `pytest` unit test suites.

---

## 42 School Norm Compliance

* **Language**: Python 3.10+ using object-oriented principles.
* **No Graph Libraries**: All graph structures and search algorithms (Dijkstra, BFS) are implemented completely from scratch.
* **Code Quality**: Passes `flake8` (0 warnings) and strict `mypy` static type checking.
* **Standard Logs**: Formats movement output strings adhering strictly to the assignment specifications.