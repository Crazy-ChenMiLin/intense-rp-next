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


async def _noop():
    return None


def _actions():
    return RemoteControlActions(
        stop=_noop,
        restart=_noop,
        switch_account=_noop,
        hotswap=lambda _provider: _noop(),
        switch_loadout=lambda _payload: _noop(),
        switch_model=lambda _payload: _noop(),
        get_state=lambda: {"running": True, "busy": False},
    )


class RemoteControlWebLoginTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._stdout_enabled = Logger._stdout_enabled
        Logger.set_stdout_enabled(False)
        self.tmp = tempfile.TemporaryDirectory()
        self.web = None
        self.client = None

    async def asyncTearDown(self):
        if self.client is not None:
            await self.client.aclose()
        if self.web is not None:
            self.web.stop()
        self.tmp.cleanup()
        Logger.set_stdout_enabled(self._stdout_enabled)

    async def _make_client(self, *, password="secret"):
        app = FastAPI()
        config = DummyConfig(self.tmp.name, password=password)
        self.web = RemoteControlWeb(
            config,
            enforce_ip_whitelist=lambda _request: None,
            actions=_actions(),
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


if __name__ == "__main__":
    unittest.main()
