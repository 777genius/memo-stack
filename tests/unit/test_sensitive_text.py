import pytest
from memo_stack_core.application.sensitive_text import (
    contains_sensitive_text,
    redact_sensitive_text,
)
from memo_stack_mcp.domain.models import (
    contains_sensitive_value,
)
from memo_stack_mcp.domain.models import (
    redact_sensitive_text as redact_mcp_sensitive_text,
)


@pytest.mark.parametrize(
    "raw",
    [
        "Bearer abcdefghijklmnopqrstuvwxyz123456",
        "sk-proj-abcdefghijklmnop",
        "sk-svcacct-abcdefghijklmnopqrstuvwxyz123456",
        "sk-abcdefghijklmnop",
        "ghp_abcdefghijklmnop",
        "AKIA1234567890ABCDEF",
        "PASSWORD=super-secret-password-12345",
        "api_key: super-secret-api-key-12345",
        "https://user:password@example.test/path",
        "-----BEGIN PRIVATE KEY-----\nabcdefghijklmnopqrstuvwxyz\n-----END PRIVATE KEY-----",
    ],
)
def test_shared_sensitive_text_policy_covers_common_credentials(raw: str) -> None:
    assert contains_sensitive_text(raw) is True
    assert contains_sensitive_value(raw) is True
    assert raw not in redact_sensitive_text(raw, marker="[redacted-secret]")
    assert raw not in redact_mcp_sensitive_text(raw)


def test_shared_sensitive_text_policy_keeps_non_secret_memory_text() -> None:
    text = "Remember: Memo Stack uses Graphiti for temporal graph projection."

    assert contains_sensitive_text(text) is False
    assert contains_sensitive_value(text) is False
    assert redact_sensitive_text(text, marker="[redacted-secret]") == text
    assert redact_mcp_sensitive_text(text) == text


def test_shared_sensitive_text_policy_allows_safe_env_placeholders() -> None:
    text = 'MEMORY_MCP_AUTH_TOKEN="${MEMORY_MCP_AUTH_TOKEN}"'

    assert contains_sensitive_text(text) is False
    assert contains_sensitive_value(text) is False
    assert redact_sensitive_text(text, marker="[redacted-secret]") == text
    assert redact_mcp_sensitive_text(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "token=[redacted-secret]",
        "api_key=[redacted]",
        "password=<redacted:secret>",
    ],
)
def test_shared_sensitive_text_policy_allows_redacted_placeholders(text: str) -> None:
    assert contains_sensitive_text(text) is False
    assert contains_sensitive_value(text) is False
    assert redact_sensitive_text(text, marker="[redacted-secret]") == text
    assert redact_mcp_sensitive_text(text) == text
