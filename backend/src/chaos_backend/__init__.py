"""Chaos One backend.

Services:
- Discrimination — RV / decoy / debris classification ensemble.
- CourseOfAction — game-theoretic COA generation.
- AdversaryModel — Bayesian playbook hypothesis tracking.

Each service ships with a deterministic mock implementation suitable for
front-end development; real ML and optimization land in milestones 4 and 6.
"""

__version__ = "0.1.0"
