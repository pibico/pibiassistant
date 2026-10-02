"""Every /assets/pibiassistant/ path that hooks.py injects must exist on disk."""

import os
import unittest

from pibiassistant import hooks

PUBLIC = os.path.join(os.path.dirname(hooks.__file__), "public")
KEYS = ("app_include_js", "app_include_css", "web_include_js", "web_include_css")
PREFIX = "/assets/pibiassistant/"


class TestHooksAssets(unittest.TestCase):
    def test_all_included_assets_exist(self):
        missing, checked = [], 0
        for key in KEYS:
            value = getattr(hooks, key, [])
            for path in [value] if isinstance(value, str) else value:
                if not path.startswith(PREFIX):
                    continue
                checked += 1
                rel = path[len(PREFIX) :].split("?")[0]
                if not os.path.isfile(os.path.join(PUBLIC, rel)):
                    missing.append(f"{key}: {path}")
        self.assertGreater(checked, 10)
        self.assertEqual(missing, [], "hooks.py references assets that do not exist")
