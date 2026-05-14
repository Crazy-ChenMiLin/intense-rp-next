import unittest

from utils.ip_utils import is_ip_address_allowed, normalize_ip_address, normalize_ip_list


class IpUtilsTests(unittest.TestCase):
    def test_normalize_ipv4_mapped_ipv6(self):
        self.assertEqual(normalize_ip_address("::ffff:127.0.0.1"), "127.0.0.1")

    def test_normalize_ip_list_skips_empty_values(self):
        self.assertEqual(normalize_ip_list([" 127.0.0.1 ", "", None]), ["127.0.0.1"])

    def test_loopback_addresses_are_allowed_as_a_group(self):
        self.assertTrue(is_ip_address_allowed("::1", ["127.0.0.1"]))

    def test_non_matching_address_is_rejected(self):
        self.assertFalse(is_ip_address_allowed("192.168.1.50", ["192.168.1.51"]))

    def test_invalid_client_address_is_rejected(self):
        self.assertFalse(is_ip_address_allowed("not-an-ip", ["127.0.0.1"]))


if __name__ == "__main__":
    unittest.main()
