#!/usr/bin/env python3
import os
import sys
from oscore.libconfig2 import Config

sys.path.append("{{SYS_FRAMEWORKS}}/ReachSphere/Libraries/Endpoint")
import enrollment_manager as endpoint


def main():
    args = sys.argv
    if len(args) < 2:
        print("Usage: reachsphere [enroll/withdraw] [namespace] <domain> <email>")
        return

    action = args[1]
    if action == "enroll":
        if len(args) != 5:
            print("Usage: reachsphere enroll [namespace] <domain> <email>")
            return

        namespace = args[2]
        domain = args[3]
        email = args[4]
        enroll(namespace, domain, email)

    elif action == "withdraw":
        if len(args) != 3:
            print("Usage: reachsphere withdraw [namespace]")
            return
        namespace = args[2]
        withdraw(namespace)

    else:
        print("Unknown action. Use 'enroll' or 'withdraw'.")


def enroll(namespace: str, domain: str, email: str):
    # ReachSphere 등록 처리
    if endpoint.is_machine_enrolled(namespace):
        print("This machine is already enrolled in ReachSphere.")
        return

    print(f"Enrolling {email} to ReachSphere with domain {domain}...")

    # 환경 변수에서 RS_ENROLL_PASSWORD, RS_ENROLL_TOTP 읽기
    password = os.getenv("RS_ENROLL_PASSWORD")
    user_totp = os.getenv("RS_ENROLL_TOTP")

    # 없으면 입력 받기
    if not password:
        # 안보이게 입력 받기
        import oscore.getpass2 as getpass2
        password = getpass2.getpass_star(f'Enter password for ReachSphere@{domain}: ')
    if not user_totp:
        user_totp = input(f"Enter your ReachSphere@{domain} TOTP code: ")

    endpoint.enroll_machine(domain=domain, email=email, password=password, user_totp=user_totp, namespace=namespace)

def withdraw(namespace: str):
    # ReachSphere 탈퇴 처리
    if not endpoint.is_machine_enrolled(namespace):
        endpoint._delete_namespace_container(namespace)

        print("This machine is not enrolled in ReachSphere.")
        return

    print("Withdrawing from ReachSphere...")
    configuration: Config = endpoint.get_config(namespace)

    domain: str = configuration.get("domain")
    email: str = configuration.get("email")

    # 환경 변수에서 RS_ENROLL_PASSWORD, RS_ENROLL_TOTP 읽기
    password = os.getenv("RS_ENROLL_PASSWORD")
    user_totp = os.getenv("RS_ENROLL_TOTP")
    if not password:
        # 안보이게 입력 받기
        import oscore.getpass2 as getpass2
        password = getpass2.getpass_star(f'Enter password for ReachSphere@{domain}: ')
    if not user_totp:
        user_totp = input(f"Enter your ReachSphere@{domain} TOTP code: ")


    endpoint.withdraw_machine(namespace, domain, email, password, user_totp)

if __name__ == "__main__":
    main()
