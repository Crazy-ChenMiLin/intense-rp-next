import asyncio
import importlib
import json
import sys
import types
import unittest

import httpx


def _install_api_import_stubs():
    patchright_module = types.ModuleType("patchright")
    patchright_async_api = types.ModuleType("patchright.async_api")

    class _DummyBrowser:
        pass

    class _DummyBrowserContext:
        pass

    class _DummyPage:
        pass

    async def _dummy_async_playwright():
        return None

    patchright_async_api.Browser = _DummyBrowser
    patchright_async_api.BrowserContext = _DummyBrowserContext
    patchright_async_api.Page = _DummyPage
    patchright_async_api.async_playwright = _dummy_async_playwright
    patchright_module.async_api = patchright_async_api

    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda *args, **kwargs: None

    sys.modules.setdefault("patchright", patchright_module)
    sys.modules.setdefault("patchright.async_api", patchright_async_api)
    sys.modules.setdefault("dotenv", dotenv_module)


_install_api_import_stubs()
api = importlib.import_module("api")
from drivers.providers import DriverProvider
from utils.logger import Logger


class DummyConfig:
    def __init__(self, settings=None):
        self.settings = settings or {}

    def get_setting(self, category, field):
        return self.settings.get(category, {}).get(field)


class FakeDriver:
    provider = DriverProvider.DEEPSEEK
    provider_label = "DeepSeek"

    def __init__(self, *, config=None):
        self.config_manager = config or DummyConfig()
        self.is_running = True
        self.abort_requested = False
        self.current_abort_event = None
        self.requests = []

    def request_abort(self):
        self.abort_requested = True
        if self.current_abort_event is not None:
            self.current_abort_event.set()

    async def apply_configured_model(self, model=None):
        return None

    async def generate_response(
        self,
        message,
        model="",
        stream=False,
        temperature=None,
        top_p=None,
        max_tokens=None,
        abort_event=None,
    ):
        self.current_abort_event = abort_event
        self.requests.append(
            {
                "message": message,
                "model": model,
                "stream": stream,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": max_tokens,
            }
        )
        chunk = {
            "id": "chatcmpl-test",
            "object": "chat.completion.chunk",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": "hello"},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n"
        finish = dict(chunk)
        finish["choices"] = [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ]
        yield f"data: {json.dumps(finish)}\n\n"


class ApiRouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._stdout_enabled = Logger._stdout_enabled
        Logger.set_stdout_enabled(False)
        self.driver = FakeDriver()
        self.api = api.API(self.driver)
        transport = httpx.ASGITransport(app=self.api.app)
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.api.stop()
        Logger.set_stdout_enabled(self._stdout_enabled)

    async def test_models_route_lists_deepseek_models(self):
        response = await self.client.get("/v1/models")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        ids = [item["id"] for item in payload["data"]]
        self.assertIn("deepseek-chat", ids)
        self.assertIn("deepseek-reasoner", ids)

    async def test_non_streaming_chat_completion_uses_fake_driver(self):
        response = await self.client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek-chat",
                "stream": False,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["choices"][0]["message"]["content"], "hello")
        self.assertEqual(payload["choices"][0]["finish_reason"], "stop")
        self.assertEqual(self.driver.requests[0]["message"][0].content, "hi")

    async def test_streaming_chat_completion_returns_done_marker(self):
        response = await self.client.post(
            "/v1/chat/completions",
            json={
                "model": "deepseek-chat",
                "stream": True,
                "messages": [{"role": "user", "content": "hi"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("data:", body)
        self.assertIn("hello", body)
        self.assertIn("data: [DONE]", body)

    async def test_api_key_auth_rejects_missing_bearer_token(self):
        await self.api.stop()
        self.driver = FakeDriver(
            config=DummyConfig(
                {
                    "network_settings": {
                        "use_api_keys": True,
                        "api_keys": [{"name": "Test", "key": "secret"}],
                    }
                }
            )
        )
        self.api = api.API(self.driver)
        await self.client.aclose()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.api.app),
            base_url="http://testserver",
        )

        response = await self.client.get("/v1/models")

        self.assertEqual(response.status_code, 401)

    async def test_api_key_auth_accepts_valid_bearer_token(self):
        await self.api.stop()
        self.driver = FakeDriver(
            config=DummyConfig(
                {
                    "network_settings": {
                        "use_api_keys": True,
                        "api_keys": [{"name": "Test", "key": "secret"}],
                    }
                }
            )
        )
        self.api = api.API(self.driver)
        await self.client.aclose()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.api.app),
            base_url="http://testserver",
        )

        response = await self.client.get(
            "/v1/models",
            headers={"Authorization": "Bearer secret"},
        )

        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
