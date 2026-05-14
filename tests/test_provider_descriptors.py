import importlib.util
import unittest

from config.loadouts import get_behavior_category_for_provider
from drivers.descriptors import (
    PROVIDER_DESCRIPTORS,
    get_provider_behavior_category,
    get_provider_icon_path,
    get_provider_model_prefix,
    get_provider_owned_by,
)
from drivers.providers import DriverProvider
from remote_control.web import PROVIDER_ICON_MAP
from utils.model_ids import get_legacy_model_prefix, get_owned_by_for_provider


class ProviderDescriptorTests(unittest.TestCase):
    def test_every_provider_has_descriptor(self):
        self.assertEqual(set(PROVIDER_DESCRIPTORS), set(DriverProvider))

    def test_model_id_helpers_read_provider_descriptors(self):
        expected_prefixes = {
            DriverProvider.DEEPSEEK: "deepseek",
            DriverProvider.GLM_CHAT: "glm",
            DriverProvider.MOONSHOT: "moonshot",
            DriverProvider.QWEN_LM: "qwen",
            DriverProvider.PERPLEXITY: "perplexity",
            DriverProvider.AI_STUDIO: "aistudio",
        }

        for provider, prefix in expected_prefixes.items():
            with self.subTest(provider=provider):
                self.assertEqual(get_provider_model_prefix(provider), prefix)
                self.assertEqual(get_legacy_model_prefix(provider), prefix)
                self.assertEqual(get_provider_owned_by(provider), prefix)
                self.assertEqual(get_owned_by_for_provider(provider), prefix)

    def test_loadout_behavior_categories_read_provider_descriptors(self):
        expected_categories = {
            DriverProvider.DEEPSEEK: "deepseek_behavior",
            DriverProvider.GLM_CHAT: "glm_behavior",
            DriverProvider.MOONSHOT: "moonshot_behavior",
            DriverProvider.QWEN_LM: "qwen_behavior",
            DriverProvider.PERPLEXITY: "perplexity_behavior",
            DriverProvider.AI_STUDIO: "aistudio_behavior",
        }

        for provider, category in expected_categories.items():
            with self.subTest(provider=provider):
                self.assertEqual(get_provider_behavior_category(provider), category)
                self.assertEqual(get_behavior_category_for_provider(provider), category)

    def test_remote_icon_map_reads_provider_descriptors(self):
        for provider, descriptor in PROVIDER_DESCRIPTORS.items():
            with self.subTest(provider=provider):
                self.assertEqual(
                    PROVIDER_ICON_MAP[provider.value],
                    get_provider_icon_path(provider),
                )
                self.assertEqual(PROVIDER_ICON_MAP[provider.value], descriptor.icon_path)

    def test_hotswap_provider_lists_read_provider_descriptors(self):
        if importlib.util.find_spec("PySide6") is None:
            self.skipTest("PySide6 is not installed in this test environment")

        from ui.niche.hotswap_dialog import ALL_PROVIDERS, PROVIDER_ICON_MAP as HOTSWAP_ICON_MAP

        self.assertEqual(
            ALL_PROVIDERS,
            [descriptor.provider.value for descriptor in PROVIDER_DESCRIPTORS.values()],
        )
        self.assertEqual(
            HOTSWAP_ICON_MAP,
            {
                descriptor.provider.value: descriptor.icon_path
                for descriptor in PROVIDER_DESCRIPTORS.values()
            },
        )


if __name__ == "__main__":
    unittest.main()
