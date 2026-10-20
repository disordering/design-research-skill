from engine.config import config_health, load_reviewer_config, validate_reviewer_config
from engine.errors import EngineError
from engine.local_model import LocalModelSettings


def test_local_config_is_valid_and_redacts_key():
    config = load_reviewer_config(required=True)
    assert config["providers"]["qwen"]["reasoning_model"] == "qwen3.8-max-0902"
    health = config_health(config)
    assert "api_key" not in health["providers"]["qwen"]
    assert "api_key_configured" in health["providers"]["qwen"]


def test_placeholder_key_is_reported_without_blocking_syntax(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    config_path = tmp_path / "reviewer.toml"
    config_path.write_text(
        """
[app]
criteria_path = "判据库_v1.json"

[providers.qwen]
enabled = true
api_key = ""
reasoning_model = "qwen3.8-max-0902"
ui_perception_model = "gui-plus-2026-02-26"
ocr_model = "qwen3.5-ocr"
text_embedding_model = "qwen3.7-text-embedding"
text_rerank_model = "qwen3.7-text-rerank"
vlm_embedding_model = "qwen3-vl-embedding"
vlm_rerank_model = "qwen3-vl-rerank"
""".strip(),
        encoding="utf-8",
    )
    config = load_reviewer_config(config_path, required=True)
    errors = validate_reviewer_config(config)
    assert "providers.qwen.api_key is empty" in errors


def test_local_5070ti_settings_are_selectable(tmp_path, monkeypatch):
    config_path = tmp_path / "reviewer.toml"
    config_path.write_text(
        """
[app]
criteria_path = "判据库_v1.json"

[models.local_holo15]
enabled = true
model_id = "Hcompany/Holo1.5-7B"
device = "cuda"
dtype = "auto"
load_in_4bit = true
max_new_tokens = 2048
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("REVIEW_CONFIG", str(config_path))
    settings = LocalModelSettings.from_provider("local_holo")
    assert settings.model_id == "Hcompany/Holo1.5-7B"
    assert settings.load_in_4bit is True
    assert settings.max_new_tokens == 2048


def test_local_provider_respects_disabled_flag():
    try:
        LocalModelSettings.from_provider("local_holo")
    except EngineError as exc:
        assert exc.code == "local_provider_disabled"
    else:
        raise AssertionError("disabled local provider should not be selectable")
