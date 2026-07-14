import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import github_sync
import scheduled_run


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ConfigDefaultsTests(unittest.TestCase):
    def test_terminal_field_is_at_top_and_can_be_loaded(self):
        with (PROJECT_ROOT / "config.json").open("r", encoding="utf-8-sig") as file:
            config = json.load(file)
        keys = list(config)
        self.assertEqual("GITHUB_SYNC_FIELD_ID", keys[1])

        config.update(
            {
                "GITHUB_SYNC_TOKEN": "github_pat_test",
                "GITHUB_SYNC_REPOSITORY": "owner/repo",
                "GITHUB_SYNC_FIELD_ID": "济南联通",
            }
        )
        self.assertEqual("济南联通", github_sync.validate_config(config)[4])

    def test_wxpusher_is_disabled_by_default(self):
        with (PROJECT_ROOT / "config.json").open("r", encoding="utf-8-sig") as file:
            config = json.load(file)
        self.assertFalse(config["ENABLE_WXPUSHER"])


class SetupScriptTests(unittest.TestCase):
    def test_windows_setup_uses_venv_retries_and_real_exit_codes(self):
        script = (PROJECT_ROOT / "setup.ps1").read_text(encoding="utf-8-sig")
        self.assertIn(".venv\\Scripts\\python.exe", script)
        self.assertIn('"--timeout", "120"', script)
        self.assertIn('"--retries", "10"', script)
        self.assertIn("$LASTEXITCODE", script)
        self.assertIn("curl.exe", script)
        self.assertNotIn("pip show", script)

    def test_linux_setup_uses_venv_and_preserves_gitignore(self):
        script = (PROJECT_ROOT / "setup.sh").read_text(encoding="utf-8")
        self.assertIn('.venv/bin/python', script)
        self.assertIn("--timeout 120 --retries 10", script)
        self.assertIn("append_gitignore_entry", script)
        self.assertNotIn("cat > .gitignore", script)
        self.assertNotIn("python3 -m pip install --upgrade pip", script)

    def test_core_requirements_are_centralized(self):
        requirements = {
            line.strip()
            for line in (PROJECT_ROOT / "requirements.txt").read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }
        self.assertEqual({"requests", "aiohttp"}, requirements)

    def test_update_scripts_do_not_force_reset_or_embed_tokens(self):
        for name in ("update_fork.ps1", "update_fork.sh"):
            script = (PROJECT_ROOT / name).read_text(encoding="utf-8-sig")
            self.assertIn("--ff-only", script)
            self.assertNotIn("git reset --hard", script)
            self.assertNotIn("@github.com", script)


class GitHubSyncTests(unittest.TestCase):
    def test_prepare_local_nodes_caps_and_tags_results(self):
        content = "\n".join(
            [f"104.16.0.{index}:443#US {index}.00 Mbps" for index in range(1, 8)]
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as file:
            file.write(content)
            path = file.name
        try:
            nodes = github_sync.prepare_local_nodes(path, "济南联通", 5)
        finally:
            os.remove(path)
        self.assertEqual(5, len(nodes))
        self.assertEqual("104.16.0.1:443#US|济南联通 1.00 Mbps", nodes[0])

    def test_merge_replaces_only_owned_lines(self):
        remote = (
            "104.16.0.1:443#US|济南联通\n"
            "162.159.0.1:443#US|郑州教育网\n"
            "保留的普通文本\n"
            "104.16.0.2:443#US|济南联通\n"
        )
        local = ["104.17.0.1:443#US|济南联通"]
        merged = github_sync.merge_nodes(remote, "济南联通", local)
        self.assertIn("104.17.0.1:443#US|济南联通", merged)
        self.assertIn("162.159.0.1:443#US|郑州教育网", merged)
        self.assertIn("保留的普通文本", merged)
        self.assertNotIn("104.16.0.1:443#US|济南联通", merged)
        self.assertNotIn("104.16.0.2:443#US|济南联通", merged)


class ScheduleTests(unittest.TestCase):
    CONFIG = {
        "SCHEDULE_CF_BUSY_START_HOUR": 18,
        "SCHEDULE_CF_BUSY_END_HOUR": 24,
        "SCHEDULE_BUSY_INTERVAL_MINUTES": 15,
        "SCHEDULE_OFFPEAK_INTERVAL_MINUTES": 30,
    }

    def test_busy_period_runs_every_quarter_hour(self):
        for minute in (0, 15, 30, 45):
            now = datetime(2026, 7, 13, 22, minute, tzinfo=timezone.utc)
            self.assertEqual((True, True, 15), scheduled_run.should_run(now, self.CONFIG))

    def test_offpeak_runs_only_on_hour_and_half_hour(self):
        expected = {0: True, 15: False, 30: True, 45: False}
        for minute, should_run in expected.items():
            now = datetime(2026, 7, 13, 10, minute, tzinfo=timezone.utc)
            self.assertEqual(
                (should_run, False, 30), scheduled_run.should_run(now, self.CONFIG)
            )


if __name__ == "__main__":
    unittest.main()
