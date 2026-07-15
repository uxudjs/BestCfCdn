import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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

        for name in ("setup.sh", "update_fork.sh"):
            shutil.copy2(PROJECT_ROOT / name, self.seed / name)
        self._write_template(version=1)
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
        }
        if version >= 2:
            template["NEW_SETTING"] = 42
        (self.seed / "config.example.json").write_text(
            json.dumps(template, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )

    def _push_v2(self):
        self._write_template(version=2)
        run(["git", "add", "config.example.json"], self.seed)
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

    def test_updater_preserves_values_adds_fields_and_is_idempotent(self):
        local_config = {
            "GITHUB_SYNC_FIELD_ID": "济南联通",
            "ENABLE_SCHEDULED_TASK": False,
            "OUTPUT_FILE": "ip.txt",
            "GITHUB_SYNC_REMOTE_PATH": "ip.txt",
            "EXISTING_SETTING": "custom-value",
        }
        (self.client / "config.json").write_text(
            json.dumps(local_config, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
        self._push_v2()

        command = [
            "bash",
            "update_fork.sh",
            "--non-interactive",
            "--preserve-missing-config",
        ]
        run(command, self.client, env=self._environment())

        with (self.client / "config.json").open(encoding="utf-8") as file:
            merged = json.load(file)
        self.assertEqual("济南联通", merged["GITHUB_SYNC_FIELD_ID"])
        self.assertFalse(merged["ENABLE_SCHEDULED_TASK"])
        self.assertEqual("custom-value", merged["EXISTING_SETTING"])
        self.assertEqual(42, merged["NEW_SETTING"])
        self.assertEqual("ip.local.txt", merged["OUTPUT_FILE"])

        backups = sorted(self.home.glob("bestcfcdn_backup_*"))
        self.assertEqual(1, len(backups))
        self.assertEqual("700", oct(stat.S_IMODE(backups[0].stat().st_mode))[2:])
        self.assertEqual(
            "600",
            oct(stat.S_IMODE((backups[0] / "config.json").stat().st_mode))[2:],
        )

        run(command, self.client, env=self._environment())
        self.assertEqual(backups, sorted(self.home.glob("bestcfcdn_backup_*")))


if __name__ == "__main__":
    unittest.main()
