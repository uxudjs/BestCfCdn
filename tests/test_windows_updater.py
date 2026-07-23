import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WindowsUpdaterSourceTests(unittest.TestCase):
    def test_embedded_python_uses_temporary_script_instead_of_dash_c(self):
        script = (PROJECT_ROOT / "update_fork.ps1").read_text(
            encoding="utf-8-sig"
        )
        merge_code = script.split("$mergeCode = @'", 1)[1].split("\n'@", 1)[0]

        self.assertIn("function Invoke-UpdatePythonCode", script)
        self.assertIn("[IO.File]::WriteAllText", script)
        self.assertIn("Remove-Item -LiteralPath $tempScriptPath", script)
        self.assertIn("Invoke-UpdatePythonCode -Code $validateCode", script)
        self.assertIn("Invoke-UpdatePythonCode -Code $mergeCode", script)
        self.assertNotIn('"-c", $mergeCode', script)
        self.assertNotIn('"-c", $validateCode', script)
        self.assertIn("legacy_schedule_defaults", merge_code)
        compile(merge_code, "<update_fork.ps1 merge code>", "exec")

    def test_untracked_config_probe_does_not_emit_pathspec_error(self):
        script = (PROJECT_ROOT / "update_fork.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("function Test-GitTrackedPath", script)
        self.assertNotIn('"ls-files", "--error-unmatch"', script)

    def test_backup_retention_is_bounded_and_noop_is_detected(self):
        script = (PROJECT_ROOT / "update_fork.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn('"bestcfcdn_backup_latest"', script)
        self.assertNotIn('Get-Date -Format "yyyyMMdd_HHmmss_fff"', script)
        self.assertIn("UPDATE_BACKUP_RETENTION", script)
        self.assertIn("Set-ManagedBackupRetention", script)
        self.assertIn("Remove-ManagedBackupDirectories", script)
        self.assertIn("未创建新备份", script)
        self.assertLess(
            script.index("未创建新备份"),
            script.index('$BackupDir = Join-Path $HOME "bestcfcdn_backup_latest"'),
        )


class SetupSingBoxSourceTests(unittest.TestCase):
    def test_setup_scripts_use_the_same_python_prepare_entry_before_scheduling(self):
        powershell = (PROJECT_ROOT / "setup.ps1").read_text(encoding="utf-8-sig")
        bash = (PROJECT_ROOT / "setup.sh").read_text(encoding="utf-8-sig")

        self.assertIn('"--prepare-sing-box", $configPath', powershell)
        self.assertIn('--prepare-sing-box "$CONFIG_PATH"', bash)
        self.assertLess(
            powershell.index('"--prepare-sing-box", $configPath'),
            powershell.index("$scheduleEnabled = $true"),
        )
        self.assertLess(
            bash.index('--prepare-sing-box "$CONFIG_PATH"'),
            bash.index('CRON_CMD="*/30'),
        )

    def test_setup_scripts_do_not_duplicate_sing_box_download_or_extraction(self):
        combined = "\n".join(
            (PROJECT_ROOT / name).read_text(encoding="utf-8-sig")
            for name in ("setup.ps1", "setup.sh")
        )

        self.assertNotIn("SagerNet/sing-box/releases", combined)
        self.assertNotIn("Expand-Archive", combined)
        self.assertNotIn("tar -x", combined)
        self.assertNotIn(".runtime/sing-box", combined)

    def test_prepare_entry_skips_cleanly_when_chain_testing_is_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            original = {"CHAIN_PROXY_TEST_ENABLED": False, "keep": "value"}
            config_path.write_text(json.dumps(original), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "chain_proxy.py"),
                    "--prepare-sing-box",
                    str(config_path),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn("链式测速未启用", completed.stdout)
            self.assertEqual(original, json.loads(config_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
