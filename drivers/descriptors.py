from __future__ import annotations

from dataclasses import dataclass

from drivers.providers import DriverProvider


@dataclass(frozen=True)
class ProviderDescriptor:
    provider: DriverProvider
    model_prefix: str
    owned_by: str
    behavior_category: str
    icon_path: str
    docs_slug: str


PROVIDER_DESCRIPTORS: dict[DriverProvider, ProviderDescriptor] = {
    DriverProvider.DEEPSEEK: ProviderDescriptor(
        provider=DriverProvider.DEEPSEEK,
        model_prefix="deepseek",
        owned_by="deepseek",
        behavior_category="deepseek_behavior",
        icon_path="providers/deepseek.svg",
        docs_slug="deepseek-behavior",
    ),
    DriverProvider.GLM_CHAT: ProviderDescriptor(
        provider=DriverProvider.GLM_CHAT,
        model_prefix="glm",
        owned_by="glm",
        behavior_category="glm_behavior",
        icon_path="providers/zai.svg",
        docs_slug="glm-behavior",
    ),
    DriverProvider.MOONSHOT: ProviderDescriptor(
        provider=DriverProvider.MOONSHOT,
        model_prefix="moonshot",
        owned_by="moonshot",
        behavior_category="moonshot_behavior",
        icon_path="providers/moonshot.svg",
        docs_slug="moonshot-behavior",
    ),
    DriverProvider.QWEN_LM: ProviderDescriptor(
        provider=DriverProvider.QWEN_LM,
        model_prefix="qwen",
        owned_by="qwen",
        behavior_category="qwen_behavior",
        icon_path="providers/qwen.svg",
        docs_slug="qwen-behavior",
    ),
    DriverProvider.PERPLEXITY: ProviderDescriptor(
        provider=DriverProvider.PERPLEXITY,
        model_prefix="perplexity",
        owned_by="perplexity",
        behavior_category="perplexity_behavior",
        icon_path="providers/perplexity.svg",
        docs_slug="perplexity-behavior",
    ),
    DriverProvider.AI_STUDIO: ProviderDescriptor(
        provider=DriverProvider.AI_STUDIO,
        model_prefix="aistudio",
        owned_by="aistudio",
        behavior_category="aistudio_behavior",
        icon_path="providers/aistudio.svg",
        docs_slug="aistudio-behavior",
    ),
}


def get_provider_descriptor(provider: DriverProvider) -> ProviderDescriptor | None:
    return PROVIDER_DESCRIPTORS.get(provider)


def get_provider_model_prefix(provider: DriverProvider, *, default: str = "deepseek") -> str:
    descriptor = get_provider_descriptor(provider)
    return descriptor.model_prefix if descriptor is not None else default


def get_provider_owned_by(provider: DriverProvider, *, default: str = "deepseek") -> str:
    descriptor = get_provider_descriptor(provider)
    return descriptor.owned_by if descriptor is not None else default


def get_provider_behavior_category(provider: DriverProvider) -> str | None:
    descriptor = get_provider_descriptor(provider)
    return descriptor.behavior_category if descriptor is not None else None


def get_provider_icon_path(provider: DriverProvider) -> str | None:
    descriptor = get_provider_descriptor(provider)
    return descriptor.icon_path if descriptor is not None else None
