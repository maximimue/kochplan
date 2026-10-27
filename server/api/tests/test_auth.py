async def test_dev_login_and_me(client, user):
    r = await client.get("/v1/me", headers=user["headers"])
    assert r.status_code == 200
    assert r.json()["locale"] == "de"


async def test_unauthorized_localized(client):
    r = await client.get("/v1/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    assert "angemeldet" in r.json()["error"]["message"]


async def test_refresh_rotation_and_reuse_detection(client, user):
    old = user["tokens"]["refresh_token"]
    r = await client.post("/v1/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 200
    new = r.json()["refresh_token"]
    # alter Token erneut -> abgelehnt und alle Sessions widerrufen
    assert (await client.post("/v1/auth/refresh", json={"refresh_token": old})).status_code == 401
    assert (await client.post("/v1/auth/refresh", json={"refresh_token": new})).status_code == 401


async def test_apple_not_configured(client):
    r = await client.post("/v1/auth/apple", json={"id_token": "x"})
    assert r.status_code == 503


async def test_profile_validation(client, user):
    r = await client.patch("/v1/me", headers=user["headers"], json={"appliances": ["herd", "toaster9000"]})
    assert r.status_code == 422
    r = await client.patch("/v1/me", headers=user["headers"], json={"appliances": ["Herd", "backofen"], "supermarket": "aldi"})
    assert r.status_code == 200
    assert r.json()["appliances"] == ["backofen", "herd"]


async def test_delete_account(client, user):
    assert (await client.delete("/v1/me", headers=user["headers"])).status_code == 204
    assert (await client.get("/v1/me", headers=user["headers"])).status_code == 401
