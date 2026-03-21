# pyhttpd/loader.py

import importlib.util
import inspect
import os
from osext.pyhttp.Webhook import WebhookTask


class LoadError(Exception):
    """스크립트 로딩 실패 시 발생"""
    pass


def load_webhook(path: str) -> type[WebhookTask]:
    """
    주어진 .py 파일에서 WebhookTask 서브클래스를 찾아 반환합니다.

    Args:
        path: 스크립트 절대경로

    Returns:
        WebhookTask 서브클래스 (인스턴스 아님, 클래스 자체)

    Raises:
        LoadError: 파일 없음 / 서브클래스 없음 / 여러 개 / import 실패
    """
    path = os.path.abspath(path)

    if not os.path.isfile(path):
        raise LoadError(f"File not found: {path}")

    if not path.endswith(".py"):
        raise LoadError(f"Not a Python file: {path}")

    # 모듈 이름 충돌 방지: 파일명 대신 고유 식별자 사용
    module_name = f"_pyhttpd_dyn_{os.path.basename(path)[:-3]}"

    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as e:
        raise LoadError(f"Failed to import {path}: {e}") from e

    # WebhookTask를 상속한 구체 클래스(abstract 아닌 것)만 수집
    found: list[type[WebhookTask]] = [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if (
            issubclass(obj, WebhookTask)
            and obj is not WebhookTask
            and not inspect.isabstract(obj)
            and obj.__module__ == module_name  # 외부에서 import된 클래스 제외
        )
    ]

    if len(found) == 0:
        raise LoadError(f"No concrete WebhookTask subclass found in {path}")

    if len(found) > 1:
        names = [cls.__name__ for cls in found]
        raise LoadError(
            f"Multiple WebhookTask subclasses found in {path}: {names}. "
            "One file must contain exactly one WebhookTask."
        )

    return found[0]