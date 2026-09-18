from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.contact_delivery import (
    ContactDeliveryError,
    ContactMessage,
    DisabledContactDelivery,
    get_contact_delivery,
)


class FakeDelivery:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[ContactMessage] = []

    def deliver(self, message: ContactMessage) -> None:
        if self.fail:
            raise ContactDeliveryError("simulated failure")
        self.messages.append(message)


def valid_payload() -> dict[str, str]:
    return {
        "name": "Demo Visitor",
        "email": "visitor@example.com",
        "company": "Example Studio",
        "subject": "Project conversation",
        "message": "I would like to learn more about the implementation approach.",
        "website": "",
    }


def test_contact_submit_uses_delivery_without_persistence() -> None:
    delivery = FakeDelivery()
    app.dependency_overrides[get_contact_delivery] = lambda: delivery
    try:
        response = TestClient(app).post("/api/v1/contact", json=valid_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["accepted"] is True
    assert len(delivery.messages) == 1
    assert delivery.messages[0].email == "visitor@example.com"


def test_contact_validation_rejects_invalid_and_oversized_values() -> None:
    client = TestClient(app)
    invalid_email = valid_payload() | {"email": "not-an-email"}
    short_message = valid_payload() | {"message": "Too short"}
    newline_subject = valid_payload() | {"subject": "Hello\nBcc: bad@example.com"}

    assert client.post("/api/v1/contact", json=invalid_email).status_code == 422
    assert client.post("/api/v1/contact", json=short_message).status_code == 422
    assert client.post("/api/v1/contact", json=newline_subject).status_code == 422


def test_contact_honeypot_returns_success_without_delivery() -> None:
    delivery = FakeDelivery()
    app.dependency_overrides[get_contact_delivery] = lambda: delivery
    try:
        response = TestClient(app).post(
            "/api/v1/contact",
            json=valid_payload() | {"website": "https://spam.example"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert delivery.messages == []


def test_contact_disabled_and_delivery_failure_are_safe() -> None:
    client = TestClient(app)
    for delivery in (DisabledContactDelivery(), FakeDelivery(fail=True)):
        app.dependency_overrides[get_contact_delivery] = lambda item=delivery: item
        try:
            response = client.post("/api/v1/contact", json=valid_payload())
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 503
        assert response.json() == {
            "detail": (
                "Contact delivery is temporarily unavailable. Please try again later."
            )
        }
