"""Isolated authentication regressions; importing these modules starts no services."""

from __future__ import annotations

import importlib.util
import json
import secrets
import sys
import types
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from jose import jwt

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def auth_app(monkeypatch):
    def stub(name, **attributes):
        module = types.ModuleType(name)
        module.__path__ = [str(ROOT.joinpath(*name.split(".")))]
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
        return module

    for name in ("app", "app.api", "app.api.endpoints", "app.core", "app.config"):
        stub(name)
    config = SimpleNamespace(
        api_default_username="configured-staff",
        api_default_password=secrets.token_urlsafe(24),
        api_default_fullname="工作人员",
        jwt_secret_key=secrets.token_urlsafe(40),
        jwt_algorithm="HS256",
        jwt_access_token_exp_minutes=60,
        auth_cookie_secure=False,
        public_session_exp_hours=24,
        disable_auth=False,
    )
    stub("app.config.app_config", settings=SimpleNamespace(security=config))

    def load(name):
        path = ROOT.joinpath(*name.split(".")).with_suffix(".py")
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module

    security = load("app.core.security")
    auth = load("app.core.auth")
    access = load("app.core.access")
    endpoints = load("app.api.endpoints.auth")
    application = FastAPI()
    application.include_router(endpoints.router, prefix="/api")

    @application.api_route("/api/staff-check", methods=["GET", "POST"])
    def staff_check(identity=Depends(access.require_staff)):
        return {"username": identity.user.username}

    @application.get("/api/access-check")
    def access_check(identity=Depends(access.get_chat_access)):
        return {"is_staff": identity.is_staff}

    with TestClient(application, base_url="https://testserver") as client:
        yield SimpleNamespace(
            client=client, config=config, security=security, auth=auth, access=access,
            application=application, load=load, stub=stub,
        )


def login(auth_app):
    return auth_app.client.post(
        "/api/auth/login",
        json={
            "username": auth_app.config.api_default_username,
            "password": auth_app.config.api_default_password,
        },
    )


def cookie_claims(auth_app):
    return jwt.decode(
        auth_app.client.cookies.get(auth_app.access.AUTH_COOKIE_NAME),
        auth_app.config.jwt_secret_key,
        algorithms=[auth_app.config.jwt_algorithm],
        audience=auth_app.access.STAFF_AUDIENCE,
    )


def set_staff_claims(auth_app, claims, *, secret=None):
    token = jwt.encode(
        claims,
        auth_app.config.jwt_secret_key if secret is None else secret,
        algorithm=auth_app.config.jwt_algorithm,
    )
    auth_app.client.cookies.clear()
    auth_app.client.cookies.set(auth_app.access.AUTH_COOKIE_NAME, token)


@pytest.mark.parametrize("secure", [False, True])
def test_login_issues_scoped_http_only_cookie_and_restores_session(auth_app, secure):
    auth_app.config.auth_cookie_secure = secure
    response = login(auth_app)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"user", "expires_at", "csrf_token"}
    assert body["user"] == {"username": auth_app.config.api_default_username, "full_name": "工作人员"}
    assert "access_token" not in body and "password" not in body
    cookie = SimpleCookie(response.headers["set-cookie"])[auth_app.access.AUTH_COOKIE_NAME]
    assert cookie["httponly"] and cookie["samesite"] == "strict"
    assert cookie["path"] == "/api" and cookie["domain"] == ""
    assert bool(cookie["secure"]) is secure
    assert int(cookie["max-age"]) == auth_app.config.jwt_access_token_exp_minutes * 60
    claims = cookie_claims(auth_app)
    assert claims["role"] == "staff" and claims["purpose"] == auth_app.access.STAFF_PURPOSE
    assert claims["csrf"] == body["csrf_token"]
    expires_at = datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
    assert expires_at.timestamp() == claims["exp"]
    restored = auth_app.client.get("/api/auth/session")
    assert restored.status_code == 200 and restored.json() == body
    assert response.headers["cache-control"] == restored.headers["cache-control"] == "no-store"


def test_passwords_use_salted_pbkdf2_and_preserve_unicode(auth_app):
    password = "带空格的 密码 🔑"
    first = auth_app.security.get_password_hash(password)
    second = auth_app.security.get_password_hash(password)
    assert first != second and first.startswith("pbkdf2_sha256$600000$")
    assert auth_app.security.verify_password(password, first)
    assert not auth_app.security.verify_password(password + "x", first)
    with pytest.raises(ValueError):
        auth_app.security.verify_password(password, "old-salt$old-digest")


@pytest.mark.parametrize("wrong_field", ["username", "password", "empty_username", "empty_password", "disabled"])
def test_bad_credentials_have_one_unauthorized_response(auth_app, wrong_field):
    credentials = {
        "username": auth_app.config.api_default_username,
        "password": auth_app.config.api_default_password,
    }
    if wrong_field == "disabled":
        auth_app.auth.get_api_user(credentials["username"]).disabled = True
    elif wrong_field.startswith("empty_"):
        credentials[wrong_field.removeprefix("empty_")] = ""
    else:
        credentials[wrong_field] = "incorrect"
    response = auth_app.client.post("/api/auth/login", json=credentials)
    assert response.status_code == 401
    assert response.json() == {"detail": "用户名或密码不正确。"}
    assert "set-cookie" not in response.headers


def test_legacy_disable_auth_does_not_bypass_staff_guard(auth_app):
    auth_app.config.disable_auth = True
    assert auth_app.client.get("/api/auth/session").status_code == 401
    assert auth_app.client.get("/api/staff-check").status_code == 401
    assert auth_app.client.get("/api/access-check", headers={"X-Client-Audience": "staff"}).status_code == 401


@pytest.mark.parametrize("csrf", [None, "incorrect"])
def test_staff_writes_reject_missing_or_bad_csrf(auth_app, csrf):
    assert login(auth_app).status_code == 200
    assert auth_app.client.get("/api/staff-check").status_code == 200
    headers = {} if csrf is None else {"X-CSRF-Token": csrf}
    response = auth_app.client.post("/api/staff-check", headers=headers)
    assert response.status_code == 403


def test_valid_csrf_allows_write_and_logout_only_deletes_validated_cookie(auth_app):
    assert auth_app.client.post("/api/auth/logout").status_code == 401
    body = login(auth_app).json()
    rejected = auth_app.client.post("/api/auth/logout")
    assert rejected.status_code == 403 and "set-cookie" not in rejected.headers
    headers = {"X-CSRF-Token": body["csrf_token"]}
    assert auth_app.client.post("/api/staff-check", headers=headers).status_code == 200
    response = auth_app.client.post("/api/auth/logout", headers=headers)
    assert response.status_code == 200 and response.json() == {"success": True}
    assert SimpleCookie(response.headers["set-cookie"])[auth_app.access.AUTH_COOKIE_NAME]["max-age"] == "0"
    assert auth_app.client.get("/api/auth/session").status_code == 401


@pytest.mark.parametrize("invalid_claim", ["expired", "purpose", "audience", "role", "csrf", "missing_exp", "signature"])
def test_staff_rejects_expired_or_wrong_kind_of_cookie(auth_app, invalid_claim):
    assert login(auth_app).status_code == 200
    claims = cookie_claims(auth_app)
    secret = None
    if invalid_claim == "expired":
        claims["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    elif invalid_claim == "purpose":
        claims["purpose"] = "consultation"
    elif invalid_claim == "audience":
        claims["aud"] = "consultation"
    elif invalid_claim == "role":
        claims["role"] = "public"
    elif invalid_claim == "csrf":
        claims.pop("csrf")
    elif invalid_claim == "missing_exp":
        claims.pop("exp")
    else:
        secret = secrets.token_urlsafe(40)
    set_staff_claims(auth_app, claims, secret=secret)
    assert auth_app.client.get("/api/auth/session").status_code == 401


def test_bearer_login_token_cannot_be_used_as_staff_cookie(auth_app):
    token = auth_app.auth.create_access_token({"sub": auth_app.config.api_default_username})
    auth_app.client.cookies.set(auth_app.access.AUTH_COOKIE_NAME, token)
    assert auth_app.client.get("/api/auth/session").status_code == 401


@pytest.mark.parametrize("removed", [False, True])
def test_staff_guard_rechecks_current_account(auth_app, removed):
    assert login(auth_app).status_code == 200
    username = auth_app.config.api_default_username
    if removed:
        auth_app.auth._users_db.pop(username)
    else:
        auth_app.auth.get_api_user(username).disabled = True
    assert auth_app.client.get("/api/auth/session").status_code == 401


@pytest.mark.parametrize(
    ("field", "value"),
    [("api_default_username", None), ("api_default_password", None), ("jwt_secret_key", None),
     ("jwt_secret_key", "too-short"), ("jwt_algorithm", "none")],
)
def test_missing_staff_configuration_fails_closed(auth_app, field, value):
    credentials = {"username": auth_app.config.api_default_username, "password": auth_app.config.api_default_password}
    setattr(auth_app.config, field, value)
    for response in (
        auth_app.client.post("/api/auth/login", json=credentials),
        auth_app.client.get("/api/auth/session"),
    ):
        assert response.status_code == 503 and "SECURITY__" in response.json()["detail"]
        assert "set-cookie" not in response.headers
    if field in {"api_default_username", "api_default_password"}:
        assert auth_app.auth._seed_users() == {}


def test_public_entry_needs_no_cookie_and_validates_audience(auth_app):
    assert auth_app.client.get("/api/access-check").json() == {"is_staff": False}
    auth_app.client.cookies.set(auth_app.access.AUTH_COOKIE_NAME, "invalid-cookie")
    assert auth_app.client.get("/api/access-check").json() == {"is_staff": False}
    assert auth_app.client.get("/api/access-check", headers={"X-Client-Audience": "other"}).status_code == 400


def test_public_session_uses_unpredictable_storage_id_and_signed_capability(auth_app):
    auth_app.config.api_default_username = None
    auth_app.config.api_default_password = None
    public = auth_app.access.ChatAccess()
    first = auth_app.access.resolve_chat_session(public, "session_browser_placeholder")
    second = auth_app.access.resolve_chat_session(public, "session_browser_placeholder")
    assert first.storage_id.startswith("public:") and first.storage_id != second.storage_id
    assert first.storage_id != first.client_id and len(first.storage_id) <= 255
    assert auth_app.access.resolve_chat_session(public, first.client_id, create=False) == first
    claims = jwt.decode(first.client_id, auth_app.config.jwt_secret_key, algorithms=["HS256"], audience="consultation")
    assert claims["sub"] == first.storage_id and claims["purpose"] == "consultation"
    assert 23 * 3600 < claims["exp"] - datetime.now(timezone.utc).timestamp() <= 24 * 3600


@pytest.mark.parametrize("raw_id", [None, "session_unsigned", "public:00000000-0000-0000-0000-000000000000", "arbitrary-id", "staff:someone:session_private"])
def test_public_history_rejects_unsigned_identifiers(auth_app, raw_id):
    with pytest.raises(HTTPException) as error:
        auth_app.access.resolve_chat_session(auth_app.access.ChatAccess(), raw_id, create=False)
    assert error.value.status_code == 401


@pytest.mark.parametrize("invalid_claim", ["expired", "purpose", "audience", "subject", "signature", "missing_exp"])
def test_public_capability_rejects_expiry_forgery_and_foreign_sessions(auth_app, invalid_claim):
    public = auth_app.access.ChatAccess()
    key = auth_app.access.resolve_chat_session(public, None)
    claims = jwt.decode(key.client_id, auth_app.config.jwt_secret_key, algorithms=["HS256"], audience="consultation")
    secret = auth_app.config.jwt_secret_key
    if invalid_claim == "expired":
        claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    elif invalid_claim == "purpose":
        claims["purpose"] = "staff_session"
    elif invalid_claim == "audience":
        claims["aud"] = "staff"
    elif invalid_claim == "subject":
        claims["sub"] = "staff:someone:session_private"
    elif invalid_claim == "missing_exp":
        claims.pop("exp")
    else:
        secret = secrets.token_urlsafe(40)
    forged = jwt.encode(claims, secret, algorithm="HS256")
    with pytest.raises(HTTPException) as error:
        auth_app.access.resolve_chat_session(public, forged, create=False)
    assert error.value.status_code == (403 if invalid_claim == "subject" else 401)


def test_staff_sessions_cannot_cross_owners_or_reuse_public_capability(auth_app):
    staff = auth_app.access.ChatAccess(user=auth_app.auth.get_api_user(auth_app.config.api_default_username))
    own = auth_app.access.resolve_chat_session(staff, "session_existing")
    assert own.storage_id == staff.namespace + "session_existing" and own.client_id == own.storage_id
    assert auth_app.access.resolve_chat_session(staff, own.client_id, create=False) == own
    other = auth_app.access.ChatAccess(user=auth_app.auth.APIUser(username="another-staff"))
    public = auth_app.access.resolve_chat_session(auth_app.access.ChatAccess(), None)
    for foreign_id in (own.client_id, public.client_id, public.storage_id):
        with pytest.raises(HTTPException) as error:
            auth_app.access.resolve_chat_session(other, foreign_id)
        assert error.value.status_code == 403


def test_session_identifiers_are_bounded_before_use(auth_app):
    public = auth_app.access.ChatAccess()
    with pytest.raises(HTTPException) as error:
        auth_app.access.resolve_chat_session(public, "a" * 2049)
    assert error.value.status_code == 400
    staff = auth_app.access.ChatAccess(user=auth_app.auth.get_api_user(auth_app.config.api_default_username))
    key = auth_app.access.resolve_chat_session(staff, "session_" + "x" * 152)
    assert len(key.storage_id) <= 255
    with pytest.raises(HTTPException):
        auth_app.access.resolve_chat_session(staff, "session_" + "x" * 153)


@pytest.fixture
def chat_app(auth_app, monkeypatch, tmp_path):
    for name in (
        "app.models", "app.utils", "app.agents", "app.agents.framework",
        "app.agents.framework.common", "app.agents.service",
    ):
        auth_app.stub(name)
    auth_app.load("app.models.policy")
    auth_app.load("app.api.schemas")
    auth_app.load("app.utils.lifecycle")
    sessions = auth_app.load("app.agents.framework.common.session_manager").SessionManager()
    service = SimpleNamespace(agentchat_streaming_enabled=False)

    async def answer(message, **kwargs):
        return SimpleNamespace(
            answer="政策答复", confidence=0.8,
            metadata={"session_id": kwargs["session_id"], "route": "knowledge"},
        )

    async def stream_answer(message, **kwargs):
        yield {"type": "chunk", "content": "政策"}
        yield {"type": "final", "answer": await answer(message, **kwargs)}

    service.process_query = AsyncMock(side_effect=answer)
    service.process_query_stream = Mock(side_effect=stream_answer)
    auth_app.stub("app.agents.service.agent_service", AgentService=type("AgentService", (), {}))
    manager_factory_calls = Mock()

    def get_session_manager():
        manager_factory_calls()
        return sessions

    factory_calls = Mock()

    def get_agent_service():
        factory_calls()
        return service

    auth_app.stub("app.api.deps", get_session_manager=get_session_manager, get_agent_service=get_agent_service)
    uploads = auth_app.load("app.api.endpoints.uploads")
    monkeypatch.setattr(uploads, "ATTACHMENT_DIR", tmp_path / "attachments")
    agent = auth_app.load("app.api.endpoints.agent")
    auth_app.application.include_router(agent.router, prefix="/api/agent")
    auth_app.application.include_router(uploads.router, prefix="/api/uploads")
    monkeypatch.setenv("AGENTCHAT_STREAM_ENABLED", "false")
    return SimpleNamespace(
        auth=auth_app, client=auth_app.client, sessions=sessions, service=service,
        uploads=uploads, factory_calls=factory_calls, manager_factory_calls=manager_factory_calls,
    )


@pytest.mark.parametrize("path", ["/chat", "/chat/stream"])
@pytest.mark.parametrize("private_fields", [{"connection_id": 1}, {"connection_id": 0}, {"text2sql_mode": True}, {"user_id": "another-user"}, {"user_id": ""}])
def test_public_private_options_rejected_before_session_or_service(chat_app, path, private_fields):
    response = chat_app.client.post("/api/agent" + path, json={"message": "问题", **private_fields})
    assert response.status_code == 403
    assert chat_app.sessions.list_sessions() == []
    chat_app.service.process_query.assert_not_awaited()
    chat_app.factory_calls.assert_not_called()
    chat_app.manager_factory_calls.assert_not_called()


@pytest.mark.parametrize("path", ["/chat", "/chat/stream"])
def test_invalid_public_capability_rejected_before_factories(chat_app, path):
    response = chat_app.client.post("/api/agent" + path, json={"message": "问题", "session_id": "invalid-token"})
    assert response.status_code == 401
    chat_app.factory_calls.assert_not_called()
    chat_app.manager_factory_calls.assert_not_called()
    chat_app.service.process_query.assert_not_awaited()
    chat_app.service.process_query_stream.assert_not_called()


def test_public_multi_turn_uses_signed_id_and_staff_cannot_list_it(chat_app):
    first = chat_app.client.post("/api/agent/chat", json={"message": "问题", "session_id": "session_local"})
    assert first.status_code == 200
    token = first.json()["session_id"]
    assert token == first.json()["metadata"]["session_id"]
    kwargs = chat_app.service.process_query.await_args.kwargs
    assert kwargs["allow_private_tools"] is False and kwargs["session_id"].startswith("public:")
    storage_id = kwargs["session_id"]
    second = chat_app.client.post("/api/agent/chat", json={"message": "继续", "session_id": token})
    assert second.status_code == 200 and second.json()["session_id"] == token
    assert chat_app.service.process_query.await_args.kwargs["session_id"] == storage_id
    guessed = chat_app.client.post("/api/agent/chat", json={"message": "问题", "session_id": storage_id})
    assert guessed.status_code == 401
    assert chat_app.client.get("/api/agent/sessions").status_code == 401
    assert login(chat_app.auth).status_code == 200
    assert chat_app.client.get("/api/agent/sessions").json()["sessions"] == []
    # A staff login cookie does not silently upgrade a request from the public page.
    assert chat_app.client.post("/api/agent/chat", json={"message": "公众问题"}).status_code == 200
    assert chat_app.service.process_query.await_args.kwargs["allow_private_tools"] is False


def test_staff_chat_requires_cookie_csrf_and_owned_session(chat_app):
    payload = {"message": "问题", "session_id": "session_local", "connection_id": 3}
    assert chat_app.client.post("/api/agent/chat", json=payload, headers={"X-Client-Audience": "staff"}).status_code == 401
    body = login(chat_app.auth).json()
    headers = {"X-Client-Audience": "staff", "X-CSRF-Token": body["csrf_token"]}
    assert chat_app.client.post("/api/agent/chat", json=payload, headers={"X-Client-Audience": "staff"}).status_code == 403
    response = chat_app.client.post("/api/agent/chat", json=payload, headers=headers)
    assert response.status_code == 200
    key = response.json()["session_id"]
    assert key.startswith("staff:") and chat_app.service.process_query.await_args.kwargs["allow_private_tools"] is True
    assert chat_app.client.get("/api/agent/sessions").json()["sessions"][0]["session_id"] == key
    foreign = "staff:000000000000000000000000:session_local"
    assert chat_app.client.get(f"/api/agent/sessions/{foreign}/messages").status_code == 403
    assert chat_app.client.delete(f"/api/agent/sessions/{foreign}", headers=headers).status_code == 403
    assert chat_app.client.get(f"/api/agent/sessions/{key}/messages").json()["total"] == 2


@pytest.mark.parametrize("streamed", [False, True])
def test_sse_uses_public_capability_without_persisting_it_as_storage_metadata(chat_app, monkeypatch, streamed):
    monkeypatch.setenv("AGENTCHAT_STREAM_ENABLED", "true" if streamed else "false")
    chat_app.service.agentchat_streaming_enabled = streamed
    response = chat_app.client.post("/api/agent/chat/stream", json={"message": "问题"})
    assert response.status_code == 200
    frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    token = frames[0]["session_id"]
    assert all(frame["session_id"] == token for frame in frames)
    assert all(frame["metadata"]["session_id"] == token for frame in frames if frame.get("metadata"))
    arguments = chat_app.service.process_query_stream.call_args if streamed else chat_app.service.process_query.await_args
    assert arguments.kwargs["allow_private_tools"] is False
    storage_id = arguments.kwargs["session_id"]
    assert chat_app.sessions.get_messages(storage_id)[-1]["metadata"]["session_id"] == storage_id


def test_staff_uploads_cannot_be_downloaded_or_attached_by_public(chat_app):
    login_body = login(chat_app.auth).json()
    headers = {"X-CSRF-Token": login_body["csrf_token"]}
    response = chat_app.client.post("/api/uploads/staff", files={"file": ("policy.pdf", b"policy", "application/pdf")}, headers=headers)
    assert response.status_code == 200
    uploaded = response.json()
    assert chat_app.client.get(uploaded["url"]).status_code == 200
    public_url = "/api/uploads/" + uploaded["stored_filename"]
    assert chat_app.client.get(public_url).status_code == 404
    refused = chat_app.client.post("/api/agent/chat", json={"message": "问题", "attachments": [{"path": uploaded["path"]}]})
    assert refused.status_code == 400
    chat_app.client.cookies.clear()
    assert chat_app.client.get(uploaded["url"]).status_code == 401


def test_upload_type_size_and_failed_file_cleanup(chat_app, monkeypatch):
    unsupported = chat_app.client.post("/api/uploads", files={"file": ("unsafe.html", b"text/html", "text/html")})
    assert unsupported.status_code == 400
    monkeypatch.setattr(chat_app.uploads, "MAX_ATTACHMENT_BYTES", 4)
    rejected = chat_app.client.post("/api/uploads", files={"file": ("too-large.pdf", b"12345", "application/pdf")})
    assert rejected.status_code == 413
    assert list((chat_app.uploads.ATTACHMENT_DIR / "public").iterdir()) == []


def test_primary_server_mounts_auth_and_guards_every_management_router(auth_app):
    auth_app.stub("dotenv", load_dotenv=lambda: None)
    auth_app.stub("app.models")
    auth_app.stub("app.utils")
    auth_app.load("app.models.policy")
    auth_app.load("app.api.schemas")
    auth_app.load("app.utils.lifecycle")
    for name in ("agent", "dsl", "knowledge", "uploads", "knowledge_graph", "db_connections"):
        router = APIRouter()

        @router.api_route("/check", methods=["GET", "POST"])
        def check():
            return {"success": True}

        auth_app.stub("app.api.endpoints." + name, router=router)
    manager = SimpleNamespace(start=Mock(), stop=AsyncMock())
    auth_app.stub("app.api.deps", close_dependencies=AsyncMock(), get_session_manager=lambda: manager)
    server = auth_app.load("api_server")
    with TestClient(server.app, base_url="https://testserver") as client:
        assert client.get("/api/health").status_code == 200
        for prefix in ("dsl", "knowledge", "knowledge-graph", "db"):
            assert client.get(f"/api/{prefix}/check").status_code == 401
        body = client.post("/api/auth/login", json={
            "username": auth_app.config.api_default_username,
            "password": auth_app.config.api_default_password,
        }).json()
        for prefix in ("dsl", "knowledge", "knowledge-graph", "db"):
            assert client.get(f"/api/{prefix}/check").status_code == 200
            assert client.post(f"/api/{prefix}/check").status_code == 403
            assert client.post(f"/api/{prefix}/check", headers={"X-CSRF-Token": body["csrf_token"]}).status_code == 200


def test_frontend_access_uses_real_login_and_does_not_fake_backend_data(auth_app):
    graph_router = APIRouter()
    preview_router = APIRouter()

    @graph_router.get("/subgraph")
    def subgraph():
        return {"nodes": [], "links": []}

    @preview_router.post("/preview")
    def preview():
        return {"success": True, "result": {"status": "VALID"}}

    auth_app.stub("app.api.endpoints.knowledge_graph", router=graph_router)
    auth_app.stub("app.api.endpoints.rule_preview", router=preview_router)
    application = auth_app.load("scripts.frontend_access").app
    with TestClient(application, base_url="http://localhost") as client:
        assert client.get("/api/auth/session").status_code == 401
        assert client.get("/api/knowledge-graph/subgraph").status_code == 401
        assert client.post("/api/auth/login", json={"username": "unknown", "password": "wrong"}).status_code == 401
        response = client.post("/api/auth/login", json={
            "username": auth_app.config.api_default_username,
            "password": auth_app.config.api_default_password,
        })
        assert response.status_code == 200
        assert client.get("/api/auth/session").json()["user"]["username"] == auth_app.config.api_default_username
        assert client.get("/api/knowledge-graph/subgraph").status_code == 200
        assert client.post("/api/dsl/preview").status_code == 403
        assert client.post("/api/dsl/preview", headers={"X-CSRF-Token": response.json()["csrf_token"]}).status_code == 200
        for path in ("/api/health", "/api/knowledge/documents"):
            assert client.get(path).status_code == 503
