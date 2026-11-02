import asyncio

import pytest

from engine.errors import EngineError
from engine.figma_auth import OAuthStorage
from engine.session_contracts import SessionCreate, SourceInput
from engine.session_models import build_session_model
from engine.session_adapters import AdapterHub, figma_target


def test_local_model_is_disabled_until_explicitly_configured():
    request = SessionCreate(purpose="review", provider="local", sources=[SourceInput(kind="document", content="data")])
    with pytest.raises(EngineError) as error:
        build_session_model(request)
    assert error.value.code == "local_session_model_disabled"


def test_local_model_profile_uses_loopback_without_cloud_fallback(monkeypatch):
    monkeypatch.setattr("engine.session_models.load_reviewer_config", lambda **kwargs: {
        "providers": {"local": {"enabled": True, "base_url": "http://127.0.0.1:1234/v1",
                                 "model": "vision-model", "api_key": "local", "vision": True}},
    })
    request = SessionCreate(purpose="review", provider="local", sources=[SourceInput(kind="document", content="data")])
    model = build_session_model(request)
    assert model.settings.provider == "local"
    assert model.settings.model == "vision-model"
    assert model.supports_images
    monkeypatch.setenv("REVIEW_SESSION_LOCAL_URL", "https://external.example/v1")
    with pytest.raises(EngineError) as error:
        build_session_model(request)
    assert error.value.code == "local_session_model_invalid"


def test_oauth_storage_is_endpoint_bound_and_tokens_not_plaintext(tmp_path):
    from mcp.shared.auth import OAuthToken
    path = tmp_path / "oauth.dat"
    storage = OAuthStorage("https://mcp.figma.com/mcp", path)
    token = OAuthToken(access_token="fixture-token-not-real", token_type="Bearer", expires_in=3600)
    asyncio.run(storage.set_tokens(token))
    assert asyncio.run(storage.get_tokens()).access_token == token.access_token
    assert asyncio.run(OAuthStorage("https://other.example/mcp", path).get_tokens()) is None
    import os
    if os.name == "nt":
        assert b"fixture-token-not-real" not in path.read_bytes()


def test_long_documents_are_read_in_traceable_chunks_not_silently_truncated():
    from engine.session_contracts import SourceRecord, Action
    source = SourceRecord(input=SourceInput(kind="document", content="Section\n" * 4000))
    hub = AdapterHub()
    first = asyncio.run(hub.read("s", source))
    assert first.partial and first.locator["chunk_count"] > 1
    action = Action(source_id=source.source_id, kind="inspect_document", chunk_index=1,
                    expected_state_id=first.state_id, reason="Read more", requires_explicit_authorization=False)
    assert not asyncio.run(hub.needs_authorization("s", source, action))
    second = asyncio.run(hub.act("s", source, action, authorized=False))
    assert second.locator["start_character"] == first.locator["end_character"]
    assert second.state_id != first.state_id


def test_figma_branch_uses_branch_key():
    assert figma_target("https://www.figma.com/design/root/branch/branch123/Test?node-id=1-2") == ("branch123", "1:2")


def test_registration_failure_is_detected_inside_transport_exception_group():
    from engine.figma_auth import _registration_failed
    from mcp.client.auth.exceptions import OAuthRegistrationError
    failure = OAuthRegistrationError("Registration failed: 403 Forbidden")
    assert _registration_failed(ExceptionGroup("transport", [ExceptionGroup("nested", [failure])]))
    assert not _registration_failed(TimeoutError("timeout"))


def test_figma_provider_uses_advertised_client_authentication_method(tmp_path):
    from engine.figma_auth import oauth_provider
    provider = oauth_provider("https://mcp.figma.com/mcp", OAuthStorage("https://mcp.figma.com/mcp", tmp_path / "token.dat"))
    assert provider.context.client_metadata.token_endpoint_auth_method == "client_secret_post"
