from EdgeMachine import EdgeMachine
from oscore.libconfig2 import Config
from osext.reachsphere.keygen import generate_rsa_keypair, stringify_rsa_key, rsa_decrypt, rsa_encrypt
import requests
import json
import os
import shutil

def get_config(namespace: str) -> Config:
    return Config(f"ReachSphere/{namespace}/endpoint", enforce_global=True)

def is_machine_enrolled(namespace: str) -> bool:
    current_machine = EdgeMachine.get_current_machine(namespace)
    return current_machine.get_network_instance(namespace).is_machine_enrolled(current_machine)

def enroll_machine(namespace: str, domain: str, email: str, password: str, user_totp: str):

    """
    network_name: str
    network_url: str
    machine_type: str
    group: str
    machine_name: str
    owner_email: str
    pk: str
    credentials: str
    user_totp: str
    auth_method: str = "software" # 기본: 'software'
    hardware_ak: str = ""  # TPM 또는 SE에서 생성한 증명키(AK)의 공개키
    hardware_attestation: str = ""  # TPM Quote 또는 App Attest 서명 데이터
    """

    machine_conf: Config = Config("Aqua/System", enforce_global=True).fetch()

    machine_type: str = "server" if machine_conf.get("OSCategory", "Workstation").lower() == "server" else "desktop"

    # 암호화 통신을 위한 임시 RSA 키쌍 생성
    sk, pk = generate_rsa_keypair()

    payload: dict[str, str] = {
        "network_url": domain,
        "machine_type": machine_type,
        "machine_name": machine_conf.ensure_type("MachineName", str).get("MachineName"),
        "owner_email": email,
        "user_totp": user_totp,
        "pk": stringify_rsa_key(pk),
        "credentials": password # TODO Digest password
    }

    # Send request to domain/v1/register_machine
    try:
        response = requests.post(f"{domain}/v1/register_machine", json=payload)
        if response.status_code == 200:
            # Get body data
            data = response.json()

            # Check state code
            if data.get("state") == "OK":
                print("Machine enrolled successfully!")
            else:
                print(f"Enrollment failed. Response: {data}")
                return

            # Decrypt data
            machine_totp_seed: str = data.get("totp_seed")
            client_sk: str = data.get("client_sk")
            server_sk: str = data.get("server_integrity_sk") # 서버의 개인키는 서버의 인증을 위해 PGP 목적으로 뒤집어서 주는 것 - 서버의 공개키를 서버가 가지고 있고, 서버가 키를 암호화 해서 보내주는 방식
            server_pk: str = data.get("server_exchange_pk") # 서버로 보낼 데이터를 위한 PK. 위의 SK 와는 다른 페어.

            success_1, machine_totp_seed = rsa_decrypt(private_key=sk, ciphertext=bytes(machine_totp_seed, "utf-8"))
            success_2, client_sk = rsa_decrypt(private_key=sk, ciphertext=bytes(client_sk, "utf-8"))
            success_3, server_sk = rsa_decrypt(private_key=sk, ciphertext=bytes(server_sk, "utf-8"))

            if not success_1 and not success_2 and not success_3:
                raise ValueError("Error code - REACHSPHERE_CLIENT_RSOK_DEC_FAIL: Failed to decrypt server response with client-generated RSA key. Contact to server administrator.")

            # Create config
            rsconfig: Config = get_config(namespace)
            rsconfig["namespace"] = namespace
            rsconfig["domain"] = domain
            rsconfig["email"] = email
            rsconfig["password"] = password # TODO ???? IS THIS CORRECT???
            rsconfig["machine_totp_seed"] = machine_totp_seed
            rsconfig["client_sk"] = client_sk
            rsconfig["server_integrity_sk"] = server_sk
            rsconfig["server_exchange_pk"] = server_pk
            rsconfig.sync()

        else:
            raise ValueError(f"Failed to enroll machine. Status code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        raise e

def withdraw_machine(namespace: str, domain: str, email: str, password: str, user_totp: str):
    machine_conf: Config = Config("Aqua/System", enforce_global=True).fetch()

    machine_type: str = "server" if machine_conf.get("OSCategory", "Workstation").lower() == "server" else "desktop"

    # 설정값 가져오기
    rsconfig: Config = get_config(namespace).fetch()

    server_exchange_pk: str = rsconfig.get("server_exchange_pk")


    payload: dict[str, str] = {
        "network_url": domain,
        "machine_type": machine_type,
        "machine_name": machine_conf.ensure_type("MachineName", str).get("MachineName"),
        "owner_email": email,
        "user_totp": user_totp,
        "credentials": password  # TODO Digest password
    }

    wrapped_payload: dict[str, str] = {
        "authenticate": "", # TODO Proof that current machine is valid
        "payload": rsa_encrypt(pk_str=server_exchange_pk, plaintext=json.dumps(payload))
    }

    # Send request to domain/v1/withdraw_machine
    try:
        response = requests.post(f"{domain}/v1/withdraw_machine", json=wrapped_payload)
        if response.status_code == 200:
            # Get body data
            data = response.json()

            # Check state code
            if data.get("state") == "OK":
                print("Machine withdrew successfully!")
            else:
                print(f"Withdrawal failed. Response: {data}")
                return

            # Remove directory of config
            _delete_namespace_container(namespace)

        else:
            raise ValueError(
                f"Failed to enroll machine. Status code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        raise e

def _delete_namespace_container(namespace: str):
    config_file: str = get_config(namespace).path
    config_dir: str = os.path.dirname(config_file)
    shutil.rmtree(config_dir, ignore_errors=True)
