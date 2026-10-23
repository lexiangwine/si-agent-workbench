import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

from workbench.providers import (NoRedirect, build_request, complete, parse_result,
                                 profile_for, validate_endpoint)
from workbench.storage import WorkbenchError


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.p = {"api":"responses", "endpoint":"https://api.example.com/v1/responses",
                  "allowed_hosts":["api.example.com"], "api_key_env":"TEST_API_KEY",
                  "model":"test-model", "max_output_tokens":1000, "timeout_seconds":2}
        self.env = patch.dict(os.environ, {"TEST_API_KEY":"test-credential-only"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_responses_payload(self):
        req = build_request(self.p, "测试内容")
        body = json.loads(req.data)
        self.assertFalse(body["store"])
        self.assertEqual(1000, body["max_output_tokens"])
        self.assertEqual("测试内容", body["input"])

    def test_chat_payload_and_token_parameter(self):
        self.p.update(api="chat_completions", token_field="max_completion_tokens")
        body = json.loads(build_request(self.p, "测试").data)
        self.assertEqual(1000, body["max_completion_tokens"])
        self.assertFalse(body["stream"])

    def test_anthropic_payload(self):
        self.p.update(api="anthropic_messages", workspace_id="workspace-test")
        req = build_request(self.p, "测试")
        self.assertEqual("2023-06-01", req.get_header("Anthropic-version"))
        self.assertEqual("workspace-test", req.get_header("Anthropic-workspace-id"))
        self.assertEqual(1000, json.loads(req.data)["max_tokens"])

    def test_missing_key_blocks(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(WorkbenchError):
            build_request(self.p, "内容")

    def test_reject_bad_endpoint_or_host(self):
        for url in ("http://api.example.com/v1", "https://key@api.example.com/v1",
                    "https://api.example.com/v1?api_key=secret", "https://unapproved.example/v1"):
            with self.subTest(url=url), self.assertRaises(WorkbenchError):
                validate_endpoint({**self.p, "endpoint":url})

    def test_redirect_never_forwards_credential(self):
        with self.assertRaises(WorkbenchError):
            NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.example")

    def test_parse_three_protocols(self):
        samples = {
            "responses":{"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":"OK"}]}]},
            "chat_completions":{"choices":[{"finish_reason":"stop","message":{"content":"OK"}}]},
            "anthropic_messages":{"stop_reason":"end_turn","content":[{"type":"text","text":"OK"}]} }
        for api, sample in samples.items():
            with self.subTest(api=api):
                self.assertEqual("OK\n", parse_result(api, sample).text)

    def test_refuse_truncated_empty_and_malformed_output(self):
        for api, data in (("responses", {"status":"incomplete"}),
                          ("chat_completions", {"choices":[{"finish_reason":"length"}]}),
                          ("anthropic_messages", {"stop_reason":"max_tokens"}),
                          ("responses", {"status":"completed","output":[]}),
                          ("chat_completions", {}), ("responses", []),
                          ("chat_completions", {"choices":[None]}),
                          ("responses", {"status":"completed", "output":[None]})):
            with self.subTest(api=api, data=data), self.assertRaises(WorkbenchError):
                parse_result(api, data)

    def test_usage_keeps_numeric_counts_only(self):
        data = {"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":"OK"}]}],
                "usage":{"input_tokens":10,"private_field":"do-not-log","nested":{"value":1}}}
        self.assertEqual({"input_tokens":10}, parse_result("responses", data).usage)

    def test_config_models_from_environment(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "providers.json"
            p.write_text(json.dumps({"default_provider":"test","providers":{"test":{**self.p,"model":"env:TEST_MODEL"}}}))
            with patch.dict(os.environ, {"TEST_MODEL":"chosen-model"}):
                self.assertEqual("chosen-model", profile_for(p, "analyst")[1]["model"])
            with patch.dict(os.environ, {}, clear=True), self.assertRaises(WorkbenchError):
                profile_for(p, "analyst")

    def test_plaintext_key_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "providers.json"
            p.write_text(json.dumps({"default_provider":"test","providers":{"test":{**self.p,"api_key":"bad"}}}))
            with self.assertRaises(WorkbenchError):
                profile_for(p, "analyst")

    def test_http_failure_does_not_disclose_body_or_retry(self):
        opener = MagicMock()
        opener.open.side_effect = HTTPError(self.p["endpoint"], 401, "denied", {}, io.BytesIO(b"reflected-private-data"))
        with patch("workbench.providers.request.build_opener", return_value=opener), self.assertRaises(WorkbenchError) as caught:
            complete(self.p, "private prompt")
        self.assertNotIn("private", str(caught.exception))
        opener.open.assert_called_once()

    def test_timeout_does_not_retry(self):
        opener = MagicMock()
        opener.open.side_effect = URLError("connection failure")
        with patch("workbench.providers.request.build_opener", return_value=opener), self.assertRaises(WorkbenchError):
            complete(self.p, "data")
        opener.open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
