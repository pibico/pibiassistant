import unittest

from pibiassistant.pibiassistant_chat.api._helpers import _redact_upstream_internals


class TestRedactUpstreamInternals(unittest.TestCase):
    def test_strips_saas_table_name(self):
        raw = (
            '(1020, "Record has changed since last read in table '
            "'tabAR Tenant User'; try restarting transaction\")"
        )
        out = _redact_upstream_internals(raw)
        self.assertNotIn("tabAR", out)
        self.assertNotIn("AR Tenant User", out)
        self.assertIn("Record has changed since last read", out)

    def test_strips_backticked_table(self):
        out = _redact_upstream_internals("UPDATE `tabAR Tenant User` SET x=1")
        self.assertNotIn("tabAR", out)
        self.assertIn("[internal table]", out)

    def test_strips_module_path(self):
        out = _redact_upstream_internals("assistant_runtime.agent.agent_pool.AgentPool failed")
        self.assertNotIn("assistant_runtime", out)

    def test_renames_legacy_stream_error_title(self):
        out = _redact_upstream_internals("AR stream_error: LLM_UNAVAILABLE")
        self.assertNotIn("AR stream_error", out)
        self.assertIn("PA Chat stream error", out)
