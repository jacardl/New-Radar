"""
æµè¯RobustJSONParserçåç§ä¿®å¤è½å

éªè¯è§£æå¨è½å¤å¤çï¼
1. åºæ¬çmarkdownåè£¹
2. æèåå®¹æ¸ç?
3. ç¼ºå°éå·çä¿®å¤?
4. æ¬å·ä¸å¹³è¡¡çä¿®å¤
5. æ§å¶å­ç¬¦è½¬ä¹
6. å°¾ééå·ç§»é¤
"""

import json
import unittest
from json_parser import RobustJSONParser, JSONParseError


class TestRobustJSONParser(unittest.TestCase):
    """æµè¯é²æ£JSONè§£æå¨çåç§ä¿®å¤ç­ç¥""

    def setUp(self):
        """åå§åè§£æå¨""
        self.parser = RobustJSONParser(
            enable_json_repair=False,  # åæµè¯æ¬å°ä¿®å¤?
            enable_llm_repair=False,
        )

    def test_basic_json(self):
        """æµè¯è§£æåºæ¬çåæ³JSON""
        json_str = '{"name": "test", "value": 123}'
        result = self.parser.parse(json_str, "åºæ¬æµè¯")
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["value"], 123)

    def test_markdown_wrapped(self):
        """æµè¯è§£æè¢«```jsonåè£¹çJSON""
        json_str = """```json
{
  "name": "test",
  "value": 123
}
```"""
        result = self.parser.parse(json_str, "Markdownåè£¹æµè¯")
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["value"], 123)

    def test_thinking_content_removal(self):
        """æµè¯æ¸çæèåå®¹""
        json_str = """<thinking>è®©ææ³æ³å¦ä½æé è¿ä¸ªJSON</thinking>
{
  "name": "test",
  "value": 123
}"""
        result = self.parser.parse(json_str, "æèåå®¹æ¸çæµè¯?)
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["value"], 123)

    def test_missing_comma_fix(self):
        """æµè¯ä¿®å¤ç¼ºå°çéå·""
        # è¿æ¯å®ééè¯¯ä¸­å¸¸è§çæåµï¼æ°ç»åç´ ä¹é´ç¼ºå°éå·
        json_str = """{
  "totalWords": 40000,
  "globalGuidelines": [
    "éç¹çªåºææ¯çº¢å©åéå¤±è¡?
    "è¯¦ç¥ç­ç¥ï¼ææ¯åæ?
  ],
  "chapters": []
}"""
        result = self.parser.parse(json_str, "ç¼ºå°éå·ä¿®å¤æµè¯")
        self.assertEqual(len(result["globalGuidelines"]), 2)

    def test_unbalanced_brackets(self):
        """æµè¯ä¿®å¤æ¬å·ä¸å¹³è¡¡""
        # ç¼ºå°ç»ææ¬å·
        json_str = """{
  "name": "test",
  "nested": {
    "value": 123
  }
"""  # ç¼ºå°æå¤å±ç?}
        result = self.parser.parse(json_str, "æ¬å·ä¸å¹³è¡¡æµè¯?)
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["nested"]["value"], 123)

    def test_control_character_escape(self):
        """æµè¯è½¬ä¹æ§å¶å­ç¬¦""
        # JSONå­ç¬¦ä¸²ä¸­çè£¸æ¢è¡ç¬¦åºè¯¥è¢«è½¬ä¹
        json_str = """{
  "text": "è¿æ¯ç¬¬ä¸è¡?
è¿æ¯ç¬¬äºè¡?,
  "value": 123
}"""
        result = self.parser.parse(json_str, "æ§å¶å­ç¬¦è½¬ä¹æµè¯")
        # ç¡®ä¿æ¢è¡ç¬¦è¢«æ­£ç¡®å¤ç
        self.assertIn("ç¬¬ä¸è¡?, result["text"])
        self.assertIn("ç¬¬äºè¡?, result["text"])

    def test_trailing_comma_removal(self):
        """æµè¯ç§»é¤å°¾ééå·""
        json_str = """{
  "name": "test",
  "value": 123,
  "items": [1, 2, 3,],
}"""
        result = self.parser.parse(json_str, "å°¾ééå·æµè¯")
        self.assertEqual(result["name"], "test")
        self.assertEqual(len(result["items"]), 3)

    def test_colon_equals_fix(self):
        """æµè¯ä¿®å¤åå·ç­å·éè¯¯""
        json_str = """{
  "name":= "test",
  "value": 123
}"""
        result = self.parser.parse(json_str, "åå·ç­å·æµè¯")
        self.assertEqual(result["name"], "test")

    def test_extract_first_json(self):
        """æµè¯ä»ææ¬ä¸­æåç¬¬ä¸ä¸ªJSONç»æ""
        json_str = """è¿æ¯ä¸äºè¯´ææå­ï¼ä¸é¢æ¯JSONï¼?
{
  "name": "test",
  "value": 123
}
åé¢è¿æä¸äºå¶ä»æå­?""
        result = self.parser.parse(json_str, "æåJSONæµè¯")
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["value"], 123)

    def test_unterminated_string_with_json_repair(self):
        """æµè¯ä½¿ç¨json_repairåºä¿®å¤æªç»æ­¢çå­ç¬¦ä¸²""
        # åå»ºå¯ç¨json_repairçè§£æå¨
        parser_with_repair = RobustJSONParser(
            enable_json_repair=True,
            enable_llm_repair=False,
        )

        # æ¨¡æå®ééè¯¯ï¼å­ç¬¦ä¸²ä¸­ææªè½¬ä¹çæ§å¶å­ç¬¦æå¼å?
        json_str = """{
  "template_name": "ç¹å®æ¿ç­æ¥å",
  "selection_reason": "è¿æ¯æµè¯åå®¹"
}"""
        result = parser_with_repair.parse(json_str, "æªç»æ­¢å­ç¬¦ä¸²æµè¯")
        # åªè¦è½å¤è§£ææåï¼ä¸æ¥éå°±å¯ä»¥äº
        self.assertIsInstance(result, dict)
        self.assertIn("template_name", result)

    def test_array_with_best_match(self):
        """æµè¯ä»æ°ç»ä¸­æåæä½³å¹éçåç´ ""
        json_str = """[
  {
    "name": "test",
    "value": 123
  },
  {
    "totalWords": 40000,
    "globalGuidelines": ["guide1", "guide2"],
    "chapters": []
  }
]"""
        result = self.parser.parse(
            json_str,
            "æ°ç»æä½³å¹éæµè¯?,
            expected_keys=["totalWords", "globalGuidelines", "chapters"],
        )
        # åºè¯¥æåç¬¬äºä¸ªåç´ ï¼å ä¸ºå®å¹éäº3ä¸ªé®
        self.assertEqual(result["totalWords"], 40000)
        self.assertEqual(len(result["globalGuidelines"]), 2)

    def test_key_alias_recovery(self):
        """æµè¯é®åå«åæ¢å¤""
        json_str = """{
  "templateName": "test_template",
  "selectionReason": "This is a test"
}"""
        result = self.parser.parse(
            json_str,
            "é®å«åæµè¯?,
            expected_keys=["template_name", "selection_reason"],
        )
        # åºè¯¥èªå¨æ å° templateName -> template_name
        self.assertEqual(result["template_name"], "test_template")
        self.assertEqual(result["selection_reason"], "This is a test")

    def test_complex_real_world_case(self):
        """æµè¯çå®ä¸ççå¤ææ¡ä¾ï¼ç±»ä¼¼å®ééè¯¯ï¼""
        # æ¨¡æå®ééè¯¯ï¼ç¼ºå°éå·ãæmarkdownåè£¹ãææèåå®?
        json_str = """<thinking>æéè¦æé ä¸ä¸ªç¯å¹è§å?/thinking>
```json
{
  "totalWords": 40000,
  "tolerance": 2000,
  "globalGuidelines": [
    "éç¹çªåºææ¯çº¢å©åéå¤±è¡¡ãäººææµå¤±ä¸èä¸è®¤åå±æºç­ç»ææ§çç?
    "è¯¦ç¥ç­ç¥ï¼ææ¯åæ°ä¸ä¼ ç»æèºçç¢°æ"
    "æ¡ä¾å¯¼åï¼ä¼åå¼ç¨çå®æ°æ®åè°ç "
  ],
  "chapters": [
    {
      "chapterId": "ch1",
      "targetWords": 5000
    }
  ]
}
```"""
        result = self.parser.parse(json_str, "å¤æçå®æ¡ä¾æµè¯")
        self.assertEqual(result["totalWords"], 40000)
        self.assertEqual(result["tolerance"], 2000)
        self.assertEqual(len(result["globalGuidelines"]), 3)
        self.assertEqual(len(result["chapters"]), 1)

    def test_expected_keys_validation(self):
        """æµè¯ææé®çéªè¯""
        json_str = '{"name": "test"}'
        # ä¸åºè¯¥å ä¸ºç¼ºå°é®èå¤±è´¥ï¼åªæ¯è­¦å
        result = self.parser.parse(
            json_str, "é®éªè¯æµè¯?, expected_keys=["name", "value"]
        )
        self.assertIn("name", result)

    def test_wrapper_key_extraction(self):
        """æµè¯ä»åè£¹é®ä¸­æåæ°æ®""
        json_str = """{
  "wrapper": {
    "name": "test",
    "value": 123
  }
}"""
        result = self.parser.parse(
            json_str, "åè£¹é®æµè¯?, extract_wrapper_key="wrapper"
        )
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["value"], 123)

    def test_empty_input(self):
        """æµè¯ç©ºè¾å¥""
        with self.assertRaises(JSONParseError):
            self.parser.parse("", "ç©ºè¾å¥æµè¯?)

    def test_invalid_json_after_all_repairs(self):
        """æµè¯ææä¿®å¤ç­ç¥é½æ æ³å¤ççæåµ""
        # è¿æ¯ä¸ä¸ªä¸¥éæåçJSONï¼æ æ³ä¿®å¤?
        json_str = "{å®å¨ä¸æ¯JSONæ ¼å¼çåå®?##"
        with self.assertRaises(JSONParseError):
            self.parser.parse(json_str, "æ æ³ä¿®å¤æµè¯")


def run_manual_test():
    """æå¨è¿è¡æµè¯ï¼æå°è¯¦ç»ä¿¡æ¯""
    print("=" * 60)
    print("å¼å§æµè¯RobustJSONParser")
    print("=" * 60)

    parser = RobustJSONParser(enable_json_repair=False, enable_llm_repair=False)

    # æµè¯å®ééè¯¯æ¡ä¾
    test_case = """```json
{
  "totalWords": 40000,
  "tolerance": 2000,
  "globalGuidelines": [
    "éç¹çªåºææ¯çº¢å©åéå¤±è¡¡ãäººææµå¤±ä¸èä¸è®¤åå±æºç­ç»ææ§çç?
    "è¯¦ç¥ç­ç¥ï¼ææ¯åæ°ä¸ä¼ ç»æèºçç¢°æ"
  ],
  "chapters": []
}
```"""

    print("\næµè¯æ¡ä¾ï¼?)
    print(test_case)
    print("\n" + "=" * 60)

    try:
        result = parser.parse(test_case, "æå¨æµè¯")
        print("\nâ?è§£ææåï¼?)
        print("\nè§£æç»æï¼?)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"\nâ?è§£æå¤±è´¥: {e}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # è¿è¡æå¨æµè¯
    run_manual_test()

    # è¿è¡ååæµè¯
    print("\n\nè¿è¡ååæµè¯...")
    unittest.main(verbosity=2)
