"""Tests for the arch-report P1 performance hardening:
- /ws/alerts + /ws/command-centre single-producer broadcast (one payload
  build per tick for all clients; webhooks dispatched once, not per client)
- API-key bcrypt verify moved off the event loop + 60s positive cache
- Stripe SDK + sync DB sessions run via asyncio.to_thread
"""
import asyncio

import core.auth as auth_mod
from core.auth import _api_key_cache, verify_api_key_cached


class _FakeWS:
    def __init__(self):
        self.sent = []

    async def accept(self):
        pass

    async def send_json(self, payload):
        self.sent.append(payload)


class TestPushBroadcaster:
    def test_fanout_single_producer(self):
        """All clients receive every tick; payload built once per tick."""

        async def main():
            from core.api import PushBroadcaster

            calls = {"build": 0, "after": 0}

            class B(PushBroadcaster):
                poll_interval = 0.02

                async def _build_payload(self):
                    calls["build"] += 1
                    return {"tick": calls["build"]}

                async def _after_tick(self, payload):
                    calls["after"] += 1

            b = B()
            w1, w2 = _FakeWS(), _FakeWS()
            await b.connect(w1)
            await b.connect(w2)
            await asyncio.sleep(0.09)
            b.disconnect(w1)
            b.disconnect(w2)
            await b.stop()

            assert len(w1.sent) >= 1
            assert w1.sent == w2.sent  # identical broadcast
            assert calls["build"] == len(w1.sent)  # NOT ticks x clients
            assert calls["after"] == calls["build"]  # hook once per tick

        asyncio.run(main())

    def test_refresh_triggers_immediate_tick(self):
        async def main():
            from core.api import PushBroadcaster

            class B(PushBroadcaster):
                poll_interval = 60.0  # would never tick again on its own

                async def _build_payload(self):
                    return {"tick": 1}

            b = B()
            w = _FakeWS()
            await b.connect(w)
            await asyncio.sleep(0.05)
            assert len(w.sent) == 1
            b.request_refresh()
            await asyncio.sleep(0.15)
            assert len(w.sent) >= 2
            b.disconnect(w)
            await b.stop()

        asyncio.run(main())

    def test_producer_stops_when_empty(self):
        async def main():
            from core.api import PushBroadcaster

            class B(PushBroadcaster):
                poll_interval = 0.02

                async def _build_payload(self):
                    return {}

            b = B()
            w = _FakeWS()
            await b.connect(w)
            await asyncio.sleep(0.05)
            b.disconnect(w)
            await asyncio.sleep(0.06)
            assert b._task is None  # producer loop exited

        asyncio.run(main())


class _FakeAlert:
    severity = "critical"

    def __init__(self):
        self.title = "t"
        self.message = "m"
        self.category = "lice"
        self.metric_value = 0.7
        self.threshold = 0.5
        self.created_at = "2026-10-12T00:00:00Z"

    def to_dict(self):
        return {
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "category": self.category,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "created_at": self.created_at,
        }


class TestAlertsBroadcasterWebhookFanout:
    def test_webhooks_dispatched_once_not_per_client(self, monkeypatch):
        """Regression: previously N connected clients => N duplicate webhook
        dispatches of every critical alert."""

        async def main():
            from core.api import _AlertsBroadcaster
            from core.market import threshold_alerts, webhook_dispatcher

            dispatched = {"n": 0}

            async def fake_check_all():
                return [_FakeAlert()]

            async def fake_dispatch(event_type, payload):
                dispatched["n"] += 1

            monkeypatch.setattr(
                threshold_alerts.threshold_alert_engine, "check_all", fake_check_all
            )
            monkeypatch.setattr(
                webhook_dispatcher.webhook_dispatcher, "dispatch_alert", fake_dispatch
            )

            b = _AlertsBroadcaster()
            b.poll_interval = 0.02
            w1, w2, w3 = _FakeWS(), _FakeWS(), _FakeWS()
            for w in (w1, w2, w3):
                await b.connect(w)
            await asyncio.sleep(0.05)  # one tick
            for w in (w1, w2, w3):
                b.disconnect(w)
            await b.stop()

            assert len(w1.sent) == len(w2.sent) == len(w3.sent) >= 1
            # One dispatch per TICK, not per connected client (was Nx before)
            assert dispatched["n"] == len(w1.sent)

        asyncio.run(main())


class TestApiKeyVerifyCache:
    def setup_method(self):
        _api_key_cache.clear()

    def test_positive_result_cached(self, monkeypatch):
        calls = {"n": 0}

        def fast_verify(raw, hashed):
            calls["n"] += 1
            return True

        monkeypatch.setattr(auth_mod, "verify_api_key", fast_verify)
        assert verify_api_key_cached("oc_live_abc123", "$2b$hash1") is True
        assert verify_api_key_cached("oc_live_abc123", "$2b$hash1") is True
        assert calls["n"] == 1  # bcrypt ran once, second call was cache hit

    def test_negative_result_not_cached(self, monkeypatch):
        calls = {"n": 0}

        def fast_verify(raw, hashed):
            calls["n"] += 1
            return False

        monkeypatch.setattr(auth_mod, "verify_api_key", fast_verify)
        assert verify_api_key_cached("oc_live_bad", "$2b$hash1") is False
        assert verify_api_key_cached("oc_live_bad", "$2b$hash1") is False
        assert calls["n"] == 2  # negatives always re-verified

    def test_hash_rotation_invalidates_cache(self, monkeypatch):
        calls = {"n": 0}

        def fast_verify(raw, hashed):
            calls["n"] += 1
            return True

        monkeypatch.setattr(auth_mod, "verify_api_key", fast_verify)
        verify_api_key_cached("oc_live_abc123", "$2b$hash_old")
        verify_api_key_cached("oc_live_abc123", "$2b$hash_new")  # rotated
        assert calls["n"] == 2


class TestStripeOffLoop:
    def test_stripe_network_calls_run_in_thread(self):
        import inspect

        import core.billing.stripe_billing as sb

        assert "to_thread" in inspect.getsource(sb.StripeBillingEngine.create_checkout_session)
        assert "to_thread" in inspect.getsource(sb.StripeBillingEngine.get_subscription_status)
        assert "to_thread" in inspect.getsource(sb.StripeBillingEngine.cancel_subscription)
        assert "to_thread" in inspect.getsource(sb.StripeBillingEngine.get_invoice_history)

    def test_bcrypt_runs_off_event_loop_in_routes(self):
        import inspect

        import core.routers.auth_routes as ar

        src = inspect.getsource(ar)
        assert "to_thread(" in src and "verify_password" in src
        assert "to_thread(hash_password" in src

    def test_api_key_verify_off_loop(self):
        import inspect

        src = inspect.getsource(auth_mod._authenticate_via_api_key)
        assert "to_thread(verify_api_key_cached" in src