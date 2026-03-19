import unittest
import tempfile
import os
import json
from json import JSONDecodeError


# 테스트를 위해 oscore.libatomic.atomic_write 동작을 모방하는 더미 함수
def mock_atomic_write(path, content):
    with open(path, "w") as f:
        f.write(content)

from oscore.libconfig import Config

class TestConfig(unittest.TestCase):

    def setUp(self):
        # 테스트 격리를 위한 임시 디렉토리 생성
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = self.temp_dir.name

    def tearDown(self):
        # 테스트 완료 후 임시 디렉토리 삭제
        self.temp_dir.cleanup()

    def test_general_fetch_and_sync(self):
        # 일반 모드 읽기/쓰기 테스트
        test_file = os.path.join(self.base_path, "test_config.json")

        # 1. 쓰기 테스트
        config_write = Config(path="dummy", resolve_pattern=False)
        config_write.path = test_file  # 시스템 경로 대신 임시 경로로 강제 할당
        config_write["key1"] = "value1"
        config_write["key2"] = 123
        self.assertTrue(config_write.sync())

        # 2. 읽기 테스트
        config_read = Config(path="dummy", resolve_pattern=False)
        config_read.path = test_file
        config_read.fetch()

        self.assertEqual(config_read["key1"], "value1")
        self.assertEqual(config_read["key2"], 123)

    def test_cascade_merge_mode(self):
        # Cascade Merge 모드 우선순위 덮어쓰기 테스트
        priority1 = os.path.join(self.base_path, "p1.json")
        priority2 = os.path.join(self.base_path, "p2.json")

        # p1이 우선순위가 더 낮고, p2가 우선순위가 더 높다고 가정 (나중에 덮어씀)
        with open(priority1, "w") as f: json.dump({"a": 1, "b": 2}, f)
        with open(priority2, "w") as f: json.dump({"b": 99, "c": 3}, f)

        config = Config(
            path="dummy",
            cascade=True,
            cascade_merge_mode=True,
            cascade_priorities=[priority2, priority1]  # 인덱스 0이 가장 높은 우선순위
        )
        config.fetch()

        # p1의 값이 p2에 의해 덮어씌워졌는지 검증
        self.assertEqual(config["a"], 1)
        self.assertEqual(config["b"], 99)  # 2가 99로 덮어씌워져야 함
        self.assertEqual(config["c"], 3)

    def test_resolve_pattern_links_read(self):
        # 외부 파일 참조(_links) 읽기 테스트
        main_file = os.path.join(self.base_path, "main.json")
        link_json_file = os.path.join(self.base_path, "linked.json")
        link_txt_file = os.path.join(self.base_path, "linked.txt")

        # 메인 파일과 링크된 파일들 생성
        main_data = {
            "normal_key": "normal_value",
            "_links": {
                "my_json": link_json_file,
                "my_txt": link_txt_file
            }
        }
        with open(main_file, "w") as f: json.dump(main_data, f)
        with open(link_json_file, "w") as f: json.dump({"nested": "data"}, f)
        with open(link_txt_file, "w") as f: f.write("plain text content")

        config = Config(path="dummy", resolve_pattern=True)
        config.path = main_file
        config.fetch()

        # 링크가 links 딕셔너리로 잘 빠졌는지 확인
        self.assertNotIn("_links", config.data)

        # 일반 키와 링크된 키 읽기 검증
        self.assertEqual(config["normal_key"], "normal_value")
        self.assertEqual(config["my_json"], {"nested": "data"})
        self.assertEqual(config["my_txt"], "plain text content")

    def test_resolve_pattern_links_write(self):
        # 외부 파일 참조(_links) 쓰기 테스트
        main_file = os.path.join(self.base_path, "main.json")
        link_json_file = os.path.join(self.base_path, "linked.json")

        main_data = {
            "_links": {
                "dynamic_link": link_json_file
            }
        }
        with open(main_file, "w") as f: json.dump(main_data, f)

        config = Config(path="dummy", resolve_pattern=True)
        config.path = main_file
        config.fetch()

        # 링크된 키에 새로운 값 할당 (__setitem__ 테스트)
        config["dynamic_link"] = {"new": "updated_data"}

        # 실제 파일 시스템에 잘 기록되었는지 확인
        with open(link_json_file, "r") as f:
            saved_data = json.load(f)
        self.assertEqual(saved_data, {"new": "updated_data"})

    def test_missing_link_file_handling(self):
        # 링크된 파일이 존재하지 않을 때의 예외 처리 흐름 테스트
        main_file = os.path.join(self.base_path, "main.json")
        missing_file = os.path.join(self.base_path, "does_not_exist.json")

        main_data = {"_links": {"missing": missing_file}}
        with open(main_file, "w") as f: json.dump(main_data, f)

        config = Config(path="dummy", resolve_pattern=True)
        config.path = main_file
        config.fetch()

        # get() 메서드는 기본값을 반환해야 함
        self.assertEqual(config.get("missing", "default_val"), "default_val")
        self.assertIsNone(config.get("missing"))

        # __getitem__ 접근 방식은 KeyError를 발생시켜야 함
        with self.assertRaises(KeyError):
            _ = config["missing"]


if __name__ == "__main__":
    unittest.main()
