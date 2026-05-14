from __future__ import annotations

import hashlib
import json
import secrets
import time
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

from utils.logger import Logger


REMOTE_SESSION_TTL_SECONDS = 15 * 60
MAX_CONCURRENT_REMOTE_SESSIONS = 5

PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 200_000
LEGACY_PASSWORD_HASH_ALGORITHM = "sha256"


class RemoteControlSessionStore:
    VERSION = 2
    FILENAME = "remote_control_sessions.json.enc"

    def __init__(self, config_dir: str | Path):
        self.config_dir = Path(config_dir).resolve()
        self._sessions_path = (self.config_dir / self.FILENAME).resolve()
        self._key_path = (self.config_dir / "settings.key").resolve()
        self._cipher = Fernet(self._load_or_create_settings_key())
        self._payload = self._read_payload()
        self._verified_password_cache_key: tuple[str, str, int, str, str] | None = None

    def _load_or_create_settings_key(self) -> bytes:
        try:
            self._key_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            Logger.warning(
                f"RemoteControl: failed to create key directory ({self._key_path.parent}): {exc}"
            )

        if self._key_path.exists():
            try:
                return self._key_path.read_bytes()
            except Exception as exc:
                Logger.warning(
                    f"RemoteControl: failed to read settings.key ({self._key_path}): {exc}"
                )

        key = Fernet.generate_key()
        try:
            self._key_path.write_bytes(key)
        except Exception as exc:
            Logger.warning(
                f"RemoteControl: failed to write settings.key ({self._key_path}): {exc}"
            )
        return key

    def _default_payload(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "password_hash_algorithm": "",
            "password_hash_iterations": 0,
            "password_hash_salt": "",
            "password_hash": "",
            "sessions": [],
        }

    def _read_payload(self) -> dict[str, Any]:
        if not self._sessions_path.exists():
            return self._default_payload()

        try:
            encrypted = self._sessions_path.read_bytes()
            decrypted = self._cipher.decrypt(encrypted)
            payload = json.loads(decrypted.decode("utf-8"))
            if not isinstance(payload, dict):
                return self._default_payload()

            version = payload.get("version")
            password_hash_algorithm = payload.get("password_hash_algorithm")
            password_hash_iterations = payload.get("password_hash_iterations")
            password_hash_salt = payload.get("password_hash_salt")
            password_hash = payload.get("password_hash")
            sessions = payload.get("sessions")
            if not isinstance(version, int):
                return self._default_payload()
            if not isinstance(password_hash_algorithm, str):
                password_hash_algorithm = ""
            if not isinstance(password_hash_iterations, int):
                password_hash_iterations = 0
            if not isinstance(password_hash_salt, str):
                password_hash_salt = ""
            if not isinstance(password_hash, str):
                password_hash = ""
            if not isinstance(sessions, list):
                sessions = []

            if password_hash and not password_hash_algorithm:
                password_hash_algorithm = LEGACY_PASSWORD_HASH_ALGORITHM

            return {
                "version": version,
                "password_hash_algorithm": password_hash_algorithm,
                "password_hash_iterations": password_hash_iterations,
                "password_hash_salt": password_hash_salt,
                "password_hash": password_hash,
                "sessions": list(sessions),
            }
        except Exception as exc:
            Logger.warning(
                f"RemoteControl: failed to read {self._sessions_path.name}: {exc}"
            )
            return self._default_payload()

    def _write_payload(self) -> bool:
        try:
            self._sessions_path.parent.mkdir(parents=True, exist_ok=True)
            raw = json.dumps(
                self._payload,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            encrypted = self._cipher.encrypt(raw)
            self._sessions_path.write_bytes(encrypted)
            return True
        except Exception as exc:
            Logger.warning(
                f"RemoteControl: failed to write {self._sessions_path.name}: {exc}"
            )
            return False

    @staticmethod
    def _legacy_hash_password(password: str | None) -> str:
        raw = str(password or "").encode("utf-8")
        return hashlib.sha256(raw).hexdigest() if raw else ""

    @staticmethod
    def _password_cache_fingerprint(password: str | None) -> str:
        raw = str(password or "").encode("utf-8")
        return hashlib.sha256(raw).hexdigest() if raw else ""

    @staticmethod
    def _hash_password_pbkdf2(
        password: str | None,
        *,
        salt_hex: str,
        iterations: int,
    ) -> str:
        raw = str(password or "").encode("utf-8")
        if not raw or not salt_hex or iterations <= 0:
            return ""

        try:
            salt = bytes.fromhex(salt_hex)
        except ValueError:
            return ""

        return hashlib.pbkdf2_hmac(
            "sha256",
            raw,
            salt,
            iterations,
        ).hex()

    @classmethod
    def _build_password_hash_record(cls, password: str | None) -> dict[str, Any]:
        if not str(password or ""):
            return cls._blank_password_hash_record()

        salt_hex = secrets.token_bytes(16).hex()
        password_hash = cls._hash_password_pbkdf2(
            password,
            salt_hex=salt_hex,
            iterations=PASSWORD_HASH_ITERATIONS,
        )
        return {
            "password_hash_algorithm": PASSWORD_HASH_ALGORITHM,
            "password_hash_iterations": PASSWORD_HASH_ITERATIONS,
            "password_hash_salt": salt_hex,
            "password_hash": password_hash,
        }

    @staticmethod
    def _blank_password_hash_record() -> dict[str, Any]:
        return {
            "password_hash_algorithm": "",
            "password_hash_iterations": 0,
            "password_hash_salt": "",
            "password_hash": "",
        }

    def _current_password_hash_record(self) -> dict[str, Any]:
        return {
            "password_hash_algorithm": str(
                self._payload.get("password_hash_algorithm") or ""
            ),
            "password_hash_iterations": int(
                self._payload.get("password_hash_iterations") or 0
            ),
            "password_hash_salt": str(self._payload.get("password_hash_salt") or ""),
            "password_hash": str(self._payload.get("password_hash") or ""),
        }

    def _stored_password_matches(self, password: str | None) -> bool:
        safe_password = str(password or "")
        current_hash = str(self._payload.get("password_hash") or "")
        if not safe_password or not current_hash:
            return False

        algorithm = str(self._payload.get("password_hash_algorithm") or "")
        iterations = int(self._payload.get("password_hash_iterations") or 0)
        salt_hex = str(self._payload.get("password_hash_salt") or "")
        password_fingerprint = self._password_cache_fingerprint(safe_password)
        cache_key = (algorithm, salt_hex, iterations, current_hash, password_fingerprint)
        if self._verified_password_cache_key == cache_key:
            return True

        matched = False
        if algorithm == LEGACY_PASSWORD_HASH_ALGORITHM:
            candidate = self._legacy_hash_password(safe_password)
            matched = bool(candidate) and secrets.compare_digest(candidate, current_hash)

        elif algorithm == PASSWORD_HASH_ALGORITHM:
            candidate = self._hash_password_pbkdf2(
                safe_password,
                salt_hex=salt_hex,
                iterations=iterations,
            )
            matched = bool(candidate) and secrets.compare_digest(candidate, current_hash)

        if matched:
            self._verified_password_cache_key = cache_key
        return matched

    def _password_hash_needs_upgrade(self) -> bool:
        return (
            str(self._payload.get("password_hash_algorithm") or "") != PASSWORD_HASH_ALGORITHM
            or int(self._payload.get("password_hash_iterations") or 0) != PASSWORD_HASH_ITERATIONS
            or not str(self._payload.get("password_hash_salt") or "")
        )

    @staticmethod
    def _normalize_token(token: str | None) -> str:
        return str(token or "").strip()

    def _normalize_sessions(self, now: float | None = None) -> list[dict[str, Any]]:
        current_time = float(now if now is not None else time.time())
        normalized: list[dict[str, Any]] = []
        for raw_session in self._payload.get("sessions", []):
            if not isinstance(raw_session, dict):
                continue

            token = self._normalize_token(raw_session.get("token"))
            if not token:
                continue

            try:
                issued_at = float(raw_session.get("issued_at") or 0.0)
            except Exception:
                issued_at = 0.0
            try:
                last_seen_at = float(raw_session.get("last_seen_at") or issued_at)
            except Exception:
                last_seen_at = issued_at
            try:
                expires_at = float(raw_session.get("expires_at") or 0.0)
            except Exception:
                expires_at = 0.0

            if expires_at <= current_time:
                continue

            normalized.append(
                {
                    "token": token,
                    "issued_at": issued_at,
                    "last_seen_at": last_seen_at,
                    "expires_at": expires_at,
                }
            )

        normalized.sort(key=lambda item: float(item.get("issued_at") or 0.0), reverse=True)
        return normalized[:MAX_CONCURRENT_REMOTE_SESSIONS]

    def sync_password(self, password: str | None) -> None:
        safe_password = str(password or "")
        sessions = self._normalize_sessions()

        changed = False
        if safe_password:
            password_matches = self._stored_password_matches(safe_password)
            if not password_matches:
                sessions = []
                changed = True

            if (not password_matches) or self._password_hash_needs_upgrade():
                password_record = self._build_password_hash_record(safe_password)
                changed = True
            else:
                password_record = self._current_password_hash_record()
        else:
            password_record = self._blank_password_hash_record()
            if (
                self._payload.get("password_hash")
                or self._payload.get("password_hash_algorithm")
                or self._payload.get("password_hash_salt")
                or self._payload.get("password_hash_iterations")
            ):
                changed = True
            if sessions:
                sessions = []
                changed = True

        if sessions != self._payload.get("sessions"):
            changed = True

        self._payload["version"] = self.VERSION
        self._payload.update(password_record)
        self._payload["sessions"] = sessions
        self._verified_password_cache_key = (
            None
            if not safe_password
            else (
                str(password_record["password_hash_algorithm"]),
                str(password_record["password_hash_salt"]),
                int(password_record["password_hash_iterations"]),
                str(password_record["password_hash"]),
                self._password_cache_fingerprint(safe_password),
            )
        )

        if changed:
            self._write_payload()

    def issue_session(self, password: str | None) -> dict[str, Any] | None:
        if not str(password or ""):
            return None

        self.sync_password(password)
        now = time.time()
        sessions = self._normalize_sessions(now)
        session = {
            "token": secrets.token_urlsafe(32),
            "issued_at": now,
            "last_seen_at": now,
            "expires_at": now + REMOTE_SESSION_TTL_SECONDS,
        }
        sessions.insert(0, session)
        sessions = sessions[:MAX_CONCURRENT_REMOTE_SESSIONS]
        self._payload["sessions"] = sessions
        self._write_payload()
        return dict(session)

    def validate_token(self, token: str | None, password: str | None) -> dict[str, Any] | None:
        normalized_token = self._normalize_token(token)
        if not normalized_token or not str(password or ""):
            return None

        self.sync_password(password)
        now = time.time()
        sessions = self._normalize_sessions(now)
        matched_session: dict[str, Any] | None = None

        for session in sessions:
            session_token = self._normalize_token(session.get("token"))
            if not session_token:
                continue
            if secrets.compare_digest(session_token, normalized_token):
                session["last_seen_at"] = now
                session["expires_at"] = now + REMOTE_SESSION_TTL_SECONDS
                matched_session = dict(session)
                break

        if matched_session is None:
            if sessions != self._payload.get("sessions"):
                self._payload["sessions"] = sessions
                self._write_payload()
            return None

        sessions.sort(key=lambda item: float(item.get("issued_at") or 0.0), reverse=True)
        self._payload["sessions"] = sessions[:MAX_CONCURRENT_REMOTE_SESSIONS]
        self._write_payload()
        return matched_session

    def revoke_token(self, token: str | None) -> bool:
        normalized_token = self._normalize_token(token)
        if not normalized_token:
            return False

        before = len(self._payload.get("sessions", []))
        sessions = [
            session
            for session in self._normalize_sessions()
            if not secrets.compare_digest(
                self._normalize_token(session.get("token")),
                normalized_token,
            )
        ]
        self._payload["sessions"] = sessions
        if len(sessions) == before:
            return False
        self._write_payload()
        return True
