---
icon: material/source-branch
---

# :material-source-branch: Secondary Development Plan

This page is a working plan for secondary development of IntenseRP Next v2. It focuses on changes that reduce regression risk, improve security, and make new provider work less repetitive.

---

## :material-flag-checkered: Current Baseline

Recent hardening work established a small safety net before larger refactors:

- API helper and route tests cover model listing, streaming, non-streaming responses, API-key authentication, request disconnect handling, and message content normalization.
- Remote Control session tests cover session issue/validation, password-change invalidation, empty-password behavior, and session limits.
- Remote Control login now rate-limits repeated password failures per client.
- Network startup warnings flag risky LAN and Remote Control configurations.
- Provider static metadata is centralized in `drivers/descriptors.py` and is now used by model IDs, loadouts, Remote Control icons, and the hotswap dialog.
- CI runs the Python unittest suite on push and pull request.

---

## :material-shield-lock: Phase 1: Security and Regression Guardrails

Priority: high.

1. Add ASGI tests for Remote Control action routes:
   - `/remote/api/session`
   - `/remote/api/state`
   - `/remote/api/action/stop`
   - `/remote/api/action/restart`
   - `/remote/api/action/hotswap`
   - `/remote/api/action/switch-loadout`
   - `/remote/api/action/switch-model`
2. Test IP whitelist enforcement on Remote Control routes, not only OpenAI-compatible API routes.
3. Replace the Remote Control password hash used for session invalidation with a versioned secret or salted KDF design.
4. Add configurable CORS origins for `/v1/*`, with a clear default for localhost-first usage.
5. Add a settings-side security preset flow:
   - Local only
   - LAN API with API keys
   - LAN Remote Control with password and IP whitelist

---

## :material-puzzle: Phase 2: Provider Capability Registry

Priority: high.

The next provider-related refactor should expand `ProviderDescriptor` into the single provider capability registry.

Recommended descriptor fields:

| Field | Purpose |
|---|---|
| `provider` | Stable enum value |
| `driver_class` | Driver factory target |
| `model_prefix` | Legacy and real-model API prefix |
| `owned_by` | OpenAI-compatible model metadata |
| `behavior_category` | Settings schema category |
| `parallel_setting_key` | Providers-in-parallel setting field |
| `icon_path` | Desktop and Remote Control icon |
| `docs_slug` | Provider docs page |
| `supports_real_models` | Whether real model IDs can be exposed |
| `supports_runtime_model_switch` | Whether Remote Control can switch model at runtime |

Target outcome: adding a provider should require adding a descriptor, a driver, schema fields, docs, and focused tests instead of touching many unrelated mapping tables.

---

## :material-remote-desktop: Phase 3: Remote Control Action Registry

Priority: medium-high.

Remote Control actions are currently implemented as route-level branching. Convert them into an action registry with:

- action name
- payload validation
- required runtime state
- busy policy
- permission/security policy
- handler
- optional UI metadata

This makes it easier to add actions such as pause queue, cancel provider queue, show provider health, switch browser profile, and restart only one provider.

---

## :material-heart-pulse: Phase 4: Runtime Health Surface

Priority: medium.

Add a provider health surface that can be reused by the desktop app, Remote Control, and diagnostics.

Suggested state per provider:

- running / stopped
- busy / idle
- queued request count
- processing request ID or mode
- active loadout
- current model label
- account/profile hint
- last error
- last successful generation time

Expose this through Remote Control state first. A dedicated `/remote/api/health` endpoint can come later if the state payload grows too large.

---

## :material-application-brackets: Phase 5: Remote Frontend Maintenance

Priority: medium.

The Remote Control frontend is already split into scripts, but DOM construction is still hand-built in several places. Add a tiny component helper layer for:

- icon-label buttons
- provider options
- dropdown rows
- status rows
- loading states
- safe text insertion

Then add browser or snapshot tests for mobile layout, provider switching, model switching, log streaming, and locked-login messaging.
