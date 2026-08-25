from fastapi import Depends, FastAPI, HTTPException
from openai import APIConnectionError, APIStatusError

from .exception_dispatch import ExceptionAdvisor, InfraiExceptionAdvisor, dispatch
from .shipment_models import DispatchResult, ShipmentEvent

service = FastAPI(title="Shipment exception cost ledger")


def get_advisor() -> ExceptionAdvisor:
    return InfraiExceptionAdvisor()


@service.post("/shipment-events", response_model=DispatchResult)
def accept_event(
    event: ShipmentEvent,
    advisor: ExceptionAdvisor = Depends(get_advisor),
) -> DispatchResult:
    try:
        return dispatch(event, advisor)
    except APIStatusError as exc:
        if 400 <= exc.status_code < 500:
            detail = "Model request was rejected"
            try:
                body = exc.response.json()
                detail = body.get("error", {}).get("message", detail)
            except ValueError:
                pass
            raise HTTPException(status_code=exc.status_code, detail=detail) from exc
        raise
    except APIConnectionError as exc:
        raise HTTPException(status_code=503, detail="Model service could not be reached") from exc

