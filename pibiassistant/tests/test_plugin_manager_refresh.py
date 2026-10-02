import threading
import unittest

from pibiassistant.utils import plugin_manager


class TestRefreshPluginManager(unittest.TestCase):
    def test_refresh_does_not_deadlock_and_returns_new_instance(self):
        before = plugin_manager.get_plugin_manager()
        box = {}

        def work():
            box["manager"] = plugin_manager.refresh_plugin_manager()

        # refresh_plugin_manager re-enters get_plugin_manager under the same lock
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        worker.join(5)
        self.assertFalse(worker.is_alive(), "refresh_plugin_manager hung on its own lock")
        self.assertIsNot(box["manager"], before)
        self.assertIs(plugin_manager.get_plugin_manager(), box["manager"])
