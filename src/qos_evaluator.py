"""QoS Evaluation Engine for cloud services.

Provides normalization, criteria weighting, and aggregate QoS score computation.

Normalization Strategy:
-----------------------
To maintain consistency and comparability across dynamic failure events, metric
normalization is performed against baseline reference bounds established by the
candidate service registry (rather than the current dynamic sample min/max).
Without fixed baseline bounds, degrading one service would artificially shift the
min/max scale and alter the normalized scores of healthy services that did not change.

Formulas:
- Lower-is-better (Latency, Cost):
    score = (max_ref - value) / (max_ref - min_ref)
- Higher-is-better (Availability, Reliability):
    score = (value - min_ref) / (max_ref - min_ref)

Edge Cases:
- Equal Min and Max (max_ref == min_ref): score defaults to 1.0, avoiding division by zero.
- Values outside reference bounds (e.g., latency spikes above max_ref or availability
  drops below min_ref): normalized score is clamped to the range [0.0, 1.0].
- Weight normalization: user weights are validated (non-negative) and normalized to sum to 1.0.
  If all weights are zero, equal weights (0.25 each) are applied.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from src.service_registry import CloudService


@dataclass
class MetricScores:
    """Normalized individual metric scores and aggregate QoS score for a service."""
    service_id: str
    latency_score: float
    cost_score: float
    availability_score: float
    reliability_score: float
    qos_score: float


DEFAULT_WEIGHTS: Dict[str, float] = {
    "latency": 0.30,
    "cost": 0.20,
    "availability": 0.30,
    "reliability": 0.20,
}


def normalize_lower_is_better(value: float, min_val: float, max_val: float) -> float:
    """Normalize a metric where lower is better (e.g., Latency, Cost).

    score = (max_val - value) / (max_val - min_val)
    Clamped to [0.0, 1.0]. If max_val == min_val, returns 1.0.
    """
    if max_val <= min_val:
        return 1.0
    score = (max_val - value) / (max_val - min_val)
    return max(0.0, min(1.0, float(score)))


def normalize_higher_is_better(value: float, min_val: float, max_val: float) -> float:
    """Normalize a metric where higher is better (e.g., Availability, Reliability).

    score = (value - min_val) / (max_val - min_val)
    Clamped to [0.0, 1.0]. If max_val == min_val, returns 1.0.
    """
    if max_val <= min_val:
        return 1.0
    score = (value - min_val) / (max_val - min_val)
    return max(0.0, min(1.0, float(score)))


def validate_and_normalize_weights(weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Validate that weights are non-negative and normalize them to sum to 1.0.

    If weights are None, negative, or sum to zero, safe fallbacks are applied.
    """
    if not weights:
        weights = DEFAULT_WEIGHTS

    clean_weights = {}
    for key in ["latency", "cost", "availability", "reliability"]:
        val = weights.get(key, 0.0)
        clean_weights[key] = max(0.0, float(val))

    total = sum(clean_weights.values())
    if total <= 0.0:
        # Equal weights fallback
        return {"latency": 0.25, "cost": 0.25, "availability": 0.25, "reliability": 0.25}

    return {k: v / total for k, v in clean_weights.items()}


class QoSEvaluator:
    """Evaluates and scores cloud services based on multi-criteria QoS metrics."""

    def __init__(self, reference_bounds: Optional[Dict[str, Dict[str, float]]] = None):
        """Initialize evaluator with reference baseline bounds."""
        self.reference_bounds = reference_bounds or {}

    def set_reference_bounds(self, reference_bounds: Dict[str, Dict[str, float]]) -> None:
        """Update reference baseline bounds."""
        self.reference_bounds = reference_bounds

    def evaluate_service(
        self,
        service: CloudService,
        weights: Optional[Dict[str, float]] = None,
        custom_bounds: Optional[Dict[str, float]] = None,
    ) -> MetricScores:
        """Calculate normalized metric scores and total weighted QoS score for a single service."""
        norm_weights = validate_and_normalize_weights(weights)

        bounds = custom_bounds or self.reference_bounds.get(service.category, {})
        min_lat = bounds.get("min_latency", service.latency)
        max_lat = bounds.get("max_latency", service.latency)
        min_cost = bounds.get("min_cost", service.cost)
        max_cost = bounds.get("max_cost", service.cost)
        min_avail = bounds.get("min_availability", service.availability)
        max_avail = bounds.get("max_availability", service.availability)
        min_rel = bounds.get("min_reliability", service.reliability)
        max_rel = bounds.get("max_reliability", service.reliability)

        lat_score = normalize_lower_is_better(service.latency, min_lat, max_lat)
        cost_score = normalize_lower_is_better(service.cost, min_cost, max_cost)
        avail_score = normalize_higher_is_better(service.availability, min_avail, max_avail)
        rel_score = normalize_higher_is_better(service.reliability, min_rel, max_rel)

        total_qos = (
            norm_weights["latency"] * lat_score
            + norm_weights["cost"] * cost_score
            + norm_weights["availability"] * avail_score
            + norm_weights["reliability"] * rel_score
        )
        total_qos = max(0.0, min(1.0, round(total_qos, 4)))

        return MetricScores(
            service_id=service.service_id,
            latency_score=round(lat_score, 4),
            cost_score=round(cost_score, 4),
            availability_score=round(avail_score, 4),
            reliability_score=round(rel_score, 4),
            qos_score=total_qos,
        )

    def evaluate_all(
        self,
        services: List[CloudService],
        weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, MetricScores]:
        """Evaluate a list of services and return a mapping of service_id -> MetricScores."""
        return {s.service_id: self.evaluate_service(s, weights) for s in services}
