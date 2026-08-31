*This project has been created as part of the 42 curriculum by <login>.*

# Fly-in: Discrete-Event Multi-Drone Routing Simulation

Fly-in is an optimized, object-oriented multi-agent routing simulation written in Python 3.10+. It computes collision-free, turn-optimal flight paths for fleets of autonomous drones navigating a constrained topological network.

---

## Description

The system reads network maps specifying zones, zone types (`normal`, `priority`, `restricted`, `blocked`), dynamic zone occupancies (`max_drones`), bidirectional connections, and link capacities (`max_link_capacity`). 

Using custom graph structures and space-time heuristic planning, the engine coordinates simultaneous flights, avoids bottlenecks, respects 2-turn restricted transit constraints, and delivers all drones to the target hub in the minimal possible number of simulation turns.

---

## Instructions

### 1. Installation
Install project dependencies (`pygame`, `pytest`, `flake8`, `mypy`):
```bash
make install