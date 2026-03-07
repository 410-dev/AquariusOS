#!/bin/bash

PASS=0
FAIL=0
ERRORS=()

run_test() {
    local file="$1"
    local ext="${file##*.}"

    case "$ext" in
        py)
            pytest "$file" -v
            ;;
        bats)
            bats "$file"
            ;;
        nim)
            nim test "$file"
            ;;
        java)
            # 가장 가까운 상위 디렉토리의 gradlew 사용
            local dir
            dir=$(dirname "$file")
            while [ "$dir" != "." ]; do
                if [ -f "$dir/gradlew" ]; then
                    (cd "$dir" && ./gradlew test)
                    return
                fi
                dir=$(dirname "$dir")
            done
            echo "gradlew 를 찾을 수 없습니다: $file"
            return 1
            ;;
        *)
            echo "알 수 없는 테스트 파일 형식: $file"
            return 1
            ;;
    esac
}

# tests/ 아래의 모든 테스트 파일 자동 탐색
while IFS= read -r -d '' file; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  $(realpath --relative-to=. "$file")"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if run_test "$file"; then
        ((PASS++))
    else
        ((FAIL++))
        ERRORS+=("$file")
    fi
done < <(find tests/ -type f \( \
    -name "test_*.py" \
    -o -name "*.bats" \
    -o -name "test_*.nim" \
    -o -name "Test*.java" \
\) -print0)

# 결과 요약
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  결과: ${PASS} 성공 / ${FAIL} 실패"
if [ ${#ERRORS[@]} -gt 0 ]; then
    echo ""
    echo "  실패한 테스트:"
    for err in "${ERRORS[@]}"; do
        echo "    ✗ $err"
    done
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

[ "$FAIL" -eq 0 ]
