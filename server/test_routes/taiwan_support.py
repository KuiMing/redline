"""Test-only route for the Taiwan support-card (臺灣奧援) proof state.

Thin wrapper around the shared setup-support-proof route with the
support_name defaulted to 臺灣奧援.
"""

from collections.abc import Callable

from fastapi import APIRouter


class TaiwanSupportTestRoutes:
    def __init__(self, support_proof_provider: Callable[[dict], dict]):
        self._support_proof_provider = support_proof_provider
        self.router = APIRouter()
        self.router.add_api_route(
            "/test/setup-taiwan-support-proof",
            self.test_setup_taiwan_support_proof,
            methods=["POST"],
        )

    def test_setup_taiwan_support_proof(self, payload: dict):
        scoped = dict(payload or {})
        scoped.setdefault("support_name", "臺灣奧援")
        return self._support_proof_provider(scoped)
