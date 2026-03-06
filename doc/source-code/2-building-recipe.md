# Build Recipe System

AquariusOS 빌드 레시피는 JSON5 포맷으로 작성되며,
`common.json5` 와 에디션별 레시피로 구성됩니다.

## 파일 구조

```
.build/
└── recipes/
    ├── common.json5          # 모든 에디션 공통 베이스
    └── editions/
        ├── home.json5
        ├── enterprise.json5
        ├── server.json5
        └── devel.json5
```

## 빌드 흐름

```
common.json5 로드
    ↓
edition.json5 로드 후 딥 머지
    ↓
키 충돌 검사 → 충돌 시 빌드 실패
    ↓
Output.Filename 선언 여부 검사 → null 이면 빌드 실패
    ↓
Components 처리 (Include/Exclude)
    ↓
Mapping 검증
    ↓
변수 평가 ($run, $ref)
    ↓
소스코드 텍스트 치환 ({{VARIABLE}})
    ↓
PostBuild 실행
```

## 딥 머지 규칙

- `common.json5` 와 `edition.json5` 의 키셋은 완전히 분리되어야 합니다.
- 중첩된 키도 포함하여 **겹치는 키가 하나라도 있으면 빌드 실패**합니다.
- 단, 아래 키는 에디션에서 오버라이드가 허용됩니다:
  - `Mapping` (에디션 전용 매핑 추가)
  - `Output.Filename`

## common.json5 레퍼런스

```json5
{
    "StructType": "BuildRecipe",      // 고정값
    "StructVersion": 2,               // 레시피 스키마 버전

    // 빌드 메타정보
    "Name": "AquariusOS",
    "Codename": "Genesis",
    "ReleaseType": "Experimental",    // Experimental | Stable | LTS
    "Upstream": "Ubuntu",

    // 동적 변수
    // $run: 빌드 시점에 쉘 명령어 실행 후 결과값 사용
    // $ref: 같은 Variables 블록 안의 다른 키 참조
    "Variables": {
        "BUILD_DATE": { "$run": "date +%y%m.%d.%H%M%S" },
        "VERSION":    { "$run": "date +%y%m.%d.%H%M" },
        "RUNNER":     { "$run": "whoami" },
    },

    // 소스코드 텍스트 치환
    // 소스 파일 안의 {{VARIABLE}} 을 Variables 값으로 치환
    "Substitutions": {
        "Delimiter": ["{{", "}}"],
        "Apply": [
            "**/*.sh", "**/*.py",
            "**/*.json", "**/*.conf",
        ],
        "Skip": [
            "**/*.jar", "**/*.class",
            "**/*.png", "**/*.jpg", "**/*.jpeg",
            "**/*.zip", "**/*.tar", "**/*.gz",
        ]
    },

    // 소스 경로 → 설치 경로 매핑
    // Include 된 컴포넌트가 Mapping 에 없으면 빌드 실패
    // Exclude 된 컴포넌트가 Mapping 에 있으면 경고 후 무시
    "Mapping": {
        "root-skeleton":           "/",
        "system/core":             "/opt/aqua/sys",
        // ...
    },

    // 전처리기 설정
    "Preprocessor": {
        // 파일명/경로 문자열 치환 (소스코드 내용이 아닌 경로 자체)
        "PathReplacements": {
            "aisp": "aqua",
            // ...
        },
        // 빌드에서 제외할 파일
        "Blacklist": [".DS_Store", "Thumbs.db"],
        // 실행 권한을 부여할 파일 패턴
        "SetExecutables": [
            "*.sh", "*.py",
            "preinst", "postinst", "prerm", "postrm"
        ],
    },

    // 서브모듈 빌드 순서 (의존성 순서대로)
    "BuildPriority": [
        "libraries/extension/java/libcodablejson",
        "libraries/extension/java/libcodablejdbc",
        "libraries/system",
        "libraries/extension",
    ],

    // 특정 오류 무시 설정
    "IgnoreErrors": {
        "FileNotFoundError": [
            "libraries/extension/java/libcodablejdbc/lib/libcodablejson"
        ]
    },

    // PostBuild 커맨드 템플릿
    // {{VARIABLE}} 으로 Variables 값 참조 가능
    "PostBuild": [
        ["sudo", "chown", "-R", "root:root",             "{{Temporary}}/step_1"],
        ["sudo", "chmod", "-R", "755",                   "{{Temporary}}/step_1"],
        ["sudo", "dpkg-deb", "--build",                  "{{Temporary}}/step_1"],
        ["sudo", "chown", "{{RUNNER}}:{{RUNNER}}",       "{{Temporary}}/step_1.deb"],
        ["sudo", "chmod", "644",                         "{{Temporary}}/step_1.deb"],
        ["sudo", "chown", "-R", "{{RUNNER}}:{{RUNNER}}", "{{Temporary}}/step_1"],
        ["mv",   "{{Temporary}}/step_1.deb",             "{{Output}}/{{EDITION_FILENAME}}.deb"],
        ["rm",   "-rf",                                  "{{Temporary}}"],
    ],

    // 패키징 출력 설정
    // Filename 은 반드시 에디션에서 선언해야 함 (null 이면 빌드 실패)
    "Output": {
        "Filename": null,
        "Patterns": ["*.deb"],
    },
}
```

## edition.json5 레퍼런스

```json5
{
    "StructType": "BuildRecipeEdition",  // 고정값
    "StructVersion": 2,

    // 에디션 메타정보
    "Edition": "home",                   // home | enterprise | server | devel
    "DisplayName": "AquariusOS",
    "PrettyName": "AquariusOS",

    // 에디션 전용 변수
    // common.json5 의 Variables 와 키가 겹치면 빌드 실패
    "Variables": {
        "EDITION": "home",
        "EDITION_DISPLAY": "Home",
        "EDITION_FILENAME": "osaqua-home",
    },

    // 에디션 전용 추가 매핑
    // common.json5 의 Mapping 에 병합됨
    // 키 충돌 시 빌드 실패
    "Mapping": {
        "branding/home":       "/",
        "package-meta/ubuntu": "/DEBIAN",
    },

    // 컴포넌트 구성
    "Components": {
        // blacklist: 기본 전체 포함, Exclude 만 제외
        // whitelist: 기본 전체 제외, Include 만 포함
        "Mode": "blacklist",

        // Blacklist 모드일 때 사용
        "Exclude": [
            "features/server",
            "features/file-exchange-server",
        ],

        // Whitelist 모드일 때 사용
        // "Include": [
        //     "system/*",
        //     "frameworks/*",
        // ],

        // 기본값은 OFF, 여기 명시된 것만 설치 시 기본 ON
        "DefaultOn": [
            "features/motd",
        ]
    },

    // Output.Filename 은 반드시 선언해야 함
    "Output": {
        "Filename": "osaqua-home",
    },
}
```

## 컴포넌트 구성 규칙

### Blacklist 모드
- 전체 컴포넌트가 기본 포함됩니다.
- `Exclude` 에 명시된 것만 제외됩니다.
- 대부분의 컴포넌트를 포함하는 에디션에 적합합니다. (Home, Enterprise)

### Whitelist 모드
- 전체 컴포넌트가 기본 제외됩니다.
- `Include` 에 명시된 것만 포함됩니다.
- 구성이 크게 다른 에디션에 적합합니다. (Server)
- `Include` 에 명시된 항목이 `Mapping` 에 없으면 빌드 실패합니다.

### 활성화 상태
- 모든 기능의 기본 상태는 **OFF** 입니다.
- `DefaultOn` 에 명시된 것만 설치 시 기본 ON 으로 설정됩니다.
- `Exclude` 된 항목이 `Mapping` 에 있으면 **경고** 를 출력하고 무시합니다.
- `Include` 된 항목이 `Mapping` 에 없으면 **빌드 실패** 합니다.

## 새 에디션 추가하기

에디션 파일에서 선언해야 하는 것은 4가지입니다:

```
1. 에디션 메타정보    Edition, DisplayName, PrettyName
2. 에디션 전용 변수   EDITION, EDITION_DISPLAY, EDITION_FILENAME
3. 브랜딩 매핑        Mapping
4. 컴포넌트 구성      Components
```

새 에디션 추가 시 `common.json5` 는 수정할 필요가 없습니다.

## 변수 참조 문법

| 문법 | 설명 | 예시 |
|------|------|------|
| `{ "$run": "..." }` | 빌드 시점에 쉘 명령어 실행 | `{ "$run": "date +%Y" }` |
| `{ "$ref": "..." }` | 같은 Variables 블록의 다른 키 참조 | `{ "$ref": "VERSION" }` |
| `{{VARIABLE}}` | 소스코드/커맨드 안에서 변수 치환 | `{{BUILD_DATE}}` |
