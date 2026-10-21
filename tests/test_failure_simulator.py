"""Unit tests for the Dynamic Failure Simulator."""

import pytest
from src.failure_simulator import FailureSimulator
from src.service_registry import get_default_services


def test_latency_spike():
    """Verify latency injection increases latency and remains positive."""
    sim = FailureSimulator()
    target_id = "SVC-C01"
    svc = sim.get_service(target_id)
    initial_latency = svc.latency

    success, msg = sim.inject_latency_spike(target_id, spike_ms=150.0)
    assert success is True
    assert svc.latency == initial_latency + 150.0
    assert svc.latency > 0

    logs = sim.get_event_logs()
    assert len(logs) == 1
    assert logs[0]["action"] == "LATENCY_SPIKE"
    assert logs[0]["service_id"] == target_id


def test_simulate_outage():
    """Verify simulating outage marks service UNAVAILABLE."""
    sim = FailureSimulator()
    target_id = "SVC-C02"
    svc = sim.get_service(target_id)
    assert svc.operational_status == "AVAILABLE"

    success, msg = sim.simulate_outage(target_id)
    assert success is True
    assert svc.operational_status == "UNAVAILABLE"

    logs = sim.get_event_logs()
    assert any(log["action"] == "SERVICE_OUTAGE" and log["service_id"] == target_id for log in logs)


def test_reduce_availability_and_bounds():
    """Verify availability reduction is clamped to [0.0, 100.0]."""
    sim = FailureSimulator()
    target_id = "SVC-C03"
    svc = sim.get_service(target_id)
    initial_avail = svc.availability

    # Step 1: Normal reduction
    success, _ = sim.reduce_availability(target_id, reduction_percentage=20.0)
    assert success is True
    assert pytest.approx(svc.availability) == initial_avail - 20.0

    # Step 2: Severe reduction that exceeds remaining availability
    success, _ = sim.reduce_availability(target_id, reduction_percentage=150.0)
    assert success is True
    assert svc.availability == 0.0  # Clamped to 0.0


def test_restore_service_idempotence():
    """Verify restoring a modified service returns it to baseline QoS (idempotent)."""
    sim = FailureSimulator()
    target_id = "SVC-C01"
    svc = sim.get_service(target_id)
    baseline_latency = svc.baseline["latency"]
    baseline_status = svc.baseline["operational_status"]

    # Degrade and outage
    sim.inject_latency_spike(target_id, 200.0)
    sim.simulate_outage(target_id)
    assert svc.latency != baseline_latency
    assert svc.operational_status == "UNAVAILABLE"

    # First restore
    success1, _ = sim.restore_service(target_id)
    assert success1 is True
    assert svc.latency == baseline_latency
    assert svc.operational_status == baseline_status

    # Second restore (idempotent)
    success2, _ = sim.restore_service(target_id)
    assert success2 is True
    assert svc.latency == baseline_latency
    assert svc.operational_status == baseline_status


def test_reset_simulation_idempotence():
    """Verify resetting restores all services to pristine state (idempotent)."""
    sim = FailureSimulator()
    # Modify multiple services
    sim.simulate_outage("SVC-C01")
    sim.inject_latency_spike("SVC-C02", 300.0)
    sim.reduce_availability("SVC-C03", 50.0)

    # First reset
    sim.reset_simulation()
    for s in sim.get_all_services():
        assert s.operational_status == "AVAILABLE"
        assert s.latency == s.baseline["latency"]
        assert s.availability == s.baseline["availability"]

    # Second reset (idempotent)
    sim.reset_simulation()
    for s in sim.get_all_services():
        assert s.operational_status == "AVAILABLE"
        assert s.latency == s.baseline["latency"]


def test_repeated_actions_do_not_accumulate_drift():
    """Verify that repeatedly restoring and resetting maintains pristine values without drift."""
    sim = FailureSimulator()
    target_id = "SVC-C01"

    # Repeatedly modify, restore, and check
    for _ in range(5):
        sim.inject_latency_spike(target_id, 50.0)
        sim.reduce_availability(target_id, 10.0)
        sim.restore_service(target_id)
        svc = sim.get_service(target_id)
        assert svc.latency == svc.baseline["latency"]
        assert svc.availability == svc.baseline["availability"]
        assert svc.operational_status == svc.baseline["operational_status"]

    # Repeated resets
    for _ in range(3):
        sim.reset_simulation()
        for s in sim.get_all_services():
            assert s.latency == s.baseline["latency"]
            assert s.cost == s.baseline["cost"]
            assert s.availability == s.baseline["availability"]
            assert s.reliability == s.baseline["reliability"]
            assert s.operational_status == s.baseline["operational_status"]

