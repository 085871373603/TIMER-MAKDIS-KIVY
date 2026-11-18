import configparser
import os
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProjectIntegrityTests(unittest.TestCase):
    def test_required_files(self):
        required = [
            "main.py", "timer_logic.py", "buildozer.spec",
            "services/timer_service.py", "assets/icon.png", "assets/notifikasi.mp3",
            "android_resources/drawable/ic_stat_maxdis.png",
            "android_resources/extra_manifest_application_arguments.xml",
            "android_src/id/arinex/timermaxdis/MaxdisPythonService.java",
        ]
        for relative in required:
            with self.subTest(relative=relative):
                path = ROOT / relative
                self.assertTrue(path.is_file(), f"Missing {relative}")
                self.assertGreater(path.stat().st_size, 0, f"Empty {relative}")

    def test_manifest_fragment_is_well_formed(self):
        path = ROOT / "android_resources/extra_manifest_application_arguments.xml"
        tree = ET.parse(path)
        service = tree.getroot()
        self.assertTrue(service.tag.endswith("service"))
        android_name = "{http://schemas.android.com/apk/res/android}name"
        self.assertEqual(service.attrib[android_name], "id.arinex.timermaxdis.ServiceTimer")
        self.assertEqual(service.attrib["{http://schemas.android.com/apk/res/android}foregroundServiceType"], "specialUse")

    def test_buildozer_configuration(self):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(ROOT / "buildozer.spec", encoding="utf-8")
        app = parser["app"]
        self.assertIn("foregroundServiceType=specialUse", app["services"])
        self.assertIn("FOREGROUND_SERVICE_SPECIAL_USE", app["android.permissions"])
        self.assertIn("POST_NOTIFICATIONS", app["android.permissions"])
        self.assertIn("ic_stat_maxdis", app["android.add_resources"])
        self.assertEqual(app["android.service_class_name"], "id.arinex.timermaxdis.MaxdisPythonService")

    def test_workflow_runs_unit_tests_before_build(self):
        workflow = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf-8")
        self.assertIn("python -m unittest discover", workflow)
        self.assertIn("buildozer -v android debug", workflow)
        self.assertIn("upload-artifact", workflow)

    def test_custom_notification_channel_is_visible(self):
        java_source = (ROOT / "android_src/id/arinex/timermaxdis/MaxdisPythonService.java").read_text(encoding="utf-8")
        self.assertIn("NotificationManager.IMPORTANCE_LOW", java_source)
        self.assertIn("super.doStartForeground(extras)", java_source)


if __name__ == "__main__":
    unittest.main()
