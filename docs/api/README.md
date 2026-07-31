# Android API contract

`openapi-v1.json` is the committed contract for native clients. The backend
still serves the live schema at `/api/openapi.json`; CI fails when the live
schema and committed file differ.

Authentication for Android:

1. `POST /api/auth/mobile/login` with email, password, device name, and an
   optional TOTP code.
2. Keep the returned access token in memory and the refresh token in Android
   Keystore-backed encrypted storage.
3. Send `Authorization: Bearer <access_token>`.
4. On expiry, call `POST /api/auth/mobile/refresh`. Refresh tokens rotate:
   replace the stored token atomically and never reuse the previous value.
5. Use `/sessions`, `/sessions/{id}`, `/logout`, and `/logout-all` for device
   management.

Mobile auth errors use `detail.code` plus a human-readable `detail.message`.
Clients branch on the code, never on translated text.

Generate Retrofit/Kotlin models from the pinned generator:

```bash
mkdir -p generated/android-client
./scripts/generate-android-client.sh
```

Generated sources are intentionally ignored. The OpenAPI file is the source of
truth and the Android repository decides when to regenerate and commit its own
client.

Before accepting a contract update, compare it with the prior version:

```bash
backend/.venv/bin/python backend/scripts/check_openapi_compat.py \
  old-openapi-v1.json docs/api/openapi-v1.json
```

The compatibility check rejects removed paths, operations, responses, schemas,
fields, and newly-required fields. Additive optional fields and endpoints pass.
