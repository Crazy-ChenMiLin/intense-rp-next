import tempfile
import time
import unittest

from remote_control.sessions import (
    MAX_CONCURRENT_REMOTE_SESSIONS,
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

    def test_password_change_invalidates_existing_sessions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = RemoteControlSessionStore(tmp)
            session = store.issue_session("pw")

            store.sync_password("new-pw")

            self.assertIsNone(store.validate_token(session["token"], "new-pw"))

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
