import time

from app import webauth
from tests.conftest import OWNER, TOKEN, connection, hook


def login_fields(user_id=OWNER, auth_date=None, token=TOKEN):
    fields = {"id": user_id, "first_name": "Ayşe", "username": "ayse", "auth_date": int(auth_date or time.time())}
    fields["hash"] = webauth.sign_login({k: str(v) for k, v in fields.items()}, token)
    return fields


def test_site_and_panel_are_served(client):
    assert "Vekil" in client.get("/").text
    assert client.get("/app").status_code == 200 and client.get("/panel").status_code == 200


def test_public_config_has_no_secrets(client):
    data = client.get("/api/public").json()
    assert set(data) == {"product_name", "bot_username", "trial_replies", "plan_stars", "plan_replies", "sales_enabled"}


def test_web_login_issues_session_that_opens_the_panel(client):
    hook(client, connection())
    token = client.post("/api/auth/telegram", json=login_fields()).json()["token"]
    me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["connected"]


def test_forged_or_stale_login_is_rejected(client):
    forged = login_fields()
    forged["id"] = OWNER + 1
    assert client.post("/api/auth/telegram", json=forged).status_code == 401
    assert client.post("/api/auth/telegram", json=login_fields(token="1:other")).status_code == 401
    assert client.post("/api/auth/telegram", json=login_fields(auth_date=time.time() - 2 * 86400)).status_code == 401


def test_session_tokens_cannot_be_tampered_or_reused_after_expiry():
    token = webauth.issue_session(OWNER, TOKEN)
    assert webauth.read_session(token, TOKEN) == OWNER
    uid, exp, sig = token.split(".")
    for bad in (f"{OWNER + 1}.{exp}.{sig}", f"{uid}.{int(exp) + 999}.{sig}", "garbage", token + "x"):
        try:
            webauth.read_session(bad, TOKEN)
            raise AssertionError(bad)
        except webauth.AuthError:
            pass
    old = webauth.issue_session(OWNER, TOKEN, ttl=10, now=time.time() - 100)
    try:
        webauth.read_session(old, TOKEN)
        raise AssertionError("expired accepted")
    except webauth.AuthError:
        pass


def test_bad_bearer_is_401(client):
    assert client.get("/api/me", headers={"Authorization": "Bearer nope"}).status_code == 401
