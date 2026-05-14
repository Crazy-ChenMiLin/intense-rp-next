import unittest

from utils.network_security import build_network_security_warnings


class DummyConfig:
    def __init__(self, settings):
        self.settings = settings

    def get_setting(self, category, field):
        return self.settings.get(category, {}).get(field)


def cfg(
    *,
    lan=False,
    api_keys=False,
    ip_whitelist=False,
    remote=False,
    remote_password="",
):
    return DummyConfig(
        {
            "network_settings": {
                "available_on_lan": lan,
                "use_api_keys": api_keys,
                "use_ip_whitelist": ip_whitelist,
            },
            "experimental": {
                "enable_remote_control": remote,
                "remote_control_password": remote_password,
            },
        }
    )


class NetworkSecurityWarningTests(unittest.TestCase):
    def test_local_only_api_without_remote_control_has_no_warning(self):
        self.assertEqual(build_network_security_warnings(cfg()), [])

    def test_lan_without_api_keys_or_ip_whitelist_warns(self):
        warnings = build_network_security_warnings(cfg(lan=True))

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].title, "LAN API Access Is Unprotected")

    def test_lan_with_api_key_has_no_unprotected_api_warning(self):
        warnings = build_network_security_warnings(cfg(lan=True, api_keys=True))

        self.assertFalse(any(warning.title == "LAN API Access Is Unprotected" for warning in warnings))

    def test_remote_control_without_password_warns(self):
        warnings = build_network_security_warnings(cfg(remote=True))

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].title, "Remote Control Has No Password")

    def test_remote_control_on_lan_with_password_but_no_ip_whitelist_warns(self):
        warnings = build_network_security_warnings(
            cfg(lan=True, api_keys=True, remote=True, remote_password="secret")
        )

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].title, "Remote Control Is Exposed on LAN")

    def test_lan_remote_control_without_password_reports_both_risks(self):
        warnings = build_network_security_warnings(cfg(lan=True, remote=True))
        titles = {warning.title for warning in warnings}

        self.assertIn("LAN API Access Is Unprotected", titles)
        self.assertIn("Remote Control Has No Password", titles)

    def test_remote_control_without_password_on_lan_with_ip_whitelist_mentions_extra_layer(self):
        warnings = build_network_security_warnings(
            cfg(lan=True, ip_whitelist=True, remote=True)
        )

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].title, "Remote Control Has No Password")
        self.assertIn("adds another layer", warnings[0].message)
        self.assertNotIn("enable the IP whitelist", warnings[0].message)


if __name__ == "__main__":
    unittest.main()
