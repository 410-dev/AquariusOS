# ObjectiveShell 사용 매뉴얼

---

## 목차
1. 개요
2. 기본 문법
3. 내장 명령어
4. 변수 & 환경변수
5. 인라인 명령어 (Command Substitution)
6. 외부 명령어 (Python 스크립트)
7. 경로 탐색
8. ExecResult

---

## 1. 개요

**ObjectiveShell**은 Python 기반의 셸 인터프리터입니다. 일반적인 셸(bash, zsh)과 유사하게 동작하지만, Python 객체를 값으로 직접 다룰 수 있다는 점이 특징입니다.

```python
session = ObjectiveShellSession()
result = session.execute_line(session.parse_line("echo Hello World"))
```

---

## 2. 기본 문법

### 명령어 구조

```
<명령어> <인자1> <인자2> ...
```

### 따옴표

| 문법 | 설명 |
|------|------|
| `'text'` | 단일 따옴표: 내용을 그대로 처리 |
| `"text"` | 이중 따옴표: 내용을 그대로 처리, 공백 포함 가능 |

```shell
echo hello world        # 두 개의 토큰: "hello", "world"
echo "hello world"      # 한 개의 토큰: "hello world"
echo 'hello world'      # 한 개의 토큰: "hello world"
```

---

## 3. 내장 명령어

### `echo`
표준 출력으로 인자를 출력합니다.

```shell
echo Hello World
# → Hello World
```

---

### `set`
변수 또는 환경변수를 설정합니다.

```
set var <이름> = <값>
set env <이름> = <값>
```

```shell
set var mynum = 42
set env HOME = /home/user
```

> `=` 는 구분자 역할의 토큰입니다. 반드시 포함해야 합니다.

---

### `unset`
변수 또는 환경변수를 삭제합니다.

```
unset var <이름>
unset env <이름>
```

```shell
unset var mynum
unset env HOME
```

---

### `add`
두 정수를 더합니다. 결과는 `returns`에 담깁니다.

```
add <a> <b>
```

```shell
add 3 5
# → ExecResult(exit_code=0, returns=8)
```

---

### `cd`
현재 작업 디렉토리를 변경합니다.

```
cd <디렉토리>
```

```shell
cd /home/user/projects
cd ..
```

---

### `pwd`
현재 작업 디렉토리를 반환합니다.

```shell
echo $(pwd)
# → /home/user/projects
```

---

### `exit`
셸을 종료합니다. 종료 코드를 인자로 받습니다.

```
exit <코드>
```

```shell
exit 0   # 정상 종료
exit 1   # 오류 종료
```

---

## 4. 변수 & 환경변수

### 설정 및 참조

변수는 `set`으로 설정하고, `${var:이름}` 또는 `${env:이름}`으로 참조합니다.

```shell
set var name = Alice
echo ${var:name}
# → Alice

set env LANG = ko_KR
echo ${env:LANG}
# → ko_KR
```

### 타입 보존

변수가 토큰 전체일 경우, Python 객체 타입이 그대로 유지됩니다.

```shell
set var mylist = $(some_command)
# mylist에 반환된 Python 객체가 그대로 저장됨
```

문자열 안에 삽입될 경우에는 `str()`로 자동 변환됩니다.

```shell
echo "값은: ${var:mylist}"
# → str()로 변환되어 출력
```

### PATH 변수

명령어 탐색 경로를 추가할 수 있습니다.

```shell
# 환경변수 PATH (콜론 구분)
set env PATH = /usr/bin:/usr/local/bin

# 변수 PATH (Python 리스트)
set var PATH = ["/home/user/scripts", "/opt/tools"]
```

---

## 5. 인라인 명령어 (Command Substitution)

`$()` 문법으로 명령어 실행 결과를 다른 명령어의 인자로 사용할 수 있습니다.

### 기본 사용

```shell
echo $(add 3 5)
# → 8
```

### exit_code 참조

```shell
$(add 3 5).exit_code
# → 0
```

### 문자열 안 삽입

```shell
echo "현재 경로는 $(pwd) 입니다"
# → 현재 경로는 /home/user 입니다
```

### 중첩 사용

```shell
echo $(add $(add 1 2) $(add 3 4))
# → 10
```

### 변수에 저장

```shell
set var result = $(add 10 20)
echo ${var:result}
# → 30
```

### 동작 규칙 요약

| 상황 | 동작 |
|------|------|
| `$(cmd)` 단독 토큰 | `returns` 값을 Python 타입 그대로 반환 |
| `"text $(cmd)"` 문자열 안 | `str(returns)`로 변환 후 삽입 |
| `$(cmd).exit_code` | `exit_code` 정수값 반환 |
| 중첩 `$($(cmd))` | 안쪽부터 재귀적으로 실행 |

---

## 6. 외부 명령어 (Python 스크립트)

탐색 경로에 있는 `.py` 파일을 외부 명령어로 실행할 수 있습니다.

### 스크립트 작성 규칙

외부 스크립트는 아래 두 함수 중 하나 이상을 정의해야 합니다.

#### `main(session, *args)`
기본 진입점입니다. 세션 객체와 인자를 받습니다.

```python
# greet.py
def main(session, name):
    print(f"Hello, {name}!")
    return (0, f"Hello, {name}!")
```

```shell
greet Alice
# → Hello, Alice!
```

#### `udef_main(session, *args)`
`main`이 없거나 인자 불일치 시 자동으로 호출되는 폴백 함수입니다. 인자 개수를 유연하게 처리할 때 사용합니다.

```python
# flexible.py
def udef_main(session, args):
    # args는 리스트로 전달됨 (인자 초과 시)
    print(f"받은 인자들: {args}")
    return (0, args)
```

### 반환값 규칙

외부 스크립트의 반환값은 아래 형식을 모두 지원합니다.

| 반환 형식 | 처리 결과 |
|-----------|-----------|
| `ExecResult(code, value)` | 그대로 사용 |
| `(int, value)` 튜플 | `ExecResult(int, value)`로 변환 |
| `int` | `ExecResult(int, None)`로 변환 |
| `str` | `ExecResult(0, str)`로 변환 |
| 그 외 객체 | `ExecResult(0, 객체)`로 변환 |

### 서브디렉토리 명령어

탐색 경로 내의 디렉토리를 토큰으로 입력해 하위 스크립트를 실행할 수 있습니다.

```
# 디렉토리 구조 예시
/scripts/
  math/
    multiply.py
```

```shell
set env PATH = /scripts
math multiply 3 4
# → math 디렉토리 → multiply.py 실행, 인자: ["3", "4"]
```

---

## 7. 경로 탐색

명령어 실행 시 아래 순서로 스크립트를 탐색합니다.

```
1. 현재 작업 디렉토리 (pwd)
2. 환경변수 PATH (콜론으로 구분된 경로들)
3. 변수 PATH (문자열 리스트)
```

같은 이름의 스크립트가 여러 경로에 있을 경우, 위 순서에서 먼저 발견된 것이 실행됩니다.

---

## 8. ExecResult

모든 명령어는 `ExecResult` 객체를 반환합니다.

```python
class ExecResult:
    exit_code: int   # 0 = 성공, 그 외 = 오류
    returns: Any     # 명령어의 반환값 (Python 객체)
```

| `exit_code` | 의미 |
|-------------|------|
| `0` | 정상 실행 |
| `1` | 일반 오류 |
| `-32768` | 명령어를 찾을 수 없음 |

### Python에서 결과 확인

```python
session = ObjectiveShellSession()
result = session.execute_line(session.parse_line("add 10 20"))

print(result.exit_code)   # 0
print(result.returns)     # 30
```

---

## 종합 예시

```shell
# 1. 환경변수 및 경로 설정
set env PATH = /home/user/scripts
set env USER = Alice

# 2. 변수에 계산 결과 저장
set var total = $(add 100 200)

# 3. 결과 출력
echo "합계: ${var:total}"
# → 합계: 300

# 4. 외부 스크립트 실행 및 결과 활용
set var msg = $(greet ${env:USER})
echo ${var:msg}
# → Hello, Alice!

# 5. 중첩 연산
echo $(add $(add 1 2) $(add 3 4))
# → 10

# 6. 서브디렉토리 명령어
math multiply 6 7
# → 42
```