# oscore/pyhttp/Webhook.py

from abc import ABC, abstractmethod
import traceback


class WebhookTask(ABC):
    """
    pyhttpd에 등록될 웹훅의 베이스 클래스.

    개발자는 이 클래스를 상속받아 on_request()를 구현합니다.

    Returns:
        tuple[int, dict]
          - int  : HTTP status code (200, 400, 500, ...)
          - dict : Response body (JSON으로 직렬화됨)
    """

    @staticmethod
    @abstractmethod
    def on_request(body: str) -> tuple[int, dict]:
        ...

    # ------------------------------------------------------------------ #
    # 선택적으로 오버라이드 가능한 훅들                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def on_error(exc: Exception) -> tuple[int, dict]:
        """
        on_request 실행 중 예외가 발생했을 때 호출됩니다.
        기본 동작: 500 반환. 오버라이드해서 커스텀 에러 응답 가능.
        """
        traceback.print_exc()
        return 500, {"error": str(exc)}

    @staticmethod
    def validate(body: str) -> bool:
        """
        on_request 호출 전 body 유효성 검사.
        False를 반환하면 400 Bad Request.
        기본 동작: 항상 통과.
        """
        return True

    @classmethod
    def metadata(cls) -> dict:
        """
        인스턴스 정보를 반환합니다. pyhttpd list / status 에서 활용.
        """
        return {
            "class": cls.__name__,
            "module": cls.__module__,
            "doc": cls.__doc__ or "",
        }