import asyncio
import importlib
import sys
import types
import unittest


def _install_base_driver_import_stubs():
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

    sys.modules.setdefault("patchright", patchright_module)
    sys.modules.setdefault("patchright.async_api", patchright_async_api)


_install_base_driver_import_stubs()
base_driver = importlib.import_module("drivers.base_driver")
from drivers.providers import DriverProvider
from utils.logger import Logger


class AbortBridgeDriver(base_driver.BaseDriver):
    def __init__(self):
        super().__init__(config_manager=None, provider=DriverProvider.DEEPSEEK)
        self.abort_generation_calls = 0

    def get_start_url(self):
        return "https://example.invalid"

    async def login(self):
        return None

    async def set_sidebar_status(self, open):
        return None

    async def click_new_chat(self, source="auto"):
        return None

    async def set_deepthink_state(self, state):
        return None

    async def set_search_state(self, state):
        return None

    async def upload_file(self, file_spec):
        return None

    async def enter_message(self, message):
        return None

    async def send_message(self, timeout=None):
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
        if False:
            yield None

    async def abort_generation(self):
        self.abort_generation_calls += 1


class FailingAbortBridgeDriver(AbortBridgeDriver):
    async def abort_generation(self):
        self.abort_generation_calls += 1
        raise RuntimeError("abort failed")


class BaseDriverAbortTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._stdout_enabled = Logger._stdout_enabled
        Logger.set_stdout_enabled(False)

    async def asyncTearDown(self):
        Logger.set_stdout_enabled(self._stdout_enabled)

    async def test_request_abort_sets_event_and_bridges_abort_generation(self):
        driver = AbortBridgeDriver()
        abort_event = asyncio.Event()
        driver.current_abort_event = abort_event

        driver.request_abort()
        await asyncio.sleep(0)

        self.assertTrue(driver.abort_requested)
        self.assertTrue(abort_event.is_set())
        self.assertEqual(driver.abort_generation_calls, 1)

    async def test_request_abort_does_not_schedule_duplicate_abort_task(self):
        driver = AbortBridgeDriver()

        driver.request_abort()
        driver.request_abort()
        await asyncio.sleep(0)

        self.assertEqual(driver.abort_generation_calls, 1)

    async def test_abort_generation_errors_are_swallowed(self):
        driver = FailingAbortBridgeDriver()

        driver.request_abort()
        await asyncio.sleep(0)
        await driver._abort_generation_task

        self.assertTrue(driver.abort_requested)
        self.assertEqual(driver.abort_generation_calls, 1)


if __name__ == "__main__":
    unittest.main()
