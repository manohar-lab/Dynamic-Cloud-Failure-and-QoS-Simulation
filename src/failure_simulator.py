"""Dynamic Failure Simulator for injecting QoS degradation and outages.

Supports deterministic failure events:
- Injecting latency spikes
- Simulating service outages
- Reducing availability
- Restoring individual services to baseline
- Resetting the entire simulation state to baseline
"""

from __future__ import annotations
import copy
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from src.service_registry import CloudService, get_default_services


class SimulationEvent:
    """Represents a logged simulation action and outcome."""

    def __init__(
        self,
        action: str,
        service_id: str,
        service_name: str,
        details: str,
        timestamp: Optional[str] = None,
    ):
        self.action = action
        self.service_id = service_id
        self.service_name = service_name
        self.details = details
        self.timestamp = timestamp or datetime.now().strftime("%H:%M:%S")

    def to_dict(self) -> Dict[str, str]:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "service_id": self.service_id,
            "service_name": self.service_name,
            "details": self.details,
        }


class FailureSimulator:
    """Manages service states and executes failure simulation actions."""

    def __init__(self, services: Optional[List[CloudService]] = None):
        """Initialize simulator with candidate services or fresh defaults."""
        self.services: Dict[str, CloudService] = {}
        target_services = services if services is not None else get_default_services()
        for s in target_services:
            self.services[s.service_id] = copy.deepcopy(s)
        self.event_log: List[SimulationEvent] = []

    def get_service(self, service_id: str) -> Optional[CloudService]:
        """Retrieve a service by ID."""
        return self.services.get(service_id)

    def get_all_services(self) -> List[CloudService]:
        """Return list of all current services."""
        return list(self.services.values())

    def get_services_by_category(self, category: str) -> List[CloudService]:
        """Return services belonging to the specified category."""
        return [s for s in self.services.values() if s.category == category]

    def inject_latency_spike(
        self,
        service_id: str,
        spike_ms: float = 100.0,
    ) -> Tuple[bool, str]:
        """Increase the latency of a service by spike_ms.

        Ensures latency remains a valid positive number.
        """
        service = self.get_service(service_id)
        if not service:
            return False, f"Service {service_id} not found."

        old_latency = service.latency
        spike = max(1.0, float(spike_ms))
        new_latency = round(old_latency + spike, 2)
        service.latency = new_latency

        msg = f"Latency spiked by +{spike:.1f}ms (from {old_latency:.1f}ms to {new_latency:.1f}ms)."
        self.event_log.append(
            SimulationEvent("LATENCY_SPIKE", service.service_id, service.name, msg)
        )
        return True, msg

    def simulate_outage(self, service_id: str) -> Tuple[bool, str]:
        """Mark a service as UNAVAILABLE, excluding it from candidate recommendations."""
        service = self.get_service(service_id)
        if not service:
            return False, f"Service {service_id} not found."

        old_status = service.operational_status
        service.operational_status = "UNAVAILABLE"

        msg = f"Outage triggered. Status changed from {old_status} to UNAVAILABLE."
        self.event_log.append(
            SimulationEvent("SERVICE_OUTAGE", service.service_id, service.name, msg)
        )
        return True, msg

    def reduce_availability(
        self,
        service_id: str,
        reduction_percentage: float = 20.0,
    ) -> Tuple[bool, str]:
        """Lower the availability percentage of a service, clamped to [0.0, 100.0]."""
        service = self.get_service(service_id)
        if not service:
            return False, f"Service {service_id} not found."

        old_avail = service.availability
        drop = max(0.1, float(reduction_percentage))
        new_avail = max(0.0, min(100.0, round(old_avail - drop, 2)))
        service.availability = new_avail

        msg = f"Availability reduced by -{drop:.1f}% (from {old_avail:.2f}% to {new_avail:.2f}%)."
        self.event_log.append(
            SimulationEvent("REDUCE_AVAILABILITY", service.service_id, service.name, msg)
        )
        return True, msg

    def restore_service(self, service_id: str) -> Tuple[bool, str]:
        """Restore a single service back to its baseline QoS and status (idempotent)."""
        service = self.get_service(service_id)
        if not service:
            return False, f"Service {service_id} not found."

        baseline = service.baseline
        service.latency = baseline["latency"]
        service.cost = baseline["cost"]
        service.availability = baseline["availability"]
        service.reliability = baseline["reliability"]
        service.operational_status = baseline["operational_status"]

        msg = f"Service restored to baseline QoS (Latency: {service.latency}ms, Status: {service.operational_status})."
        self.event_log.append(
            SimulationEvent("RESTORE_SERVICE", service.service_id, service.name, msg)
        )
        return True, msg

    def reset_simulation(self) -> Tuple[bool, str]:
        """Restore all services to baseline state and clear event history (idempotent)."""
        default_services = get_default_services()
        self.services = {s.service_id: s for s in default_services}
        self.event_log = [
            SimulationEvent(
                "RESET_SIMULATION",
                "ALL",
                "All Services",
                "All candidate services restored to baseline QoS configurations.",
            )
        ]
        return True, "Simulation successfully reset to baseline state."

    def get_event_logs(self) -> List[Dict[str, str]]:
        """Return list of logged events as dicts."""
        return [e.to_dict() for e in self.event_log]
