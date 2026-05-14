import tempfile
import time
import unittest

from remote_control.sessions import (
    LEGACY_PASSWORD_HASH_ALGORITHM,
    MAX_CONCURRENT_REMOTE_SESSIONS,
    PASSWORD_HASH_ALGORITHM,
    RemoteControlSessionStore,
)


class RemoteControlSessionStoreTests(unittest.TestCase):
    def test_issue_and_validate_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RemoteControlSessionStore(tmp)
            session = store.issue_session("pw")

            self.assertIsNotNone(session)
            validated = store.validate_token(session["token"], "pw")
            self.assertIsNotNone(validated)
            self.assertEqual(validated["token"], session["token"])
            self.assertEqual(
                store._payload["password_hash_algorithm"],
                PASSWORD_HASH_ALGORITHM,
            )
            self.assertTrue(store._payload["password_hash_salt"])
            self.assertNotEqual(
                store._payload["password_hash"],
                RemoteControlSessionStore._legacy_hash_password("pw"),
            )

    def test_password_change_invalidates_existing_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RemoteControlSessionStore(tmp)
            session = store.issue_session("pw")

            store.sync_password("new-pw")

            self.assertIsNone(store.validate_token(session["token"], "new-pw"))

    def test_legacy_password_hash_is_upgraded_without_invalidating_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RemoteControlSessionStore(tmp)
            session = store.issue_session("pw")
            legacy_hash = RemoteControlSessionStore._legacy_hash_password("pw")
            store._payload.update(
                {
                    "version": 1,
                    "password_hash_algorithm": LEGACY_PASSWORD_HASH_ALGORITHM,
                    "password_hash_iterations": 0,
                    "password_hash_salt": "",
                    "password_hash": legacy_hash,
                    "sessions": [session],
                }
            )
            store._write_payload()

            migrated_store = RemoteControlSessionStore(tmp)
            validated = migrated_store.validate_token(session["token"], "pw")

            self.assertIsNotNone(validated)
            self.assertEqual(
                migrated_store._payload["password_hash_algorithm"],
                PASSWORD_HASH_ALGORITHM,
            )
            self.assertTrue(migrated_store._payload["password_hash_salt"])
            self.assertNotEqual(migrated_store._payload["password_hash"], legacy_hash)

    def test_legacy_password_mismatch_invalidates_session_and_upgrades_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RemoteControlSessionStore(tmp)
            session = store.issue_session("pw")
            legacy_hash = RemoteControlSessionStore._legacy_hash_password("pw")
            store._payload.update(
                {
                    "version": 1,
                    "password_hash_algorithm": LEGACY_PASSWORD_HASH_ALGORITHM,
                    "password_hash_iterations": 0,
                    "password_hash_salt": "",
                    "password_hash": legacy_hash,
                    "sessions": [session],
                }
            )
            store._write_payload()

            migrated_store = RemoteControlSessionStore(tmp)
            validated = migrated_store.validate_token(session["token"], "new-pw")

            self.assertIsNone(validated)
            self.assertEqual(
                migrated_store._payload["password_hash_algorithm"],
                PASSWORD_HASH_ALGORITHM,
            )
            self.assertEqual(migrated_store._payload["sessions"], [])

    def test_empty_password_does_not_issue_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RemoteControlSessionStore(tmp)

            self.assertIsNone(store.issue_session(""))

    def test_session_limit_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RemoteControlSessionStore(tmp)
            sessions = [
                store.issue_session("pw")
                for _index in range(MAX_CONCURRENT_REMOTE_SESSIONS + 2)
            ]

            active = store._normalize_sessions(time.time())
            self.assertEqual(len(active), MAX_CONCURRENT_REMOTE_SESSIONS)
            self.assertEqual(active[0]["token"], sessions[-1]["token"])


if __name__ == "__main__":
    unittest.main()
