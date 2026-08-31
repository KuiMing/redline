import pydantic
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server import main
from server.test_routes.taiwan_support import TaiwanSupportTestRoutes


def _make_app(provider):
    routes = TaiwanSupportTestRoutes(provider)
    app = FastAPI()
    app.include_router(routes.router)
    return app


def _effective_app_routes():
    for route in main.app.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from original_router.routes
        else:
            yield route


def test_taiwan_support_defaults_support_name_when_missing():
    calls = []

    def fake_support(payload):
        calls.append(payload)
        return {"echo": payload}

    result = TaiwanSupportTestRoutes(fake_support).test_setup_taiwan_support_proof({})

    assert result == {"echo": {"support_name": "臺灣奧援"}}
    assert calls == [{"support_name": "臺灣奧援"}]


def test_taiwan_support_none_payload_still_defaults_support_name():
    def fake_support(payload):
        return {"echo": payload}

    result = TaiwanSupportTestRoutes(fake_support).test_setup_taiwan_support_proof(None)

    assert result == {"echo": {"support_name": "臺灣奧援"}}


def test_taiwan_support_preserves_extra_fields_and_explicit_override():
    def fake_support(payload):
        return {"echo": payload}

    result = TaiwanSupportTestRoutes(fake_support).test_setup_taiwan_support_proof(
        {"support_name": "自訂奧援", "tier": 3, "faction_id": "liberals"}
    )

    assert result == {
        "echo": {"support_name": "自訂奧援", "tier": 3, "faction_id": "liberals"}
    }


def test_taiwan_support_does_not_mutate_caller_payload_dict():
    caller_payload = {"tier": 1}

    def fake_support(payload):
        return {"echo": payload}

    TaiwanSupportTestRoutes(fake_support).test_setup_taiwan_support_proof(
        caller_payload
    )

    assert caller_payload == {"tier": 1}


def test_main_taiwan_support_delegates_to_shared_support_route(monkeypatch):
    calls = []

    def fake_support_proof(payload):
        calls.append(payload)
        return {"support_name": payload.get("support_name")}

    taiwan_support_instance = main.test_setup_taiwan_support_proof.__self__
    monkeypatch.setattr(main, "test_setup_support_proof", fake_support_proof)
    monkeypatch.setattr(
        taiwan_support_instance, "_support_proof_provider", fake_support_proof
    )

    response = TestClient(main.app).post("/test/setup-taiwan-support-proof", json={})
    assert response.status_code == 200
    assert response.json() == {"support_name": "臺灣奧援"}
    assert calls == [{"support_name": "臺灣奧援"}]

    direct = main.test_setup_taiwan_support_proof({"tier": 3})
    assert direct == {"support_name": "臺灣奧援"}
    assert callable(main.test_setup_taiwan_support_proof)


def test_taiwan_support_http_openapi_and_route_order():
    def fake_support(payload):
        return {"success": True, "support_name": payload.get("support_name")}

    app = _make_app(fake_support)
    client = TestClient(app)
    response = client.post("/test/setup-taiwan-support-proof", json={})
    assert response.status_code == 200
    assert response.json() == {"success": True, "support_name": "臺灣奧援"}
    assert client.post("/test/setup-taiwan-support-proof").status_code == 422
    list_response = client.post("/test/setup-taiwan-support-proof", json=[])
    assert list_response.status_code == (
        422 if int(pydantic.VERSION.split(".")[0]) >= 2 else 200
    )

    operation = app.openapi()["paths"]["/test/setup-taiwan-support-proof"]["post"]
    assert operation["summary"] == "Test Setup Taiwan Support Proof"
    assert operation["operationId"].startswith("test_setup_taiwan_support_proof_")
    assert operation["requestBody"]["required"] is True

    routes = list(_effective_app_routes())
    matching = [
        route
        for route in routes
        if getattr(route, "path", None) == "/test/setup-taiwan-support-proof"
    ]
    assert len(matching) == 1
    assert getattr(matching[0], "methods", None) == {"POST"}
    paths = [getattr(route, "path", None) for route in routes]
    index = paths.index("/test/setup-taiwan-support-proof")
    assert paths[index - 1] == "/test/setup-support-proof"
    assert paths[index + 1] == "/test/setup-bait-exhaustion-ui"
