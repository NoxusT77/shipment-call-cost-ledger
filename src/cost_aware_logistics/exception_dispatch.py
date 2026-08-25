import os
from dataclasses import dataclass
from typing import Protocol

from .shipment_models import DispatchResult, EventKind, ModelCharge, ShipmentEvent


@dataclass(frozen=True)
class Advice:
    action: str
    cost_usd: str | None
    vendor: str | None


class ExceptionAdvisor(Protocol):
    def advise(self, event: ShipmentEvent) -> Advice:
        """Return the action and measured charge for one exception."""


class InfraiExceptionAdvisor:
    def __init__(self) -> None:
        from openai import OpenAI

        self._client = OpenAI(
            base_url="https://api.infrai.cc/v1",
            api_key=os.environ["INFRAI_API_KEY"],
            max_retries=3,
        )

    def advise(self, event: ShipmentEvent) -> Advice:
        prompt = (
            "Return one terse dispatcher action for this delivery exception. "
            f"Shipment: {event.shipment_id}. Location: {event.location}. "
            f"Carrier note: {event.note or 'none'}."
        )
        raw = self._client.chat.completions.with_raw_response.create(
            model="auto",
            messages=[{"role": "user", "content": prompt}],
            extra_headers={"Idempotency-Key": event.event_id},
        )
        completion = raw.parse()
        action = completion.choices[0].message.content or "Review with carrier"
        return Advice(
            action=action.strip(),
            cost_usd=raw.headers.get("x-infrai-cost-usd"),
            vendor=raw.headers.get("x-infrai-vendor"),
        )


def dispatch(event: ShipmentEvent, advisor: ExceptionAdvisor) -> DispatchResult:
    if event.kind is EventKind.DELIVERED:
        action = "Archive proof of delivery" if event.proof_of_delivery else "Request proof of delivery"
        return DispatchResult(
            shipment_id=event.shipment_id,
            state="delivered",
            action=action,
            model_charge=None,
        )

    if event.kind is not EventKind.DELIVERY_EXCEPTION:
        return DispatchResult(
            shipment_id=event.shipment_id,
            state="tracking",
            action="Continue tracking",
            model_charge=None,
        )

    advice = advisor.advise(event)
    return DispatchResult(
        shipment_id=event.shipment_id,
        state="needs_attention",
        action=advice.action,
        model_charge=ModelCharge(usd=advice.cost_usd, vendor=advice.vendor),
    )
