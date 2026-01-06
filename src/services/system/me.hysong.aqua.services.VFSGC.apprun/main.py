import time

import libapplog as log
import libvfs as vfs
import libreg as reg


def main():

    while True:
        # 레지스트리에서 대기 시간 읽기 (기본값 60초)
        latency_reg = reg.read("SYSTEM/Services/me.hysong.aqua.services.VFSGC/Latency", 60)
        try:
            latency = int(latency_reg)
        except Exception as e:
            log.error(f"Invalid latency value in registry: {latency_reg}")
            latency = 60

        # 레이턴시 시작
        time.sleep(latency)
        
        # VFS 에서 액세스 파일 읽어들이기
        try:
            all_access_files: dict[str, dict[str, any]] = vfs.get_all_access_records()

            # TTL 값 읽기 (기본값 3600초)
            global_ttl = reg.read("SYSTEM/Services/me.hysong.aqua.services.VFSGC/TTL", 3600)
            try:
                global_ttl = int(global_ttl)
            except Exception as e:
                log.error(f"Invalid TTL value in registry: {global_ttl}, using default 3600")
                global_ttl = 3600
            
            # 현재 시간
            current_time = time.time()

            # 각 파일에 대해 검사
            for filename, record in all_access_files.items():
                last_accessed = record.get("last_read_at", 0)
                last_wrote = record.get("last_wrote_at", 0)
                last_accessed = max(last_accessed, last_wrote)  # 읽기/쓰기 중 더 최근 시간 사용
                ttl = record.get("ttl", global_ttl)

                # TTL이 0 이하인 경우 무한대
                if ttl <= 0:
                    continue

                # 마지막 액세스 시간과 현재 시간의 차이 계산
                time_diff = current_time - last_accessed

                # TTL 초과 시 파일 삭제
                if time_diff > ttl:
                    try:
                        success: bool = vfs.delete(filename)
                        if success:
                            log.info(f"Deleted VFS file due to TTL expiry: {filename}")
                        else:
                            log.warning(f"Failed to delete VFS file (not found or inaccessible): {filename}")
                    except Exception as e:
                        log.error(f"Failed to delete VFS file {filename}: {e}")

        except Exception as e:
            log.error(f"Error during VFS GC: {e}")


if __name__ == "__main__":
    main()
