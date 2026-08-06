import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run(command, cwd, env=None, timeout=30):
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@unittest.skipUnless(
    os.name == "posix" and shutil.which("git") and shutil.which("bash"),
    "needs POSIX, git, and bash",
)
class SetupUpdateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.seed = self.root / "seed"
        self.remote = self.root / "remote.git"
        self.client = self.root / "client with spaces"
        self.home = self.root / "home"
        self.fake_bin = self.root / "fake-bin"
        self.home.mkdir()
        self.fake_bin.mkdir()
        self.seed.mkdir()

        fake_crontab = self.fake_bin / "crontab"
        fake_crontab.write_text(
            "#!/bin/sh\n"
            "if [ \"${1:-}\" = \"-l\" ]; then\n"
            "  echo 'no crontab for integration-test' >&2\n"
            "  exit 1\n"
            "fi\n"
            "cat >/dev/null\n",
            encoding="utf-8",
        )
        fake_crontab.chmod(0o755)

        shutil.copy2(PROJECT_ROOT / "setup.sh", self.seed / "setup.sh")
        (self.seed / "scripts").mkdir()
        shutil.copy2(
            PROJECT_ROOT / "scripts" / "update_fork.sh",
            self.seed / "scripts" / "update_fork.sh",
        )
        legacy_updater = self.seed / "update_fork.sh"
        legacy_updater.write_text(
            "#!/usr/bin/env bash\n"
            'exec bash "$(dirname "$0")/scripts/update_fork.sh" "$@"\n',
            encoding="utf-8",
        )
        legacy_updater.chmod(0o755)
        (self.seed / "main.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
        self._write_template(version=1)
        shutil.copy2(
            self.seed / "config" / "config.example.json",
            self.seed / "config.example.json",
        )
        (self.seed / ".gitignore").write_text("*.pyc\n", encoding="utf-8")

        run(["git", "init", "-b", "main"], self.seed)
        run(["git", "config", "user.name", "Setup Test"], self.seed)
        run(["git", "config", "user.email", "setup@example.invalid"], self.seed)
        run(["git", "add", "."], self.seed)
        run(["git", "commit", "-m", "v1"], self.seed)
        run(["git", "clone", "--bare", str(self.seed), str(self.remote)], self.root)
        run(["git", "remote", "add", "origin", str(self.remote)], self.seed)
        run(["git", "clone", str(self.remote), str(self.client)], self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_template(self, version):
        template = {
            "_comment": "integration fixture",
            "GITHUB_SYNC_FIELD_ID": "请填写终端名称",
            "ENABLE_SCHEDULED_TASK": True,
            "OUTPUT_FILE": "ip.local.txt",
            "GITHUB_SYNC_REMOTE_PATH": "ip.txt",
            "EXISTING_SETTING": f"default-v{version}",
            "SCHEDULE_BUSY_INTERVAL_MINUTES": 60 if version == 1 else 90,
            "SCHEDULE_OFFPEAK_INTERVAL_MINUTES": 180,
        }
        if version >= 2:
            template["NEW_SETTING"] = 42
            template["UPDATE_BACKUP_RETENTION"] = 1
        config_dir = self.seed / "config"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "config.example.json").write_text(
            json.dumps(template, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )

    def _push_v2(self):
        self._write_template(version=2)
        (self.seed / "update_fork.sh").unlink(missing_ok=True)
        shutil.copy2(
            self.seed / "config" / "config.example.json",
            self.seed / "config.example.json",
        )
        run(["git", "add", "-A"], self.seed)
        run(["git", "commit", "-m", "v2"], self.seed)
        run(["git", "push", "origin", "main"], self.seed)

    def _environment(self):
        environment = os.environ.copy()
        environment["HOME"] = str(self.home)
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["PATH"] = f"{self.fake_bin}{os.pathsep}{environment['PATH']}"
        return environment

    def test_first_setup_updates_then_creates_config_without_installing(self):
        self._push_v2()

        completed = run(
            ["bash", "setup.sh"],
            self.client,
            env=self._environment(),
        )

        with (self.client / "config.json").open(encoding="utf-8") as file:
            config = json.load(file)
        self.assertEqual(42, config["NEW_SETTING"])
        self.assertFalse((self.client / ".venv").exists())
        self.assertFalse((self.client / "update_fork.sh").exists())
        self.assertEqual(
            (self.client / "config" / "config.example.json").read_bytes(),
            (self.client / "config.example.json").read_bytes(),
        )
        self.assertIn("首次部署到此暂停", completed.stdout)
        self.assertNotIn("是否立即运行一次", completed.stdout)
        self.assertEqual(
            "600",
            oct(stat.S_IMODE((self.client / "config.json").stat().st_mode))[2:],
        )
        status = run(["git", "status", "--porcelain"], self.client)
        self.assertEqual("", status.stdout)
        self.assertEqual(
            "*.pyc\n", (self.client / ".gitignore").read_text(encoding="utf-8")
        )
        self.assertIn(
            "config.json",
            (self.client / ".git" / "info" / "exclude").read_text(
                encoding="utf-8"
            ),
        )

    def test_first_setup_updates_through_symlinked_repository_path(self):
        self._push_v2()
        client_alias = self.root / "client-alias"
        client_alias.symlink_to(self.client, target_is_directory=True)

        completed = run(
            ["bash", str(client_alias / "setup.sh")],
            self.root,
            env=self._environment(),
        )

        with (self.client / "config.json").open(encoding="utf-8") as file:
            config = json.load(file)
        self.assertEqual(42, config["NEW_SETTING"])
        self.assertNotIn("当前不是可更新的 Git 仓库", completed.stdout)
        self.assertEqual(
            run(["git", "rev-parse", "HEAD"], self.seed).stdout,
            run(["git", "rev-parse", "HEAD"], self.client).stdout,
        )

    def test_updater_preserves_values_adds_fields_and_is_idempotent(self):
        local_config = {
            "GITHUB_SYNC_FIELD_ID": "device-a",
            "ENABLE_SCHEDULED_TASK": False,
            "OUTPUT_FILE": "ip.txt",
            "GITHUB_SYNC_REMOTE_PATH": "ip.txt",
            "EXISTING_SETTING": "custom-value",
            "SCHEDULE_BUSY_INTERVAL_MINUTES": 60,
            "SCHEDULE_OFFPEAK_INTERVAL_MINUTES": 180,
        }
        (self.client / "config.json").write_text(
            json.dumps(local_config, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
        for suffix in ("20260701_010101_001", "20260702_020202.abc123"):
            legacy = self.home / f"bestcfcdn_backup_{suffix}"
            legacy.mkdir()
            (legacy / "config.json").write_text("{}\n", encoding="utf-8")
        self._push_v2()

        command = [
            "bash",
            "scripts/update_fork.sh",
            "--non-interactive",
            "--preserve-missing-config",
        ]
        run(command, self.client, env=self._environment())

        with (self.client / "config.json").open(encoding="utf-8") as file:
            merged = json.load(file)
        self.assertEqual("device-a", merged["GITHUB_SYNC_FIELD_ID"])
        self.assertFalse(merged["ENABLE_SCHEDULED_TASK"])
        self.assertEqual("custom-value", merged["EXISTING_SETTING"])
        self.assertEqual(42, merged["NEW_SETTING"])
        self.assertEqual("ip.local.txt", merged["OUTPUT_FILE"])
        self.assertEqual(90, merged["SCHEDULE_BUSY_INTERVAL_MINUTES"])
        self.assertEqual(180, merged["SCHEDULE_OFFPEAK_INTERVAL_MINUTES"])

        backups = sorted(self.home.glob("bestcfcdn_backup_*"))
        self.assertEqual(1, len(backups))
        self.assertEqual("bestcfcdn_backup_latest", backups[0].name)
        self.assertEqual("700", oct(stat.S_IMODE(backups[0].stat().st_mode))[2:])
        self.assertEqual(
            "600",
            oct(stat.S_IMODE((backups[0] / "config.json").stat().st_mode))[2:],
        )

        run(command, self.client, env=self._environment())
        self.assertEqual(backups, sorted(self.home.glob("bestcfcdn_backup_*")))

    def test_retention_zero_removes_backup_after_success(self):
        local_config = {
            "GITHUB_SYNC_FIELD_ID": "device-a",
            "UPDATE_BACKUP_RETENTION": 0,
        }
        (self.client / "config.json").write_text(
            json.dumps(local_config, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
        legacy = self.home / "bestcfcdn_backup_20260701_010101_001"
        legacy.mkdir()
        (legacy / "config.json").write_text("{}\n", encoding="utf-8")
        self._push_v2()

        completed = run(
            [
                "bash",
                "scripts/update_fork.sh",
                "--non-interactive",
                "--preserve-missing-config",
            ],
            self.client,
            env=self._environment(),
        )

        self.assertEqual([], list(self.home.glob("bestcfcdn_backup_*")))
        self.assertIn("按配置在成功更新后移除备份", completed.stdout)

    def test_invalid_retention_is_rejected_before_update(self):
        local_config = {
            "GITHUB_SYNC_FIELD_ID": "device-a",
            "UPDATE_BACKUP_RETENTION": 2,
        }
        (self.client / "config.json").write_text(
            json.dumps(local_config, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
        self._push_v2()

        completed = subprocess.run(
            [
                "bash",
                "scripts/update_fork.sh",
                "--non-interactive",
                "--preserve-missing-config",
            ],
            cwd=self.client,
            env=self._environment(),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertNotEqual(0, completed.returncode)
        self.assertIn("UPDATE_BACKUP_RETENTION", completed.stderr)
        self.assertNotEqual(
            run(["git", "rev-parse", "HEAD"], self.client).stdout,
            run(["git", "rev-parse", "HEAD"], self.seed).stdout,
        )

    def test_failed_update_keeps_one_rescue_backup_when_retention_is_zero(self):
        local_config = {
            "GITHUB_SYNC_FIELD_ID": "device-a",
            "UPDATE_BACKUP_RETENTION": 0,
        }
        (self.client / "config.json").write_text(
            json.dumps(local_config, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
        (self.client / "ip.local.txt").write_text(
            "104.16.0.1:443#device-a\n", encoding="utf-8"
        )
        (self.seed / "ip.local.txt").write_text(
            "remote file that must not overwrite local state\n", encoding="utf-8"
        )
        run(["git", "add", "ip.local.txt"], self.seed)
        run(["git", "commit", "-m", "introduce collision"], self.seed)
        run(["git", "push", "origin", "main"], self.seed)

        completed = subprocess.run(
            [
                "bash",
                "scripts/update_fork.sh",
                "--non-interactive",
                "--preserve-missing-config",
            ],
            cwd=self.client,
            env=self._environment(),
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertNotEqual(0, completed.returncode)
        backups = list(self.home.glob("bestcfcdn_backup_*"))
        self.assertEqual([self.home / "bestcfcdn_backup_latest"], backups)
        self.assertEqual(
            "104.16.0.1:443#device-a\n",
            (self.client / "ip.local.txt").read_text(encoding="utf-8"),
        )
        self.assertTrue((backups[0] / "config.json").is_file())
        self.assertTrue((backups[0] / "ip.local.txt").is_file())

    def test_updater_preserves_custom_schedule_intervals(self):
        local_config = {
            "GITHUB_SYNC_FIELD_ID": "device-a",
            "SCHEDULE_BUSY_INTERVAL_MINUTES": 20,
            "SCHEDULE_OFFPEAK_INTERVAL_MINUTES": 90,
        }
        (self.client / "config.json").write_text(
            json.dumps(local_config, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
        self._push_v2()

        run(
            [
                "bash",
                "scripts/update_fork.sh",
                "--non-interactive",
                "--preserve-missing-config",
            ],
            self.client,
            env=self._environment(),
        )

        with (self.client / "config.json").open(encoding="utf-8") as file:
            merged = json.load(file)
        self.assertEqual(20, merged["SCHEDULE_BUSY_INTERVAL_MINUTES"])
        self.assertEqual(90, merged["SCHEDULE_OFFPEAK_INTERVAL_MINUTES"])


if __name__ == "__main__":
    unittest.main()
