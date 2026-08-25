from datetime import datetime, timezone

from cost_aware_logistics.exception_dispatch import Advice, dispatch
from cost_aware_logistics.shipment_models import EventKind, ShipmentEvent


class FixedAdvisor:
    def advise(self, event: ShipmentEvent) -> Advice:
        assert event.note == "Recipient unavailable"
        return Advice(
            action="Schedule delivery after recipient confirmation",
            cost_usd="0.0017",
            vendor="example-provider",
        )


def test_exception_moves_to_attention_and_records_exact_call_cost() -> None:
    event = ShipmentEvent(
        event_id="evt_1042",
        shipment_id="SHP-1042",
        kind=EventKind.DELIVERY_EXCEPTION,
        occurred_at=datetime(2026, 8, 18, 9, 30, tzinfo=timezone.utc),
        location="Shanghai depot",
        note="Recipient unavailable",
    )

    result = dispatch(event, FixedAdvisor())

    assert result.state == "needs_attention"
    assert result.action == "Schedule delivery after recipient confirmation"
    assert result.model_charge is not None
    assert result.model_charge.usd == "0.0017"


def test_delivered_event_archives_proof_without_model_call() -> None:
    class AdvisorMustStayIdle:
        def advise(self, event: ShipmentEvent) -> Advice:
            raise AssertionError("delivered events must not call the model")

    event = ShipmentEvent.model_validate(
        {
            "event_id": "evt_1043",
            "shipment_id": "SHP-1043",
            "kind": "delivered",
            "occurred_at": "2026-08-18T10:00:00Z",
            "location": "Customer address",
            "proof_of_delivery": {
                "name": "signed-receipt.pdf",
                "media_type": "application/pdf",
                "sha256": "a" * 64,
            },
        }
    )

    result = dispatch(event, AdvisorMustStayIdle())

    assert result.state == "delivered"
    assert result.action == "Archive proof of delivery"
    assert result.model_charge is None

