import unittest

from src.llm.providers.codex_cli_client import (
    extract_assistant_text_from_codex_json_events,
)


class CodexJsonEventParsingTests(unittest.TestCase):
    def test_extracts_agent_message_when_warnings_are_interleaved(self):
        raw = "\n".join(
            [
                "2026-06-29T17:17:14Z WARN plugin warning",
                '{"type":"thread.started","thread_id":"abc"}',
                '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"JSON_SMOKE_OK"}}',
                '{"type":"turn.completed","usage":{"input_tokens":1,"output_tokens":1}}',
            ]
        )

        text, errors = extract_assistant_text_from_codex_json_events(raw)

        self.assertEqual(text, "JSON_SMOKE_OK")
        self.assertEqual(errors, [])

    def test_collects_error_events(self):
        raw = "\n".join(
            [
                '{"type":"error","message":"bad request"}',
                '{"type":"turn.failed","error":{"message":"turn failed"}}',
            ]
        )

        text, errors = extract_assistant_text_from_codex_json_events(raw)

        self.assertEqual(text, "")
        self.assertEqual(errors, ["bad request", "turn failed"])


if __name__ == "__main__":
    unittest.main()
