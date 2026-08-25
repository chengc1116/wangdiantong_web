import unittest

from wangdian.signing import generate_sign, signing_string


class SigningTests(unittest.TestCase):
    def test_official_sign_example(self) -> None:
        parameters = {
            "appkey": "test2-xx",
            "page_no": "0",
            "end_time": "2016-08-01 13:00:00",
            "start_time": "2016-08-01 12:00:00",
            "page_size": "40",
            "sid": "test2",
            "timestamp": "1470042310",
        }

        self.assertEqual(
            generate_sign(parameters, "12345"),
            "ad4e6fe037ea6e3ba4768317be9d1309",
        )

    def test_uses_utf8_byte_length(self) -> None:
        self.assertEqual(signing_string({"name": "中文"}), "04-name:0006-中文")

    def test_rejects_non_string_values(self) -> None:
        with self.assertRaises(TypeError):
            signing_string({"page_no": 1})  # type: ignore[dict-item]


if __name__ == "__main__":
    unittest.main()

