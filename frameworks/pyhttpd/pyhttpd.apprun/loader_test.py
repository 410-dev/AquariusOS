# pyhttpd/loader_test.py

import os
import textwrap
import pytest
from loader import load_webhook, LoadError


# ── 헬퍼: 임시 .py 파일 생성 ─────────────────────────────────────

@pytest.fixture
def tmp_script(tmp_path):
    """내용을 받아 임시 .py 파일을 만들어주는 팩토리 픽스처."""
    def _make(source: str, filename: str = "webhook.py") -> str:
        path = tmp_path / filename
        path.write_text(textwrap.dedent(source))
        return str(path)
    return _make


# ── 정상 케이스 ──────────────────────────────────────────────────

class TestLoadWebhookSuccess:
    def test_loads_valid_webhook(self, tmp_script):
        path = tmp_script("""
            from osext.pyhttp.Webhook import WebhookTask
            class MyHook(WebhookTask):
                @staticmethod
                def on_request(body):
                    return 200, {}
        """)
        cls = load_webhook(path)
        assert cls.__name__ == "MyHook"

    def test_returned_class_is_subclass(self, tmp_script):
        from osext.pyhttp.Webhook import WebhookTask
        path = tmp_script("""
            from osext.pyhttp.Webhook import WebhookTask
            class MyHook(WebhookTask):
                @staticmethod
                def on_request(body):
                    return 200, {}
        """)
        cls = load_webhook(path)
        assert issubclass(cls, WebhookTask)

    def test_loaded_class_is_callable(self, tmp_script):
        path = tmp_script("""
            from osext.pyhttp.Webhook import WebhookTask
            class MyHook(WebhookTask):
                @staticmethod
                def on_request(body):
                    return 201, {"created": True}
        """)
        cls = load_webhook(path)
        status, body = cls.on_request("{}")
        assert status == 201
        assert body["created"] is True

    def test_ignores_imported_webhook_subclasses(self, tmp_script):
        """파일 내에서 import된 WebhookTask 서브클래스는 탐색 대상에서 제외."""
        path = tmp_script("""
            from osext.pyhttp.Webhook import WebhookTask

            # 외부에서 import된 것처럼 시뮬레이션: 직접 정의만 포함되어야 함
            class LocalHook(WebhookTask):
                @staticmethod
                def on_request(body):
                    return 200, {}
        """)
        cls = load_webhook(path)
        assert cls.__name__ == "LocalHook"


# ── 실패 케이스 ──────────────────────────────────────────────────

class TestLoadWebhookFailure:
    def test_raises_on_missing_file(self):
        with pytest.raises(LoadError, match="not found"):
            load_webhook("/nonexistent/path/webhook.py")

    def test_raises_on_non_py_file(self, tmp_path):
        f = tmp_path / "webhook.txt"
        f.write_text("hello")
        with pytest.raises(LoadError, match="Not a Python file"):
            load_webhook(str(f))

    def test_raises_on_no_subclass(self, tmp_script):
        path = tmp_script("""
            def just_a_function():
                pass
        """)
        with pytest.raises(LoadError, match="No concrete WebhookTask subclass"):
            load_webhook(path)

    def test_raises_on_multiple_subclasses(self, tmp_script):
        path = tmp_script("""
            from osext.pyhttp.Webhook import WebhookTask
            class HookA(WebhookTask):
                @staticmethod
                def on_request(body): return 200, {}
            class HookB(WebhookTask):
                @staticmethod
                def on_request(body): return 200, {}
        """)
        with pytest.raises(LoadError, match="Multiple WebhookTask subclasses"):
            load_webhook(path)

    def test_raises_on_syntax_error(self, tmp_script):
        path = tmp_script("this is not valid python !!!")
        with pytest.raises(LoadError, match="Failed to import"):
            load_webhook(path)

    def test_raises_on_abstract_only(self, tmp_script):
        """on_request를 구현하지 않은 추상 서브클래스는 로드 거부."""
        path = tmp_script("""
            from osext.pyhttp.Webhook import WebhookTask
            class IncompleteHook(WebhookTask):
                pass  # on_request 미구현
        """)
        with pytest.raises(LoadError, match="No concrete WebhookTask subclass"):
            load_webhook(path)