import base64
import json
import random

import libreg as reg
import libapplog as logger
import libcryptography as credentials

def make_clientside_header_v1() -> tuple[str, str]:
    """
    :return: 세션 키, 헤더 문자열
    """
    # 필요값 가져오기
    dc_pk: str = reg.read("HKEY_LOCAL_MACHINE/SYSTEM/ControlSet/Control/GroupEnrollment/Directory/DomainControllerPublicKey", "")
    dc_identifier: str = reg.read("HKEY_LOCAL_MACHINE/SYSTEM/ControlSet/Control/GroupEnrollment/Directory/DomainControllerIdentifier", "")
    registered_id: str = reg.read("HKEY_LOCAL_MACHINE/SYSTEM/ControlSet/Control/GroupEnrollment/VisibleID", "")

    # 값 유효성 체크
    if not dc_pk:
        logger.info("Directory Service is disabled. (Invalid DCPK setup)")
        return "", ""
    if not dc_identifier:
        logger.info("Directory Service is disabled. (Invalid DCID setup)")
        return "", ""
    if not registered_id:
        logger.info("Directory Service is disabled. (Invalid RGID setup)")
        return "", ""

    session_key: str = "".join(random.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=32))

    return session_key, f"DCMP1:{dc_identifier}:{registered_id}:{session_key}"

def make_serverside_header_v1(session_relay: str) -> str:
    is_server_enabled: bool = reg.read("HKEY_LOCAL_MACHINE/SYSTEM/ControlSet/Control/GroupController/Enabled", False)
    if not is_server_enabled:
        logger.info("Directory Service is disabled.")
        return ""
    server_identifier: str = reg.read("HKEY_LOCAL_MACHINE/SYSTEM/ControlSet/Control/GroupController/Identifier", "")
    if not server_identifier:
        logger.info("Directory Service is not configured correctly. (Invalid SRVID setup)")
        return ""
    return f"DSMP1:{server_identifier}:_:{session_relay}"

def parse_response_v1(response: str, decryption_key: str) -> dict[str, str]:

    # 응답 파싱
    lines = response.split(":")

    # 갯수는 5개여야 함
    if len(lines) != 5:
        logger.error("Invalid response format received from Directory Service.")
        return {}

    # 버전 체크
    version = lines[0]
    if version != "DSMP1":
        logger.error(f"Unsupported Directory Service response version: {version}")
        return {}

    # 바디 복호화
    encrypted_body = lines[4]
    try:
        decrypted_b64 = credentials.decrypt(encrypted_body, decryption_key, symmetric=False)
        decrypted_bytes = base64.b64decode(decrypted_b64)
        body_str = decrypted_bytes.decode("utf-8")
        body_dict: dict = json.loads(body_str)
        
        body_dict["header"] = {
            "version": lines[0],
            "server-identifier": lines[1],
            "client-identifier": lines[2],
            "session-relay": lines[3],
        }

    except Exception as e:
        logger.error(f"Failed to decrypt or parse Directory Service response body: {str(e)}")
        return {}

    # 결과 반환
    return body_dict

def make_body_v1(body: dict, encryption_key: str) -> str:
    body_str: str = json.dumps(body)
    body_b64: str = base64.b64encode(body_str.encode("utf-8")).decode("utf-8")
    return credentials.encrypt(body_b64, encryption_key, symmetric=False)

