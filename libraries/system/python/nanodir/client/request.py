import requests

from oscore import libreg as reg
from oscore import libapplog as logger
from oscore import libcryptography as cred

from nanodir import protocol as protocol


def make_request(body: dict) -> dict[str, str]:
    header: tuple[str, str] = protocol.make_clientside_header_v1()
    if not header[0]:
        return {}
    enabled: bool = reg.read("HKEY_LOCAL_MACHINE/SYSTEM/ControlSet/Control/GroupEnrollment/Enabled", False)

    if not enabled:
        raise Exception("Directory Service is disabled, unable to make request.")

    body: str = protocol.make_body_v1(body, protocol.client_get_dc_pk())
    dc_address: dict[str, str] = protocol.client_get_dc_address()
    body: str = f"{header[1]}:{body}"

    url: str = dc_address.get("url", "")
    if not url:
        ipv4: str = dc_address.get("ipv4", "")
        if not ipv4:
            raise Exception("Directory Controller address is not configured.")
        port: str = dc_address.get("port", "443" if dc_address.get("use_ssl", True) else "80")
        scheme: str = "https" if dc_address.get("use_ssl", True) else "http"
        url = f"{scheme}://{ipv4}:{port}/"
        print("WARNING: Unable to get URL from registry, constructed URL:", url)

    # HTTP 요청 전송
    requests.get(url, data=body.encode("utf-8"), timeout=10)
    response = requests.post(url, data=body.encode("utf-8"), timeout=10)

    if response.status_code != 200:
        logger.error(f"Directory Service request failed with status code {response.status_code}.")
        return {}

    # Return body
    return protocol.parse_response_v1(response.text, header[0])



def request_policy() -> dict[str, str]:
    # 1차 요청
    # 다음 명령어를 수행할 수 있는 권한 토큰 요청
    body: dict = {
        "request": "GET_POLICY"
    }
    response: dict[str, str] = make_request(body)

    # 응답 파싱
    body: dict = response.get("body", {})
    if not body or "status" not in body or body["status"] != "OK":
        logger.error("Failed to retrieve policy from Directory Service.")
        return {}

    # 챌린지 가져오기
    challenge: str = body.get("challenge", "")
    if not challenge:
        logger.error("No challenge provided in policy response.")
        return {}

    # 챌린지 해독
    decrypted_challenge: str = cred.decrypt(challenge, protocol.client_get_sk())

    # 최종 정책 요청
    body = {
        "request": "GET_POLICY",
        "challenge": decrypted_challenge
    }

    final_response: dict[str, str] = make_request(body)

    body: dict = final_response.get("body", {})
    if not body or "status" not in body or body["status"] != "OK":
        logger.error("Failed to retrieve policy from Directory Service.")
        return {}

    return final_response