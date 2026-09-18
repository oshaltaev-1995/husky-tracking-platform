from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.contact import ContactRequest, ContactResponse
from app.services.contact_delivery import (
    ContactDelivery,
    ContactDeliveryError,
    ContactMessage,
    get_contact_delivery,
)

router = APIRouter()
Delivery = Annotated[ContactDelivery, Depends(get_contact_delivery)]


@router.post(
    "/contact",
    response_model=ContactResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_contact(payload: ContactRequest, delivery: Delivery) -> ContactResponse:
    # A filled honeypot receives the same public success response but is not delivered.
    if payload.website:
        return ContactResponse(
            accepted=True,
            message="Thanks — your message has been received.",
        )

    try:
        delivery.deliver(
            ContactMessage(
                name=payload.name,
                email=payload.email,
                company=payload.company,
                subject=payload.subject,
                message=payload.message,
            )
        )
    except ContactDeliveryError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Contact delivery is temporarily unavailable. Please try again later."
            ),
        ) from error

    return ContactResponse(
        accepted=True,
        message="Thanks — your message has been received.",
    )
