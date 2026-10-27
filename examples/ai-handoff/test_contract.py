"""Verify the local trust boundary without replacing model integration tests."""
from unittest.mock import patch
import json
import unittest
from pathlib import Path
from agent_handoff import ANALYST_SCHEMA, REVIEWER_SCHEMA, validate_contract, validate_evidence, local_chat_url

class ContractTests(unittest.TestCase):
    def test_local_endpoint_requires_private_configuration(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(ValueError):
            local_chat_url()

    def test_only_loopback_origins_are_accepted(self):
        for value in ["https://example.com", "http://localhost/path", "http://localhost?token=example", "http://localhost#fragment"]:
            with self.subTest(value=value), patch.dict("os.environ", {"OLLAMA_BASE_URL": value}), self.assertRaises(ValueError):
                local_chat_url()
        with patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://localhost"}):
            self.assertEqual(local_chat_url(), "http://localhost/api/chat")

    def test_rejects_unknown_evidence_reference(self):
        for references in [["production_latency"], [True], [], "sqlite_reads"]:
            with self.subTest(references=references), self.assertRaises(ValueError):
                validate_contract({"summary":"A", "evidence_keys":references, "next_step":"B"}, ANALYST_SCHEMA)

    def test_rejects_action_instead_of_advisory_verdict(self):
        with self.assertRaises(ValueError):
            validate_contract({"verdict":"deploy", "reason":"A", "required_measurement":"B"}, REVIEWER_SCHEMA)

    def test_rejects_unexpected_fields(self):
        with self.assertRaises(ValueError):
            validate_contract({"verdict":"approve", "reason":"A", "required_measurement":"B", "command":"deploy"}, REVIEWER_SCHEMA)

    def test_boolean_is_not_a_measurement(self):
        evidence=json.loads(Path(__file__).with_name("integration-result.json").read_text())
        validate_evidence(evidence)
        evidence["sqlite_reads"]=True
        with self.assertRaises(ValueError):
            validate_evidence(evidence)

    def test_valid_contract_does_not_prove_truth(self):
        validate_contract({"summary":"The system is infinitely fast", "evidence_keys":["sqlite_reads"], "next_step":"Measure"}, ANALYST_SCHEMA)

if __name__ == "__main__":
    unittest.main()
