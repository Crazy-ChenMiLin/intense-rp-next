import unittest

from drivers.providers import DriverProvider
from utils.model_ids import (
    MODE_CHAT,
    MODE_REASONER,
    get_model_ids_for_provider,
    get_parallel_model_ids_for_providers,
    is_supported_model_id,
    resolve_behavior_mode,
    resolve_parallel_provider_from_model_id,
    resolve_real_model_label_from_model_id,
)


class DummyConfig:
    def __init__(self, *, enable_umm=False):
        self.enable_umm = enable_umm

    def get_setting(self, category, field):
        if category == "network_settings" and field == "enable_umm":
            return self.enable_umm
        return None


class ModelIdTests(unittest.TestCase):
    def test_legacy_model_ids_are_supported(self):
        self.assertTrue(
            is_supported_model_id(
                DriverProvider.DEEPSEEK,
                "deepseek-reasoner",
                DummyConfig(),
            )
        )
        self.assertEqual(
            resolve_behavior_mode("deepseek-chat", DriverProvider.DEEPSEEK),
            MODE_CHAT,
        )

    def test_universal_model_names_when_enabled(self):
        cfg = DummyConfig(enable_umm=True)
        self.assertIn(
            "intenserp-reasoner",
            get_model_ids_for_provider(DriverProvider.QWEN_LM, cfg),
        )
        self.assertTrue(
            is_supported_model_id(DriverProvider.QWEN_LM, "intenserp-chat", cfg)
        )

    def test_real_model_ids_round_trip_label(self):
        labels = ["GLM-5.1"]
        self.assertEqual(
            resolve_real_model_label_from_model_id(
                DriverProvider.GLM_CHAT,
                "glm-5-1-reasoner",
                labels,
            ),
            "GLM-5.1",
        )
        self.assertEqual(
            resolve_behavior_mode(
                "glm-5-1-reasoner",
                DriverProvider.GLM_CHAT,
                real_model_labels=labels,
            ),
            MODE_REASONER,
        )

    def test_parallel_real_model_collision_gets_prefixed(self):
        cfg = DummyConfig(enable_umm=True)
        providers = [DriverProvider.GLM_CHAT, DriverProvider.QWEN_LM]
        labels = {
            DriverProvider.GLM_CHAT: ["Same Model"],
            DriverProvider.QWEN_LM: ["Same Model"],
        }
        ids = get_parallel_model_ids_for_providers(
            providers,
            cfg,
            real_model_labels_by_provider=labels,
        )

        self.assertIn((DriverProvider.GLM_CHAT, "glm-same-model-chat"), ids)
        self.assertIn((DriverProvider.QWEN_LM, "qwen-same-model-chat"), ids)
        self.assertEqual(
            resolve_parallel_provider_from_model_id(
                "qwen-same-model-chat",
                providers,
                cfg,
                real_model_labels_by_provider=labels,
            ),
            DriverProvider.QWEN_LM,
        )


if __name__ == "__main__":
    unittest.main()
