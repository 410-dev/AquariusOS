# AquariusOS

### AquariusOS 란
AquariusOS 는 Ubuntu 시스템에 기능 확장을 위해 설계한 커스텀 시스템입니다.

주요 기능:
1. BTRFS 스냅샷 지원
2. ObjectiveShell
3. 파일 구조 기반 레지스트리 (중앙 설정파일 보관소)
4. AppRun 번들 실행 프레임워크
5. cloudflared, tailscale, ngrok 등 네트워크 유틸리티 빠른 설치
6. libvirtd 빠른 설치
7. 빠른 GUI / CLI 전환 명령어
8. WebDAV 를 이용한 쉬운 파일 공유
9. 시스템 정책 기능 (지원 예정)

### 요구사항
1. Ubuntu 26.04+
2. 4GB 메모리 내외 (VFS 크기 조정시 줄일 수 있음)
3. 별도로 마운트 된 /boot 파티션

### 빌드하기

아래 셸 스크립트는 `build` 디렉터리에 `osaqua.deb` 파일을 생성합니다.
```bash
sudo ./build.sh ./build-configs/aquarius-devel.json
```

