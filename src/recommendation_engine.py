"""Recommendation Engine for selecting the optimal cloud service based on QoS.

Provides transparent, deterministic ranking and explanation of selected candidates,
while excluding unavailable and failed services.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from src.service_registry import CloudService
from src.qos_evaluator import QoSEvaluator, MetricScores


@dataclass
class RecommendationResult:
    """Encapsulates the decision of the recommendation engine."""
    category: str
    selected_service: Optional[CloudService]
    selected_scores: Optional[MetricScores]
    ranked_eligible: List[Tuple[CloudService, MetricScores]]
    excluded_services: List[Tuple[CloudService, str]]
    selection_reason: str
    has_eligible_service: bool
    status_message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "selected_service_id": self.selected_service.service_id if self.selected_service else None,
            "selected_service_name": self.selected_service.name if self.selected_service else None,
            "qos_score": self.selected_scores.qos_score if self.selected_scores else None,
            "selection_reason": self.selection_reason,
            "has_eligible_service": self.has_eligible_service,
            "status_message": self.status_message,
            "num_eligible": len(self.ranked_eligible),
            "num_excluded": len(self.excluded_services),
        }


class RecommendationEngine:
    """Transparent QoS-based cloud service recommendation engine."""

    def __init__(self, evaluator: QoSEvaluator):
        self.evaluator = evaluator

    def recommend(
        self,
        services: List[CloudService],
        category: str,
        weights: Optional[Dict[str, float]] = None,
        previously_selected_id: Optional[str] = None,
    ) -> RecommendationResult:
        """Evaluate services in category and recommend the highest-scoring available candidate.

        - Filters by category.
        - Excludes unavailable services.
        - Deterministically ranks eligible services by aggregate QoS score (with service_id tiebreaker).
        - Generates clear reasoning and breakdown.
        """
        # Step 1: Filter by category
        cat_services = [s for s in services if s.category == category]
        if not cat_services:
            return RecommendationResult(
                category=category,
                selected_service=None,
                selected_scores=None,
                ranked_eligible=[],
                excluded_services=[],
                selection_reason=f"No services found registered under category '{category}'.",
                has_eligible_service=False,
                status_message=f"Category '{category}' has no candidate services registered.",
            )

        # Step 2: Separate eligible from excluded
        eligible: List[CloudService] = []
        excluded: List[Tuple[CloudService, str]] = []

        for s in cat_services:
            if s.operational_status == "UNAVAILABLE":
                reason = "Service is marked UNAVAILABLE (simulated outage/down)."
                excluded.append((s, reason))
            else:
                eligible.append(s)

        # Step 3: Handle all-unavailable edge case
        if not eligible:
            msg = f"All {len(cat_services)} service(s) in category '{category}' are currently UNAVAILABLE."
            return RecommendationResult(
                category=category,
                selected_service=None,
                selected_scores=None,
                ranked_eligible=[],
                excluded_services=excluded,
                selection_reason="No eligible candidate service available. Every candidate is in an outage/unavailable state.",
                has_eligible_service=False,
                status_message=msg,
            )

        # Step 4: Evaluate QoS for eligible services
        scored_pairs: List[Tuple[CloudService, MetricScores]] = []
        for s in eligible:
            score = self.evaluator.evaluate_service(s, weights)
            scored_pairs.append((s, score))

        # Deterministic sort: descending QoS score, then ascending service_id for ties
        scored_pairs.sort(key=lambda item: (-item[1].qos_score, item[0].service_id))

        top_service, top_score = scored_pairs[0]

        # Step 5: Construct transparent explanation
        reasons = [
            f"Selected as optimal service with highest aggregate QoS score of {top_score.qos_score:.4f}.",
            f"Latency: {top_service.latency:.1f}ms (score: {top_score.latency_score:.2f}) | "
            f"Cost: ${top_service.cost:.3f} (score: {top_score.cost_score:.2f}) | "
            f"Availability: {top_service.availability:.2f}% (score: {top_score.availability_score:.2f}) | "
            f"Reliability: {top_service.reliability:.2f}% (score: {top_score.reliability_score:.2f}).",
        ]

        # Explain reselection if previous top choice changed or failed
        if previously_selected_id and previously_selected_id != top_service.service_id:
            prev_svc = next((s for s in cat_services if s.service_id == previously_selected_id), None)
            if prev_svc:
                if prev_svc.operational_status == "UNAVAILABLE":
                    reasons.append(
                        f"Reselection trigger: Prior choice '{prev_svc.name}' ({prev_svc.service_id}) is currently UNAVAILABLE."
                    )
                else:
                    prev_score = self.evaluator.evaluate_service(prev_svc, weights)
                    reasons.append(
                        f"Reselection trigger: Prior choice '{prev_svc.name}' ({prev_svc.service_id}) QoS score ({prev_score.qos_score:.4f}) dropped below '{top_service.name}' ({top_score.qos_score:.4f})."
                    )

        reason_text = " ".join(reasons)
        status_msg = f"Successfully recommended '{top_service.name}' ({top_service.service_id}) out of {len(eligible)} eligible services."

        return RecommendationResult(
            category=category,
            selected_service=top_service,
            selected_scores=top_score,
            ranked_eligible=scored_pairs,
            excluded_services=excluded,
            selection_reason=reason_text,
            has_eligible_service=True,
            status_message=status_msg,
        )
