import unittest

from gemma_client import GemmaClient


class GemmaOutputFormattingTests(unittest.TestCase):
    def test_extracts_answer_and_removes_markdown_markers(self):
        value = GemmaClient._user_facing_text(
            "<think>Internal plan</think><answer>## Verdict\n"
            "**Harmony Lodge** is affordable.\n"
            "* Inspect before paying\n"
            "* Ask for a receipt</answer>"
        )
        self.assertEqual(
            value,
            "Verdict\nHarmony Lodge is affordable.\n"
            "• Inspect before paying\n"
            "• Ask for a receipt",
        )
        self.assertNotIn("**", value)
        self.assertNotIn("<think>", value)

    def test_converts_json_reply_to_plain_text(self):
        value = GemmaClient._user_facing_text(
            '{"reply":"Harmony Lodge costs ₦150,000 per year."}'
        )
        self.assertEqual(value, "Harmony Lodge costs ₦150,000 per year.")
        self.assertNotIn("{", value)

    def test_removes_other_markdown_and_html_syntax(self):
        value = GemmaClient._user_facing_text(
            "> ~~Old warning~~\n---\n"
            "- [x] Verify the address\n"
            "<strong>Safe step</strong>\n"
            "| Rent | ₦150,000 |\n"
            "| --- | --- |"
        )
        self.assertEqual(
            value,
            "Old warning\n"
            "• Verify the address\n"
            "Safe step\n"
            "Rent · ₦150,000",
        )


if __name__ == "__main__":
    unittest.main()
