import ast
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import github_sync
import local_state
import scheduled_run


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ConfigDefaultsTests(unittest.TestCase):
    CONFIG_TEMPLATE = PROJECT_ROOT / "config.example.json"

    def test_terminal_field_is_at_top_and_can_be_loaded(self):
        with self.CONFIG_TEMPLATE.open("r", encoding="utf-8-sig") as file:
            config = json.load(file)
        keys = list(config)
        self.assertEqual("GITHUB_SYNC_FIELD_ID", keys[1])

        config.update(
            {
                "GITHUB_SYNC_TOKEN": "github_pat_test",
                "GITHUB_SYNC_REPOSITORY": "owner/repo",
                "GITHUB_SYNC_FIELD_ID": "device-a",
            }
        )
        self.assertEqual("device-a", github_sync.validate_config(config)[4])

    def test_wxpusher_is_disabled_by_default(self):
        with self.CONFIG_TEMPLATE.open("r", encoding="utf-8-sig") as file:
            config = json.load(file)
        self.assertFalse(config["ENABLE_WXPUSHER"])

    def test_scheduled_task_is_enabled_by_default_for_backward_compatibility(self):
        with self.CONFIG_TEMPLATE.open("r", encoding="utf-8-sig") as file:
            config = json.load(file)
        self.assertTrue(config["ENABLE_SCHEDULED_TASK"])

    def test_local_output_is_separate_from_remote_aggregate(self):
        with self.CONFIG_TEMPLATE.open("r", encoding="utf-8-sig") as file:
            config = json.load(file)
        self.assertEqual("ip.local.txt", config["OUTPUT_FILE"])
        self.assertEqual("ip.txt", config["GITHUB_SYNC_REMOTE_PATH"])

    def test_proxy_experience_v2_defaults_are_enabled(self):
        with self.CONFIG_TEMPLATE.open("r", encoding="utf-8-sig") as file:
            config = json.load(file)
        self.assertEqual(4, config["TCP_PROBES"])
        self.assertEqual(0.75, config["MIN_SUCCESS_RATE"])
        self.assertEqual(5, config["HTTP_JITTER_SAMPLES"])
        self.assertEqual(0.30, config["PROXY_SCORE_BANDWIDTH_WEIGHT"])
        self.assertEqual(0.40, config["PROXY_SCORE_HTTP_LATENCY_WEIGHT"])
        self.assertEqual(0.25, config["BANDWIDTH_MIN_PARTIAL_MB"])
        self.assertEqual(1.0, config["BANDWIDTH_MIN_TRANSFER_SECONDS"])
        self.assertNotIn("SPEED_WEIGHT", config)

    def test_runtime_fallback_matches_latest_mainland_defaults(self):
        with self.CONFIG_TEMPLATE.open("r", encoding="utf-8-sig") as file:
            template = json.load(file)

        tree = ast.parse(
            (PROJECT_ROOT / "main.py").read_text(encoding="utf-8-sig")
        )
        defaults = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "defaults"
                for target in node.targets
            ):
                defaults = ast.literal_eval(node.value)
                break

        self.assertIsNotNone(defaults)
        for key in (
            "CF_ENABLED",
            "DNS_IP_RISK_FILTER_ENABLED",
            "BLOCKED_COUNTRIES",
            "BANDWIDTH_MIN_PARTIAL_MB",
            "BANDWIDTH_MIN_TRANSFER_SECONDS",
        ):
            self.assertEqual(template[key], defaults[key])

    def test_legacy_overlapping_output_is_migrated_at_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            output = local_state.resolve_local_output(
                {
                    "OUTPUT_FILE": "ip.txt",
                    "GITHUB_SYNC_REMOTE_PATH": "ip.txt",
                },
                config_path,
            )
        self.assertEqual(os.path.join(temp_dir, "ip.local.txt"), output)


class SetupScriptTests(unittest.TestCase):
    def test_powershell_scripts_have_utf8_bom_for_windows_powershell_51(self):
        for name in ("setup.ps1", "git_sync.ps1", "update_fork.ps1"):
            content = (PROJECT_ROOT / name).read_bytes()
            self.assertTrue(
                content.startswith(b"\xef\xbb\xbf"),
                f"{name} must use UTF-8 BOM for Windows PowerShell 5.1",
            )

    def test_windows_setup_uses_venv_retries_and_real_exit_codes(self):
        script = (PROJECT_ROOT / "setup.ps1").read_text(encoding="utf-8-sig")
        self.assertIn(".venv\\Scripts\\python.exe", script)
        self.assertIn('"--timeout", "120"', script)
        self.assertIn('"--retries", "10"', script)
        self.assertIn("$LASTEXITCODE", script)
        self.assertIn("curl.exe", script)
        self.assertIn('$env:PYTHONUTF8 = "1"', script)
        self.assertIn('"-X", "utf8"', script)
        self.assertNotIn("print('依赖导入验证通过')", script)
        self.assertIn("ENABLE_SCHEDULED_TASK", script)
        self.assertIn("config.example.json", script)
        self.assertIn("Copy-Item -LiteralPath $configTemplatePath", script)
        config_block = script.split("$configTemplatePath =", 1)[1].split(
            "# ---------- 1.", 1
        )[0]
        self.assertIn("首次部署到此暂停", config_block)
        self.assertIn("exit 0", config_block)
        self.assertNotIn("Read-Host", config_block)
        self.assertIn("Remove-ProjectScheduledTask", script)
        self.assertIn("proxy_scoring.py", script)
        self.assertIn("$current = $current.InnerException", script)
        self.assertIn("-2147024894", script)
        self.assertNotIn("-2147216625", script)
        self.assertIn("删除后仍然存在", script)
        self.assertIn("无法关闭本项目计划任务", script)
        self.assertIn('手动运行：& `"$PythonExePath`" -X utf8', script)
        self.assertNotIn("pip show", script)

    def test_setup_is_the_single_entrypoint_for_safe_updates(self):
        windows_setup = (PROJECT_ROOT / "setup.ps1").read_text(
            encoding="utf-8-sig"
        )
        windows_update = (PROJECT_ROOT / "update_fork.ps1").read_text(
            encoding="utf-8-sig"
        )
        linux_setup = (PROJECT_ROOT / "setup.sh").read_text(encoding="utf-8")
        linux_update = (PROJECT_ROOT / "update_fork.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("[switch]$SkipAutoUpdate", windows_setup)
        self.assertIn(
            '& $updateScriptPath -Branch "main" -NonInteractive -PreserveMissingConfig',
            windows_setup,
        )
        self.assertLess(
            windows_setup.index("& $updateScriptPath"),
            windows_setup.index('$configPath = Join-Path $ScriptDir "config.json"'),
        )
        self.assertIn("Restart-UpdatedSetup", windows_setup)
        self.assertIn("-SkipAutoUpdate", windows_setup)
        self.assertIn("[switch]$NonInteractive", windows_update)
        self.assertIn("[switch]$PreserveMissingConfig", windows_update)
        self.assertIn("if (-not $NonInteractive)", windows_update)

        self.assertIn('UPDATE_HELPER="$SCRIPT_DIR/update_fork.sh"', linux_setup)
        self.assertIn("--preserve-missing-config", linux_setup)
        self.assertIn('BESTCFCDN_SETUP_REEXEC_DEPTH="$NEXT_REEXEC_DEPTH"', linux_setup)
        self.assertIn("BESTCFCDN_SETUP_RETRY_AUTO_UPDATE", linux_setup)
        self.assertLess(
            linux_setup.index('run_as_target bash "$UPDATE_HELPER"'),
            linux_setup.index('if [[ -e $CONFIG_PATH && ! -f $CONFIG_PATH ]]'),
        )
        self.assertIn("--preserve-missing-config", linux_update)
        self.assertIn("PRESERVE_MISSING_CONFIG", linux_update)
        self.assertNotIn('bash "$SCRIPT_DIR/setup.sh"', linux_update)

    def test_scheduler_enables_utf8_for_child_process(self):
        script = (PROJECT_ROOT / "scheduled_run.py").read_text(encoding="utf-8")
        self.assertIn('child_env.setdefault("PYTHONUTF8", "1")', script)
        self.assertIn('child_env.setdefault("PYTHONIOENCODING", "utf-8")', script)

    def test_linux_setup_uses_venv_and_preserves_gitignore(self):
        script = (PROJECT_ROOT / "setup.sh").read_text(encoding="utf-8")
        self.assertIn('.venv/bin/python', script)
        self.assertIn("--timeout 120 --retries 10", script)
        self.assertIn("append_gitignore_entry", script)
        self.assertIn("ENABLE_SCHEDULED_TASK", script)
        self.assertIn("config.example.json", script)
        self.assertIn('run_as_target cp "$CONFIG_TEMPLATE_PATH" "$CONFIG_PATH"', script)
        config_block = script.split('CONFIG_PATH="$SCRIPT_DIR/config.json"', 1)[
            1
        ].split("# ---------- 1.", 1)[0]
        self.assertIn("首次部署到此暂停", config_block)
        self.assertIn("exit 0", config_block)
        self.assertNotIn("是否立即运行", config_block)
        self.assertIn("read_target_crontab", script)
        self.assertIn("proxy_scoring.py", script)
        self.assertIn("已停止以避免覆盖其他任务", script)
        self.assertIn("自动定时优选已关闭", script)
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
            self.assertIn("config.example.json", script)
            self.assertIn("ip.local.txt", script)
            self.assertIn("ip.legacy.txt", script)
            self.assertIn("diff", script)

    def test_sensitive_and_local_runtime_files_are_ignored(self):
        ignored = set((PROJECT_ROOT / ".gitignore").read_text().splitlines())
        self.assertTrue(
            {"config.json", "ip.local.txt", "valid_tokens.txt"}.issubset(ignored)
        )

    def test_bandwidth_failure_does_not_restore_rejected_candidates(self):
        script = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8-sig")
        self.assertIn(
            "candidates_after_http or candidates_after_availability or candidates",
            script,
        )
        fallback_block = script.split("if not bandwidth_available:", 1)[1].split(
            "ranked_scores =", 1
        )[0]
        self.assertNotIn("results[:GLOBAL_TOP_N]", fallback_block)

    def test_dns_ranked_nodes_do_not_require_availability_metadata(self):
        script = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8-sig")
        self.assertIn("ip_info = ip_info or {}", script)
        self.assertNotIn("if full_bw_results and ip_info:", script)
        self.assertIn(
            "per_country_limit=None if USE_GLOBAL_MODE else PER_COUNTRY_TOP_N",
            script,
        )


class GitHubSyncTests(unittest.TestCase):
    def test_manual_sync_uses_configured_local_output_by_default(self):
        script = (PROJECT_ROOT / "github_sync.py").read_text(encoding="utf-8")
        self.assertIn("resolve_local_output(config, config_path, print)", script)
        for name in ("git_sync.ps1", "git_sync.sh"):
            wrapper = (PROJECT_ROOT / name).read_text(encoding="utf-8-sig")
            self.assertNotIn('--input "$SCRIPT_DIR/ip.txt"', wrapper)
            self.assertNotIn('Join-Path $PSScriptRoot "ip.txt"', wrapper)

    def test_prepare_local_nodes_caps_and_tags_results(self):
        content = "\n".join(
            [f"104.16.0.{index}:443#US {index}.00 Mbps" for index in range(1, 8)]
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as file:
            file.write(content)
            path = file.name
        try:
            nodes = github_sync.prepare_local_nodes(path, "device-a", 5)
        finally:
            os.remove(path)
        self.assertEqual(5, len(nodes))
        self.assertEqual("104.16.0.1:443#US|device-a 1.00 Mbps", nodes[0])

    def test_merge_replaces_only_owned_lines(self):
        remote = (
            "104.16.0.1:443#US|device-a\n"
            "162.159.0.1:443#US|device-b\n"
            "保留的普通文本\n"
            "104.16.0.2:443#US|device-a\n"
        )
        local = ["104.17.0.1:443#US|device-a"]
        merged = github_sync.merge_nodes(remote, "device-a", local)
        self.assertIn("104.17.0.1:443#US|device-a", merged)
        self.assertIn("162.159.0.1:443#US|device-b", merged)
        self.assertIn("保留的普通文本", merged)
        self.assertNotIn("104.16.0.1:443#US|device-a", merged)
        self.assertNotIn("104.16.0.2:443#US|device-a", merged)


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

    @mock.patch("scheduled_run.subprocess.call")
    @mock.patch(
        "scheduled_run.load_config",
        return_value={"ENABLE_SCHEDULED_TASK": False},
    )
    def test_disabled_schedule_does_not_launch_main(self, _load_config, call):
        self.assertEqual(0, scheduled_run.main())
        call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
