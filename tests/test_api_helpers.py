import asyncio
import importlib
import sys
import types
import unittest


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
from utils.logger import Logger


class DummyRequest:
    def __init__(self, *, disconnected=False, disconnect_after=0):
        self.disconnected = disconnected
        self.disconnect_after = disconnect_after
        self.calls = 0

    async def is_disconnected(self):
        self.calls += 1
        if self.disconnect_after and self.calls >= self.disconnect_after:
            return True
        return self.disconnected


class NonStreamingChunkTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._stdout_enabled = Logger._stdout_enabled
        Logger.set_stdout_enabled(False)

    async def asyncTearDown(self):
        Logger.set_stdout_enabled(self._stdout_enabled)

    async def test_returns_queued_chunk(self):
        queue = asyncio.Queue()
        await queue.put("data: {}\n\n")
        abort_event = asyncio.Event()
        api_instance = object.__new__(api.API)
        api_instance._notify_queue_state_changed = lambda: None

        async def _remove(_abort_event):
            return False

        api_instance._remove_queued_request_by_abort_event = _remove
        api_instance._request_abort_for_abort_event = lambda _abort_event: None

        chunk = await api.API._get_non_streaming_chunk(
            api_instance,
            queue,
            abort_event,
            DummyRequest(),
        )

        self.assertEqual(chunk, "data: {}\n\n")
        self.assertFalse(abort_event.is_set())

    async def test_disconnect_aborts_request(self):
        queue = asyncio.Queue()
        abort_event = asyncio.Event()
        api_instance = object.__new__(api.API)
        api_instance._notify_queue_state_changed = lambda: None
        api_instance.abort_called = False

        async def _remove(_abort_event):
            return False

        api_instance._remove_queued_request_by_abort_event = _remove
        api_instance._request_abort_for_abort_event = (
            lambda _abort_event: setattr(api_instance, "abort_called", True)
        )

        chunk = await api.API._get_non_streaming_chunk(
            api_instance,
            queue,
            abort_event,
            DummyRequest(disconnected=True),
        )

        self.assertIsNone(chunk)
        self.assertTrue(abort_event.is_set())
        self.assertTrue(api_instance.abort_called)

    async def test_later_disconnect_aborts_waiting_request(self):
        queue = asyncio.Queue()
        abort_event = asyncio.Event()
        api_instance = object.__new__(api.API)
        api_instance._notify_queue_state_changed = lambda: None
        api_instance.abort_called = False

        async def _remove(_abort_event):
            return False

        api_instance._remove_queued_request_by_abort_event = _remove
        api_instance._request_abort_for_abort_event = (
            lambda _abort_event: setattr(api_instance, "abort_called", True)
        )

        chunk = await api.API._get_non_streaming_chunk(
            api_instance,
            queue,
            abort_event,
            DummyRequest(disconnect_after=2),
        )

        self.assertIsNone(chunk)
        self.assertTrue(abort_event.is_set())
        self.assertTrue(api_instance.abort_called)


class MessageContentTests(unittest.TestCase):
    def test_plain_string_content_is_preserved(self):
        message = api.Message(role="user", content="hello")

        self.assertEqual(message.content, "hello")

    def test_text_content_array_is_flattened(self):
        message = api.Message(
            role="user",
            content=[
                {"type": "text", "text": "hello"},
                {"type": "image_url", "image_url": {"url": "https://example.invalid/image.png"}},
                {"type": "input_text", "text": "world"},
            ],
        )

        self.assertEqual(message.content, "hello\nworld")

    def test_none_content_becomes_empty_string(self):
        message = api.Message(role="user", content=None)

        self.assertEqual(message.content, "")


if __name__ == "__main__":
    unittest.main()
