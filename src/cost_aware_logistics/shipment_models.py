from dataclasses import dataclass
from datetime import datetime
from enum import Enum

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:
    BaseModel = None


class EventKind(str, Enum):
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    DELIVERY_EXCEPTION = "delivery_exception"


if BaseModel is not None:
    class ProofOfDelivery(BaseModel):
        name: str = Field(min_length=1)
        media_type: str = Field(pattern=r"^(image/|application/pdf)")
        sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


    class ShipmentEvent(BaseModel):
        event_id: str = Field(min_length=1)
        shipment_id: str = Field(min_length=1)
        kind: EventKind
        occurred_at: datetime
        location: str = Field(min_length=1)
        note: str = ""
        proof_of_delivery: ProofOfDelivery | None = None


    class ModelCharge(BaseModel):
        usd: str | None
        vendor: str | None


    class DispatchResult(BaseModel):
        shipment_id: str
        state: str
        action: str
        model_charge: ModelCharge | None
else:
    @dataclass
    class ProofOfDelivery:
        name: str
        media_type: str
        sha256: str


    @dataclass
    class ShipmentEvent:
        event_id: str
        shipment_id: str
        kind: EventKind
        occurred_at: datetime
        location: str
        note: str = ""
        proof_of_delivery: ProofOfDelivery | None = None

        @classmethod
        def model_validate(cls, data: dict) -> "ShipmentEvent":
            values = dict(data)
            values["kind"] = EventKind(values["kind"])
            values["occurred_at"] = datetime.fromisoformat(
                values["occurred_at"].replace("Z", "+00:00")
            )
            if values.get("proof_of_delivery") is not None:
                values["proof_of_delivery"] = ProofOfDelivery(**values["proof_of_delivery"])
            return cls(**values)


    @dataclass
    class ModelCharge:
        usd: str | None
        vendor: str | None


    @dataclass
    class DispatchResult:
        shipment_id: str
        state: str
        action: str
        model_charge: ModelCharge | None
