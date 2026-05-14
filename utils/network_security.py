from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NetworkSecurityWarning:
    title: str
    message: str
    level: str = "warning"


def _get_setting(config_manager: Any, category: str, field: str, default: Any = None) -> Any:
    try:
        value = config_manager.get_setting(category, field)
    except Exception:
        return default
    return default if value is None else value


def build_network_security_warnings(config_manager: Any) -> list[NetworkSecurityWarning]:
    warnings: list[NetworkSecurityWarning] = []

    available_on_lan = bool(_get_setting(config_manager, "network_settings", "available_on_lan", False))
    use_api_keys = bool(_get_setting(config_manager, "network_settings", "use_api_keys", False))
    use_ip_whitelist = bool(_get_setting(config_manager, "network_settings", "use_ip_whitelist", False))
    remote_enabled = bool(_get_setting(config_manager, "experimental", "enable_remote_control", False))
    remote_password = str(_get_setting(config_manager, "experimental", "remote_control_password", "") or "")

    if available_on_lan and not (use_api_keys or use_ip_whitelist):
        warnings.append(
            NetworkSecurityWarning(
                title="LAN API Access Is Unprotected",
                message=(
                    "The API server is available on your local network, but API keys and IP "
                    "whitelist are both disabled. Devices on the same network may be able to "
                    "send requests to IntenseRP."
                ),
            )
        )

    if remote_enabled and not remote_password.strip():
        if available_on_lan:
            if use_ip_whitelist:
                message = (
                    "Remote Control is enabled without a password while local network access is on. "
                    "The IP whitelist limits who can reach it, but setting a Remote Control "
                    "password adds another layer of protection."
                )
            else:
                message = (
                    "Remote Control is enabled without a password while local network access is on. "
                    "Anyone who can reach this server may be able to control the running session. "
                    "Set a Remote Control password or enable the IP whitelist."
                )
        else:
            message = (
                "Remote Control is enabled without a password. This is usually fine for "
                "local-only use, but a password is safer if you later enable LAN access."
            )
        warnings.append(
            NetworkSecurityWarning(
                title="Remote Control Has No Password",
                message=message,
            )
        )

    if available_on_lan and remote_enabled and remote_password.strip() and not use_ip_whitelist:
        warnings.append(
            NetworkSecurityWarning(
                title="Remote Control Is Exposed on LAN",
                message=(
                    "Remote Control is reachable from the local network. Password auth is enabled, "
                    "but the IP whitelist is disabled. For shared networks, consider restricting "
                    "access by IP address."
                ),
            )
        )

    return warnings
