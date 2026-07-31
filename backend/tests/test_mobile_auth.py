import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_mobile_login_refresh_rotation_and_reuse_rejection(
    client: AsyncClient, test_user
):
    login = await client.post(
        "/api/auth/mobile/login",
        json={
            "email": test_user.email,
            "password": "testpass123",
            "device_name": "Pixel 9",
        },
    )
    assert login.status_code == 200
    first = login.json()
    assert first["expires_in"] == 900
    assert first["refresh_expires_in"] == 90 * 86400
    assert first["access_token"]
    assert first["refresh_token"]

    refreshed = await client.post(
        "/api/auth/mobile/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert refreshed.status_code == 200
    second = refreshed.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert second["session_id"] != first["session_id"]

    reused = await client.post(
        "/api/auth/mobile/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert reused.status_code == 401
    assert reused.json()["detail"]["code"] == "INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_mobile_session_listing_revoke_and_logout_all(
    client: AsyncClient, test_user, auth_headers
):
    tokens = []
    for device_name in ("Phone", "Tablet"):
        response = await client.post(
            "/api/auth/mobile/login",
            json={
                "email": test_user.email,
                "password": "testpass123",
                "device_name": device_name,
            },
        )
        assert response.status_code == 200
        tokens.append(response.json())

    listed = await client.get("/api/auth/mobile/sessions", headers=auth_headers)
    assert listed.status_code == 200
    assert {item["device_name"] for item in listed.json()} == {"Phone", "Tablet"}

    revoked = await client.delete(
        f"/api/auth/mobile/sessions/{tokens[0]['session_id']}",
        headers=auth_headers,
    )
    assert revoked.status_code == 204
    failed_refresh = await client.post(
        "/api/auth/mobile/refresh",
        json={"refresh_token": tokens[0]["refresh_token"]},
    )
    assert failed_refresh.status_code == 401

    logout_all = await client.post("/api/auth/mobile/logout-all", headers=auth_headers)
    assert logout_all.status_code == 200
    second_failed_refresh = await client.post(
        "/api/auth/mobile/refresh",
        json={"refresh_token": tokens[1]["refresh_token"]},
    )
    assert second_failed_refresh.status_code == 401


@pytest.mark.asyncio
async def test_mobile_logout_is_idempotent(client: AsyncClient, test_user):
    login = await client.post(
        "/api/auth/mobile/login",
        json={
            "email": test_user.email,
            "password": "testpass123",
            "device_name": "Android",
        },
    )
    refresh_token = login.json()["refresh_token"]

    for _ in range(2):
        response = await client.post(
            "/api/auth/mobile/logout",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200

    refresh = await client.post(
        "/api/auth/mobile/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh.status_code == 401
