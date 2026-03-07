# tests/libraries/system/python/test_libreg.py
import os
import sys
import pytest
import tempfile
import shutil

sys.path.insert(0, "libraries/system/python")
import libreg


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def tmp_hive_map(tmp_path):
    """
    실제 파일시스템 대신 tmp_path 아래에 임시 하이브를 만들어 사용합니다.
    테스트 종료 후 pytest 가 자동으로 삭제합니다.
    """
    hklm = tmp_path / "HKLM"
    hkcu = tmp_path / "HKCU"
    hkvm = tmp_path / "HKVM"
    hkns = tmp_path / "HKNS"

    for d in [hklm, hkcu, hkvm, hkns]:
        d.mkdir()

    return {
        "HKEY_LOCAL_MACHINE":          str(hklm),
        "HKEY_CURRENT_USER":           str(hkcu),
        "HKEY_VOLATILE_MEMORY":        str(hkvm),
        "HKEY_LOCAL_MACHINE_NOINST":   str(hkns),
    }


# ─────────────────────────────────────────────
# 1. 내부 헬퍼 함수
# ─────────────────────────────────────────────

class TestCanonicalHiveName:
    def test_긴_이름_그대로(self):
        assert libreg._canonical_hive_name("HKEY_LOCAL_MACHINE") == "HKEY_LOCAL_MACHINE"

    def test_짧은_이름_변환(self):
        assert libreg._canonical_hive_name("HKLM") == "HKEY_LOCAL_MACHINE"
        assert libreg._canonical_hive_name("HKCU") == "HKEY_CURRENT_USER"
        assert libreg._canonical_hive_name("HKVM") == "HKEY_VOLATILE_MEMORY"
        assert libreg._canonical_hive_name("HKNS") == "HKEY_LOCAL_MACHINE_NOINST"

    def test_알_수_없는_이름(self):
        assert libreg._canonical_hive_name("HKXX") is None
        assert libreg._canonical_hive_name("") is None
        assert libreg._canonical_hive_name(None) is None


class TestSplitHiveAndRel:
    def test_긴_하이브_이름_포함(self):
        hive, rel = libreg._split_hive_and_rel("HKEY_LOCAL_MACHINE/SOFTWARE/MyApp")
        assert hive == "HKEY_LOCAL_MACHINE"
        assert rel  == "SOFTWARE/MyApp"

    def test_짧은_하이브_이름_포함(self):
        hive, rel = libreg._split_hive_and_rel("HKLM/SOFTWARE/MyApp")
        assert hive == "HKEY_LOCAL_MACHINE"
        assert rel  == "SOFTWARE/MyApp"

    def test_하이브_없음(self):
        hive, rel = libreg._split_hive_and_rel("SOFTWARE/MyApp")
        assert hive is None
        assert rel  == "SOFTWARE/MyApp"

    def test_하이브만(self):
        hive, rel = libreg._split_hive_and_rel("HKLM")
        assert hive == "HKEY_LOCAL_MACHINE"
        assert rel  == ""

    def test_앞_슬래시_무시(self):
        hive, rel = libreg._split_hive_and_rel("/HKLM/SOFTWARE")
        assert hive == "HKEY_LOCAL_MACHINE"
        assert rel  == "SOFTWARE"


class TestEncoding:
    def test_기본_인코딩(self):
        assert libreg.encode_key("hello") == "hello"

    def test_공백_인코딩(self):
        assert libreg.encode_key("hello world") == "hello%20world"

    def test_한글_인코딩(self):
        encoded = libreg.encode_key("배경화면")
        assert "%" in encoded  # 퍼센트 인코딩 됨

    def test_인코딩_디코딩_왕복(self):
        original = "my key/with special chars & spaces"
        assert libreg.decode_key(libreg.encode_key(original)) == original

    def test_슬래시_인코딩(self):
        # safe='' 이므로 슬래시도 인코딩되어야 함
        assert "/" not in libreg.encode_key("a/b")


class TestReadValueFile:
    def test_dword(self, tmp_path):
        f = tmp_path / "val.dword.rv"
        f.write_text("42")
        assert libreg._read_value_file(str(f)) == 42

    def test_qword(self, tmp_path):
        f = tmp_path / "val.qword.rv"
        f.write_text("9999999999")
        assert libreg._read_value_file(str(f)) == 9999999999

    def test_float(self, tmp_path):
        f = tmp_path / "val.float.rv"
        f.write_text("3.14")
        assert abs(libreg._read_value_file(str(f)) - 3.14) < 1e-6

    def test_bool_true(self, tmp_path):
        for val in ["1", "true", "yes", "on"]:
            f = tmp_path / "val.bool.rv"
            f.write_text(val)
            assert libreg._read_value_file(str(f)) is True

    def test_bool_false(self, tmp_path):
        for val in ["0", "false", "no", "off"]:
            f = tmp_path / "val.bool.rv"
            f.write_text(val)
            assert libreg._read_value_file(str(f)) is False

    def test_str(self, tmp_path):
        f = tmp_path / "val.str.rv"
        f.write_text("hello")
        assert libreg._read_value_file(str(f)) == "hello"

    def test_list(self, tmp_path):
        f = tmp_path / "val.list.rv"
        f.write_text("a, b, c")
        assert libreg._read_value_file(str(f)) == ["a", "b", "c"]

    def test_list_쉼표_이스케이프(self, tmp_path):
        f = tmp_path / "val.list.rv"
        f.write_text(r"a\,b, c")
        result = libreg._read_value_file(str(f))
        assert result == ["a,b", "c"]

    def test_hex(self, tmp_path):
        f = tmp_path / "val.hex.rv"
        f.write_text("FF")
        assert libreg._read_value_file(str(f)) == 255


# ─────────────────────────────────────────────
# 2. read / write / delete
# ─────────────────────────────────────────────

class TestWrite:
    def test_문자열_쓰기(self, tmp_hive_map):
        libreg.write("root", "HKLM/SOFTWARE/MyApp/Name", "Aquarius",
                     hive_map=tmp_hive_map)
        result = libreg.read("HKLM/SOFTWARE/MyApp/Name",
                             hive_map=tmp_hive_map)
        assert result == "Aquarius"

    def test_정수_dword(self, tmp_hive_map):
        libreg.write("root", "HKLM/SOFTWARE/MyApp/Count", 42,
                     hive_map=tmp_hive_map)
        assert libreg.read("HKLM/SOFTWARE/MyApp/Count",
                           hive_map=tmp_hive_map) == 42

    def test_정수_qword(self, tmp_hive_map):
        libreg.write("root", "HKLM/SOFTWARE/MyApp/BigNum", 9999999999,
                     hive_map=tmp_hive_map)
        assert libreg.read("HKLM/SOFTWARE/MyApp/BigNum",
                           hive_map=tmp_hive_map) == 9999999999

    def test_불리언(self, tmp_hive_map):
        libreg.write("root", "HKLM/SOFTWARE/MyApp/Enabled", True,
                     hive_map=tmp_hive_map)
        assert libreg.read("HKLM/SOFTWARE/MyApp/Enabled",
                           hive_map=tmp_hive_map) is True

    def test_리스트(self, tmp_hive_map):
        libreg.write("root", "HKLM/SOFTWARE/MyApp/Tags", ["a", "b", "c"],
                     hive_map=tmp_hive_map)
        assert libreg.read("HKLM/SOFTWARE/MyApp/Tags",
                           hive_map=tmp_hive_map) == ["a", "b", "c"]

    def test_typedef_강제_지정(self, tmp_hive_map):
        libreg.write("root", "HKLM/SOFTWARE/MyApp/Port", "8080",
                     hive_map=tmp_hive_map, typedef="str")
        result = libreg.read("HKLM/SOFTWARE/MyApp/Port",
                             hive_map=tmp_hive_map)
        # typedef=str 로 강제했으므로 문자열이어야 함
        assert isinstance(result, str)
        assert result == "8080"

    def test_한글_키(self, tmp_hive_map):
        libreg.write("root", "HKLM/SOFTWARE/내앱/이름", "아쿠아리우스",
                     hive_map=tmp_hive_map)
        result = libreg.read("HKLM/SOFTWARE/내앱/이름",
                             hive_map=tmp_hive_map)
        assert result == "아쿠아리우스"

    def test_지원하지_않는_타입(self, tmp_hive_map):
        with pytest.raises(ValueError):
            libreg.write("root", "HKLM/SOFTWARE/MyApp/Bad", {"dict": "value"},
                         hive_map=tmp_hive_map)


class TestRead:
    def test_없는_키_기본값(self, tmp_hive_map):
        result = libreg.read("HKLM/SOFTWARE/NonExistent",
                             default="fallback",
                             hive_map=tmp_hive_map)
        assert result == "fallback"

    def test_없는_키_기본값_None(self, tmp_hive_map):
        result = libreg.read("HKLM/SOFTWARE/NonExistent",
                             hive_map=tmp_hive_map)
        assert result is None

    def test_디렉토리_읽기(self, tmp_hive_map):
        libreg.write("root", "HKLM/SOFTWARE/MyApp/Name",    "Aquarius",
                     hive_map=tmp_hive_map)
        libreg.write("root", "HKLM/SOFTWARE/MyApp/Version", "1.0",
                     hive_map=tmp_hive_map)
        result = libreg.read("HKLM/SOFTWARE/MyApp",
                             hive_map=tmp_hive_map)
        assert isinstance(result, dict)
        assert "Name"    in result
        assert "Version" in result


class TestDelete:
    def test_값_삭제(self, tmp_hive_map):
        libreg.write("root", "HKLM/SOFTWARE/MyApp/Name", "Aquarius",
                     hive_map=tmp_hive_map)
        ok = libreg.delete("HKLM/SOFTWARE/MyApp/Name",
                           hive_map=tmp_hive_map)
        assert ok is True
        assert libreg.read("HKLM/SOFTWARE/MyApp/Name",
                           hive_map=tmp_hive_map) is None

    def test_없는_값_삭제(self, tmp_hive_map):
        ok = libreg.delete("HKLM/SOFTWARE/NonExistent",
                           hive_map=tmp_hive_map)
        assert ok is False

    def test_키_삭제(self, tmp_hive_map):
        libreg.write("root", "HKLM/SOFTWARE/MyApp/Name", "Aquarius",
                     hive_map=tmp_hive_map)
        libreg.delete("HKLM/SOFTWARE/MyApp",
                      hive_map=tmp_hive_map)
        result = libreg.read("HKLM/SOFTWARE/MyApp",
                             hive_map=tmp_hive_map)
        # 디렉토리 삭제 후 읽으면 빈 dict 또는 None
        assert not result


# ─────────────────────────────────────────────
# 3. 우선순위 및 머지
# ─────────────────────────────────────────────

class TestPriority:
    def test_HKVM이_HKLM보다_우선(self, tmp_hive_map):
        # 같은 경로에 HKLM 과 HKVM 둘 다 값이 있을 때 HKVM 이 이겨야 함
        libreg.write("root", "HKLM/SOFTWARE/MyApp/Source", "from_hklm",
                     hive_map=tmp_hive_map)
        libreg.write("root", "HKVM/SOFTWARE/MyApp/Source", "from_hkvm",
                     hive_map=tmp_hive_map)

        # 하이브 미지정 → 우선순위 적용
        result = libreg.read("SOFTWARE/MyApp/Source",
                             hive_map=tmp_hive_map)
        assert result == "from_hkvm"

    def test_HKCU가_HKLM보다_우선(self, tmp_hive_map):
        libreg.write("root", "HKLM/SOFTWARE/MyApp/Theme", "dark",
                     hive_map=tmp_hive_map)
        libreg.write("root", "HKCU/SOFTWARE/MyApp/Theme", "light",
                     hive_map=tmp_hive_map)

        result = libreg.read("SOFTWARE/MyApp/Theme",
                             hive_map=tmp_hive_map)
        assert result == "light"

    def test_하이브_명시하면_우선순위_무시(self, tmp_hive_map):
        libreg.write("root", "HKLM/SOFTWARE/MyApp/Theme", "dark",
                     hive_map=tmp_hive_map)
        libreg.write("root", "HKCU/SOFTWARE/MyApp/Theme", "light",
                     hive_map=tmp_hive_map)

        # HKLM 명시 → HKCU 무시하고 HKLM 값 반환
        result = libreg.read("HKLM/SOFTWARE/MyApp/Theme",
                             hive_map=tmp_hive_map)
        assert result == "dark"

    def test_디렉토리_머지_우선순위(self, tmp_hive_map):
        # HKLM 에 A, B 키 존재
        libreg.write("root", "HKLM/SOFTWARE/MyApp/A", "hklm_a",
                     hive_map=tmp_hive_map)
        libreg.write("root", "HKLM/SOFTWARE/MyApp/B", "hklm_b",
                     hive_map=tmp_hive_map)
        # HKCU 에 B, C 키 존재 (B 는 충돌)
        libreg.write("root", "HKCU/SOFTWARE/MyApp/B", "hkcu_b",
                     hive_map=tmp_hive_map)
        libreg.write("root", "HKCU/SOFTWARE/MyApp/C", "hkcu_c",
                     hive_map=tmp_hive_map)

        result = libreg.read("SOFTWARE/MyApp", hive_map=tmp_hive_map)
        assert "A" in result
        assert "B" in result
        assert "C" in result
        # HKCU 가 HKLM 보다 우선이므로 B 는 hkcu_b 의 타입이어야 함
        assert result["B"] == "str"
