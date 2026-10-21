"""Service registry defining synthetic candidate cloud services and their baseline QoS.

This module provides deterministic synthetic services with baseline QoS metrics,
allowing reproducible testing and demonstration of failure scenarios.
"""

from __future__ import annotations
import copy
from dataclasses import dataclass, asdict
from typing import Dict, List, Any


@dataclass
class CloudService:
    """Represents a cloud service candidate with QoS metrics and operational status."""
    service_id: str
    name: str
    category: str
    latency: float       # In milliseconds (lower is better)
    cost: float          # In illustrative currency units per invocation (lower is better)
    availability: float  # Percentage 0-100 (higher is better)
    reliability: float   # Percentage 0-100 (higher is better)
    operational_status: str  # "AVAILABLE" or "UNAVAILABLE"
    baseline: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert service instance to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CloudService:
        """Create a service instance from dictionary."""
        data_copy = copy.deepcopy(data)
        return cls(**data_copy)


# Deterministic synthetic candidate service definitions
_INITIAL_SERVICES_DATA: List[Dict[str, Any]] = [
    {
        "service_id": "SVC-C01",
        "name": "NovaCompute Standard",
        "category": "Compute",
        "latency": 45.0,
        "cost": 0.040,
        "availability": 99.90,
        "reliability": 99.50,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 45.0,
            "cost": 0.040,
            "availability": 99.90,
            "reliability": 99.50,
            "operational_status": "AVAILABLE",
        },
    },
    {
        "service_id": "SVC-C02",
        "name": "AetherCompute HighPerf",
        "category": "Compute",
        "latency": 25.0,
        "cost": 0.085,
        "availability": 99.95,
        "reliability": 99.80,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 25.0,
            "cost": 0.085,
            "availability": 99.95,
            "reliability": 99.80,
            "operational_status": "AVAILABLE",
        },
    },
    {
        "service_id": "SVC-C03",
        "name": "EcoCompute Budget",
        "category": "Compute",
        "latency": 120.0,
        "cost": 0.015,
        "availability": 98.80,
        "reliability": 97.50,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 120.0,
            "cost": 0.015,
            "availability": 98.80,
            "reliability": 97.50,
            "operational_status": "AVAILABLE",
        },
    },
    {
        "service_id": "SVC-C04",
        "name": "TitanCompute Enterprise",
        "category": "Compute",
        "latency": 55.0,
        "cost": 0.050,
        "availability": 99.85,
        "reliability": 99.90,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 55.0,
            "cost": 0.050,
            "availability": 99.85,
            "reliability": 99.90,
            "operational_status": "AVAILABLE",
        },
    },
    {
        "service_id": "SVC-C05",
        "name": "ZenithCompute Flex",
        "category": "Compute",
        "latency": 75.0,
        "cost": 0.028,
        "availability": 99.20,
        "reliability": 98.40,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 75.0,
            "cost": 0.028,
            "availability": 99.20,
            "reliability": 98.40,
            "operational_status": "AVAILABLE",
        },
    },
    {
        "service_id": "SVC-S01",
        "name": "PulseStore Standard",
        "category": "Storage",
        "latency": 35.0,
        "cost": 0.020,
        "availability": 99.90,
        "reliability": 99.60,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 35.0,
            "cost": 0.020,
            "availability": 99.90,
            "reliability": 99.60,
            "operational_status": "AVAILABLE",
        },
    },
    {
        "service_id": "SVC-S02",
        "name": "GlacierStore Archive",
        "category": "Storage",
        "latency": 160.0,
        "cost": 0.005,
        "availability": 99.10,
        "reliability": 99.90,
        "operational_status": "AVAILABLE",
        "baseline": {
            "latency": 160.0,
            "cost": 0.005,
            "availability": 99.10,
            "reliability": 99.90,
            "operational_status": "AVAILABLE",
        },
    },
]


def get_default_services() -> List[CloudService]:
    """Return a fresh list of candidate cloud services with baseline values."""
    return [CloudService.from_dict(s) for s in _INITIAL_SERVICES_DATA]


def compute_reference_bounds(services: List[CloudService]) -> Dict[str, Dict[str, float]]:
    """Compute baseline reference min/max bounds for each category.

    Using the original candidate baseline values ensures that normalized scores
    remain stable and directly comparable before and after failure injection.
    """
    bounds: Dict[str, Dict[str, float]] = {}
    categories = set(s.category for s in services)

    for cat in categories:
        cat_services = [s for s in services if s.category == cat]
        if not cat_services:
            continue

        latencies = [s.baseline["latency"] for s in cat_services]
        costs = [s.baseline["cost"] for s in cat_services]
        availabilities = [s.baseline["availability"] for s in cat_services]
        reliabilities = [s.baseline["reliability"] for s in cat_services]

        bounds[cat] = {
            "min_latency": min(latencies),
            "max_latency": max(latencies),
            "min_cost": min(costs),
            "max_cost": max(costs),
            "min_availability": min(availabilities),
            "max_availability": max(availabilities),
            "min_reliability": min(reliabilities),
            "max_reliability": max(reliabilities),
        }

    return bounds
