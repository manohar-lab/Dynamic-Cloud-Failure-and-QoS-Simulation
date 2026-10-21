"""Unit tests for the QoS Evaluation Engine."""

import pytest
from src.service_registry import CloudService, get_default_services, compute_reference_bounds
from src.qos_evaluator import (
    QoSEvaluator,
    normalize_lower_is_better,
    normalize_higher_is_better,
    validate_and_normalize_weights,
)


def test_normalize_lower_is_better():
    """Verify lower-is-better normalization formula: (max - val) / (max - min)."""
    # Mid-range: min=20, max=100, val=60 -> (100 - 60) / 80 = 40/80 = 0.5
    assert normalize_lower_is_better(60.0, 20.0, 100.0) == 0.5
    # Best case: val == min -> (100 - 20) / 80 = 1.0
    assert normalize_lower_is_better(20.0, 20.0, 100.0) == 1.0
    # Worst case: val == max -> (100 - 100) / 80 = 0.0
    assert normalize_lower_is_better(100.0, 20.0, 100.0) == 0.0
    # Clamping: val > max -> should clamp to 0.0
    assert normalize_lower_is_better(150.0, 20.0, 100.0) == 0.0
    # Clamping: val < min -> should clamp to 1.0
    assert normalize_lower_is_better(10.0, 20.0, 100.0) == 1.0


def test_normalize_lower_is_better_equal_min_max():
    """Verify handling when max == min without division by zero."""
    assert normalize_lower_is_better(50.0, 50.0, 50.0) == 1.0
    assert normalize_lower_is_better(60.0, 50.0, 50.0) == 1.0


def test_normalize_higher_is_better():
    """Verify higher-is-better normalization formula: (val - min) / (max - min)."""
    # Mid-range: min=90, max=100, val=95 -> (95 - 90) / 10 = 0.5
    assert normalize_higher_is_better(95.0, 90.0, 100.0) == 0.5
    # Best case: val == max -> 1.0
    assert normalize_higher_is_better(100.0, 90.0, 100.0) == 1.0
    # Worst case: val == min -> 0.0
    assert normalize_higher_is_better(90.0, 90.0, 100.0) == 0.0
    # Clamping: val > max -> clamp to 1.0
    assert normalize_higher_is_better(105.0, 90.0, 100.0) == 1.0
    # Clamping: val < min -> clamp to 0.0
    assert normalize_higher_is_better(80.0, 90.0, 100.0) == 0.0


def test_normalize_higher_is_better_equal_min_max():
    """Verify higher-is-better handling when max == min without division by zero."""
    assert normalize_higher_is_better(99.0, 99.0, 99.0) == 1.0
    assert normalize_higher_is_better(85.0, 99.0, 99.0) == 1.0


def test_weight_validation_and_normalization():
    """Verify weight validation and sum-to-1 normalization."""
    # Case 1: unnormalized positive weights (e.g., 2, 2, 2, 2 -> 0.25 each)
    weights = {"latency": 2.0, "cost": 2.0, "availability": 2.0, "reliability": 2.0}
    normalized = validate_and_normalize_weights(weights)
    assert pytest.approx(sum(normalized.values())) == 1.0
    assert pytest.approx(normalized["latency"]) == 0.25

    # Case 2: Unequal weights
    weights2 = {"latency": 4.0, "cost": 1.0, "availability": 3.0, "reliability": 2.0}
    normalized2 = validate_and_normalize_weights(weights2)
    assert pytest.approx(sum(normalized2.values())) == 1.0
    assert pytest.approx(normalized2["latency"]) == 0.40
    assert pytest.approx(normalized2["cost"]) == 0.10

    # Case 3: Negative weights clamped to zero
    weights3 = {"latency": -5.0, "cost": 1.0, "availability": 1.0, "reliability": 0.0}
    normalized3 = validate_and_normalize_weights(weights3)
    assert normalized3["latency"] == 0.0
    assert pytest.approx(normalized3["cost"]) == 0.5
    assert pytest.approx(normalized3["availability"]) == 0.5

    # Case 4: All zero weights fallback to equal weights (0.25 each)
    weights_zero = {"latency": 0.0, "cost": 0.0, "availability": 0.0, "reliability": 0.0}
    normalized_zero = validate_and_normalize_weights(weights_zero)
    assert pytest.approx(sum(normalized_zero.values())) == 1.0
    for v in normalized_zero.values():
        assert pytest.approx(v) == 0.25


def test_weighted_score_calculation():
    """Verify total weighted QoS score calculation on candidate service."""
    services = get_default_services()
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)

    # Let's test SVC-C02: latency=25ms (min=25, max=120) -> lat_score = 1.0
    # availability=99.95 (min=98.80, max=99.95) -> avail_score = 1.0
    svc = next(s for s in services if s.service_id == "SVC-C02")
    scores = evaluator.evaluate_service(
        svc,
        weights={"latency": 0.5, "cost": 0.0, "availability": 0.5, "reliability": 0.0},
    )

    assert scores.latency_score == 1.0
    assert scores.availability_score == 1.0
    assert scores.qos_score == 1.0
    assert 0.0 <= scores.qos_score <= 1.0


def test_evaluate_all_services():
    """Verify evaluate_all returns scores for every registered service."""
    services = get_default_services()
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)

    results = evaluator.evaluate_all(services)
    assert len(results) == len(services)
    for s in services:
        assert s.service_id in results
        assert 0.0 <= results[s.service_id].qos_score <= 1.0


def test_latency_and_cost_lower_is_better_sensitivity():
    """Verify that reducing latency or cost strictly increases the QoS score."""
    services = get_default_services()
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)

    svc = next(s for s in services if s.service_id == "SVC-C01")
    initial_score = evaluator.evaluate_service(svc, weights={"latency": 0.5, "cost": 0.5, "availability": 0.0, "reliability": 0.0})

    # Decreasing latency should improve score
    svc_improved_lat = CloudService.from_dict(svc.to_dict())
    svc_improved_lat.latency = max(25.0, svc.latency - 15.0)
    improved_lat_score = evaluator.evaluate_service(svc_improved_lat, weights={"latency": 0.5, "cost": 0.5, "availability": 0.0, "reliability": 0.0})
    assert improved_lat_score.latency_score > initial_score.latency_score
    assert improved_lat_score.qos_score > initial_score.qos_score

    # Decreasing cost should improve score
    svc_improved_cost = CloudService.from_dict(svc.to_dict())
    svc_improved_cost.cost = max(0.015, svc.cost - 0.010)
    improved_cost_score = evaluator.evaluate_service(svc_improved_cost, weights={"latency": 0.5, "cost": 0.5, "availability": 0.0, "reliability": 0.0})
    assert improved_cost_score.cost_score > initial_score.cost_score
    assert improved_cost_score.qos_score > initial_score.qos_score


def test_availability_and_reliability_higher_is_better_sensitivity():
    """Verify that increasing availability or reliability strictly increases the QoS score."""
    services = get_default_services()
    bounds = compute_reference_bounds(services)
    evaluator = QoSEvaluator(bounds)

    svc = next(s for s in services if s.service_id == "SVC-C03")
    initial_score = evaluator.evaluate_service(svc, weights={"latency": 0.0, "cost": 0.0, "availability": 0.5, "reliability": 0.5})

    # Increasing availability should improve score
    svc_improved_avail = CloudService.from_dict(svc.to_dict())
    svc_improved_avail.availability = min(99.95, svc.availability + 0.5)
    improved_avail_score = evaluator.evaluate_service(svc_improved_avail, weights={"latency": 0.0, "cost": 0.0, "availability": 0.5, "reliability": 0.5})
    assert improved_avail_score.availability_score > initial_score.availability_score
    assert improved_avail_score.qos_score > initial_score.qos_score

    # Increasing reliability should improve score
    svc_improved_rel = CloudService.from_dict(svc.to_dict())
    svc_improved_rel.reliability = min(99.90, svc.reliability + 1.0)
    improved_rel_score = evaluator.evaluate_service(svc_improved_rel, weights={"latency": 0.0, "cost": 0.0, "availability": 0.5, "reliability": 0.5})
    assert improved_rel_score.reliability_score > initial_score.reliability_score
    assert improved_rel_score.qos_score > initial_score.qos_score

