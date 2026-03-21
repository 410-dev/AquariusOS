# oscore/pyhttp/Webhook_test.py

import pytest
from osext.pyhttp.Webhook import WebhookTask


# ── 픽스처: 최소 구현체 ──────────────────────────────────────────

class OKWebhook(WebhookTask):
    @staticmethod
    def on_request(body: str) -> tuple[int, dict]:
        return 200, {"ok": True}


class ErrorWebhook(WebhookTask):
    @staticmethod
    def on_request(body: str) -> tuple[int, dict]:
        raise ValueError("intentional error")


class ValidatingWebhook(WebhookTask):
    @staticmethod
    def validate(body: str) -> bool:
        return body.strip() != ""

    @staticmethod
    def on_request(body: str) -> tuple[int, dict]:
        return 200, {"body": body}


class CustomErrorWebhook(WebhookTask):
    @staticmethod
    def on_request(body: str) -> tuple[int, dict]:
        raise RuntimeError("boom")

    @staticmethod
    def on_error(exc: Exception) -> tuple[int, dict]:
        return 418, {"custom_error": str(exc)}


# ── 테스트 ───────────────────────────────────────────────────────

class TestWebhookTaskInterface:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            WebhookTask()

    def test_subclass_without_on_request_is_abstract(self):
        class Incomplete(WebhookTask):
            pass
        with pytest.raises(TypeError):
            Incomplete()

    def test_concrete_subclass_is_instantiable(self):
        # 인스턴스화 자체보다 클래스 유효성 확인
        assert issubclass(OKWebhook, WebhookTask)


class TestOnRequest:
    def test_returns_status_and_dict(self):
        status, body = OKWebhook.on_request("")
        assert status == 200
        assert isinstance(body, dict)

    def test_return_type_is_tuple(self):
        result = OKWebhook.on_request("anything")
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestDefaultValidate:
    def test_default_validate_always_passes(self):
        assert OKWebhook.validate("") is True
        assert OKWebhook.validate("some body") is True
        assert OKWebhook.validate("{}") is True

    def test_custom_validate_rejects_empty(self):
        assert ValidatingWebhook.validate("") is False
        assert ValidatingWebhook.validate("  ") is False

    def test_custom_validate_accepts_nonempty(self):
        assert ValidatingWebhook.validate("hello") is True


class TestDefaultOnError:
    def test_default_on_error_returns_500(self):
        exc = ValueError("test")
        status, body = OKWebhook.on_error(exc)
        assert status == 500
        assert "error" in body

    def test_default_on_error_includes_message(self):
        exc = ValueError("something went wrong")
        _, body = OKWebhook.on_error(exc)
        assert "something went wrong" in body["error"]

    def test_custom_on_error_overrides_status(self):
        exc = RuntimeError("boom")
        status, body = CustomErrorWebhook.on_error(exc)
        assert status == 418
        assert body["custom_error"] == "boom"


class TestMetadata:
    def test_metadata_contains_class_name(self):
        meta = OKWebhook.metadata()
        assert meta["class"] == "OKWebhook"

    def test_metadata_contains_module(self):
        meta = OKWebhook.metadata()
        assert "module" in meta

    def test_metadata_doc_is_string(self):
        meta = OKWebhook.metadata()
        assert isinstance(meta["doc"], str)
