import asyncio
import tempfile
import unittest

import httpx
from fastapi import FastAPI

from remote_control.web import RemoteControlActions, RemoteControlWeb
from utils.logger import Logger


class DummyConfig:
    def __init__(self, config_dir, *, password="secret"):
        self.config_dir = config_dir
        self.password = password

    def get_setting(self, category, field):
        if category == "experimental" and field == "enable_remote_control":
            return True
        if category == "experimental" and field == "remote_control_password":
            return self.password
        if category == "network_settings" and field == "use_ip_whitelist":
            return False
        return None


class ActionRecorder:
    def __init__(self, state=None):
        self.state = state or {"running": True, "busy": False}
        self.calls = []

    async def stop(self):
        self.calls.append(("stop", None))

    async def restart(self):
        self.calls.append(("restart", None))

    async def switch_account(self):
        self.calls.append(("switch_account", None))

    async def hotswap(self, provider):
        self.calls.append(("hotswap", provider))

    async def switch_loadout(self, payload):
        self.calls.append(("switch_loadout", dict(payload)))

    async def switch_model(self, payload):
        self.calls.append(("switch_model", dict(payload)))

    def get_state(self):
        return dict(self.state)

    def as_actions(self):
        return RemoteControlActions(
            stop=self.stop,
            restart=self.restart,
            switch_account=self.switch_account,
            hotswap=self.hotswap,
            switch_loadout=self.switch_loadout,
            switch_model=self.switch_model,
            get_state=self.get_state,
        )


class RemoteControlWebLoginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._stdout_enabled = Logger._stdout_enabled
        Logger.set_stdout_enabled(False)
        self.tmp = tempfile.TemporaryDirectory()
        self.web = None
        self.client = None
        self.actions = None

    async def asyncTearDown(self):
        if self.client is not None:
            await self.client.aclose()
        if self.web is not None:
            self.web.stop()
        self.tmp.cleanup()
        Logger.set_stdout_enabled(self._stdout_enabled)

    async def _make_client(self, *, password="secret", state=None):
        app = FastAPI()
        config = DummyConfig(self.tmp.name, password=password)
        self.actions = ActionRecorder(state)
        self.web = RemoteControlWeb(
            config,
            enforce_ip_whitelist=lambda _request: None,
            actions=self.actions.as_actions(),
        )
        self.web.register_routes(app)
        transport = httpx.ASGITransport(
            app=app,
            client=("203.0.113.10", 12345),
        )
        self.client = httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        )
        return self.client

    async def _authenticated_client(self, *, state=None):
        client = await self._make_client(state=state)
        response = await client.post(
            "/remote/api/login",
            json={"password": "secret"},
        )
        self.assertEqual(response.status_code, 200)
        token = response.json()["token"]
        self.assertTrue(token)
        return client, {"Authorization": f"Bearer {token}"}

    async def test_failed_remote_logins_are_rate_limited(self):
        client = await self._make_client()
        for _index in range(RemoteControlWeb.LOGIN_FAILURE_LIMIT):
            response = await client.post(
                "/remote/api/login",
                json={"password": "wrong"},
            )
            self.assertEqual(response.status_code, 401)

        response = await client.post(
            "/remote/api/login",
            json={"password": "wrong"},
        )

        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)
        self.assertIn("Too many failed login attempts", response.json()["detail"])

    async def test_successful_remote_login_clears_failed_attempts(self):
        client = await self._make_client()
        for _index in range(RemoteControlWeb.LOGIN_FAILURE_LIMIT - 1):
            response = await client.post(
                "/remote/api/login",
                json={"password": "wrong"},
            )
            self.assertEqual(response.status_code, 401)

        response = await client.post(
            "/remote/api/login",
            json={"password": "secret"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["token"])

        response = await client.post(
            "/remote/api/login",
            json={"password": "wrong"},
        )
        self.assertEqual(response.status_code, 401)

    async def test_remote_login_without_password_does_not_rate_limit(self):
        client = await self._make_client(password="")
        for _index in range(RemoteControlWeb.LOGIN_FAILURE_LIMIT + 1):
            response = await client.post(
                "/remote/api/login",
                json={"password": "anything"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["needs_auth"])

    async def test_session_requires_remote_token(self):
        client = await self._make_client()

        response = await client.get("/remote/api/session")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Missing remote-control token")

    async def test_session_and_state_accept_valid_token(self):
        client, headers = await self._authenticated_client(
            state={
                "running": True,
                "busy": False,
                "current_provider": "DeepSeek",
                "model_switch_supported": True,
                "model_switch_options": ["deepseek-chat", "deepseek-reasoner"],
                "model_switch_current_model": "deepseek-chat",
            }
        )

        response = await client.get("/remote/api/session", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])

        response = await client.get("/remote/api/state", headers=headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["running"])
        self.assertEqual(payload["current_provider"], "DeepSeek")
        self.assertTrue(payload["model_switch"]["supported"])

    async def test_stop_action_runs_deferred_handler(self):
        client, headers = await self._authenticated_client()

        response = await client.post(
            "/remote/api/action/stop",
            headers=headers,
            json={},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["disconnect"])

        await asyncio.sleep(0.2)
        self.assertIn(("stop", None), self.actions.calls)

    async def test_action_rejects_when_services_are_not_running(self):
        client, headers = await self._authenticated_client(
            state={"running": False, "busy": False}
        )

        response = await client.post(
            "/remote/api/action/restart",
            headers=headers,
            json={},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Services are not running")

    async def test_action_rejects_when_services_are_busy(self):
        client, headers = await self._authenticated_client(
            state={"running": True, "busy": True}
        )

        response = await client.post(
            "/remote/api/action/restart",
            headers=headers,
            json={},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Services are busy")

    async def test_hotswap_validates_target_provider(self):
        client, headers = await self._authenticated_client(
            state={
                "running": True,
                "busy": False,
                "current_provider": "DeepSeek",
                "hotswap_targets": ["QwenLM"],
            }
        )

        response = await client.post(
            "/remote/api/action/hotswap",
            headers=headers,
            json={"provider": "Moonshot"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Provider is unavailable")

        response = await client.post(
            "/remote/api/action/hotswap",
            headers=headers,
            json={"provider": "QwenLM"},
        )
        self.assertEqual(response.status_code, 200)

        await asyncio.sleep(0.2)
        self.assertIn(("hotswap", "QwenLM"), self.actions.calls)

    async def test_switch_model_returns_noop_when_selected_model_is_current(self):
        client, headers = await self._authenticated_client(
            state={
                "running": True,
                "busy": False,
                "model_switch_supported": True,
                "model_switch_providers": [
                    {
                        "name": "DeepSeek",
                        "current_model": "deepseek-chat",
                        "options": ["deepseek-chat", "deepseek-reasoner"],
                    }
                ],
            }
        )

        response = await client.post(
            "/remote/api/action/switch-model",
            headers=headers,
            json={"provider": "DeepSeek", "model": "deepseek-chat"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["disconnect"])
        self.assertEqual(self.actions.calls, [])

    async def test_switch_model_sends_valid_changes(self):
        client, headers = await self._authenticated_client(
            state={
                "running": True,
                "busy": False,
                "model_switch_supported": True,
                "model_switch_providers": [
                    {
                        "name": "DeepSeek",
                        "current_model": "deepseek-chat",
                        "options": ["deepseek-chat", "deepseek-reasoner"],
                    }
                ],
            }
        )

        response = await client.post(
            "/remote/api/action/switch-model",
            headers=headers,
            json={"models": {"DeepSeek": "deepseek-reasoner"}},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["disconnect"])
        self.assertIn(
            ("switch_model", {"DeepSeek": "deepseek-reasoner"}),
            self.actions.calls,
        )

    async def test_switch_model_rejects_unavailable_model(self):
        client, headers = await self._authenticated_client(
            state={
                "running": True,
                "busy": False,
                "model_switch_supported": True,
                "model_switch_providers": [
                    {
                        "name": "DeepSeek",
                        "current_model": "deepseek-chat",
                        "options": ["deepseek-chat"],
                    }
                ],
            }
        )

        response = await client.post(
            "/remote/api/action/switch-model",
            headers=headers,
            json={"provider": "DeepSeek", "model": "deepseek-reasoner"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Model is unavailable")

    async def test_switch_loadout_sends_valid_changes(self):
        client, headers = await self._authenticated_client(
            state={
                "running": True,
                "busy": False,
                "loadout_switch_supported": True,
                "loadout_switch_providers": [
                    {
                        "name": "DeepSeek",
                        "current_loadout": "Default",
                        "options": ["Default", "Creative"],
                    }
                ],
            }
        )

        response = await client.post(
            "/remote/api/action/switch-loadout",
            headers=headers,
            json={"loadouts": {"DeepSeek": "Creative"}},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["disconnect"])
        self.assertIn(
            ("switch_loadout", {"DeepSeek": "Creative"}),
            self.actions.calls,
        )


if __name__ == "__main__":
    unittest.main()
