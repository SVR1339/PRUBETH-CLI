import unittest
from prubeth.config.manager import ConfigManager
from prubeth.config.schema import SETTING_REGISTRY, validate_setting_value

class TestSettingsSchema(unittest.TestCase):

    def setUp(self):
        self.cfg_mgr = ConfigManager()

    def test_all_registry_settings_have_metadata(self):
        for key, defn in SETTING_REGISTRY.items():
            self.assertEqual(key, defn.key)
            self.assertTrue(len(defn.label) > 0)
            self.assertTrue(len(defn.description) > 0)
            self.assertTrue(len(defn.impact) > 0)
            self.assertIn(defn.value_type, ["bool", "int", "str", "choice"])

    def test_boolean_validation(self):
        valid, val, err = validate_setting_value("enable_prompt_caching", "true")
        self.assertTrue(valid)
        self.assertEqual(val, True)

        valid, val, err = validate_setting_value("enable_prompt_caching", "off")
        self.assertTrue(valid)
        self.assertEqual(val, False)

        valid, val, err = validate_setting_value("enable_prompt_caching", "invalid_bool")
        self.assertFalse(valid)
        self.assertIn("expects a boolean", err)

    def test_integer_range_validation(self):
        # In range
        valid, val, err = validate_setting_value("watchdog_timeout_s", "60")
        self.assertTrue(valid)
        self.assertEqual(val, 60)

        # Out of bounds (> 300)
        valid, val, err = validate_setting_value("watchdog_timeout_s", "500")
        self.assertFalse(valid)
        self.assertIn("must be between", err)

        # Out of bounds (< 5)
        valid, val, err = validate_setting_value("watchdog_timeout_s", "2")
        self.assertFalse(valid)
        self.assertIn("must be between", err)

    def test_choice_validation(self):
        # Valid choice
        valid, val, err = validate_setting_value("plan_b_strategy", "auto_pivot")
        self.assertTrue(valid)
        self.assertEqual(val, "auto_pivot")

        # Invalid choice
        valid, val, err = validate_setting_value("plan_b_strategy", "chaos_mode")
        self.assertFalse(valid)
        self.assertIn("must be one of", err)

    def test_config_manager_inspect_setting(self):
        meta = self.cfg_mgr.inspect_setting("speculative_plan_b")
        self.assertIsNotNone(meta)
        self.assertEqual(meta["key"], "speculative_plan_b")
        self.assertEqual(meta["type"], "bool")
        self.assertIn("zero-stoppage", meta["recommendation"].lower())

        # Unknown setting
        unknown = self.cfg_mgr.inspect_setting("non_existent_key")
        self.assertIsNone(unknown)

    def test_config_manager_set_validation(self):
        # Setting with valid value
        self.cfg_mgr.set("watchdog_timeout_s", 50)
        self.assertEqual(self.cfg_mgr.get("watchdog_timeout_s"), 50)

        # Setting with invalid value should raise ValueError
        with self.assertRaises(ValueError):
            self.cfg_mgr.set("watchdog_timeout_s", 9999)

        # Reset back
        self.cfg_mgr.set("watchdog_timeout_s", 45)

    def test_config_manager_toggle_rejection_on_non_bool(self):
        with self.assertRaises(ValueError):
            self.cfg_mgr.toggle("default_model")

if __name__ == "__main__":
    unittest.main()
