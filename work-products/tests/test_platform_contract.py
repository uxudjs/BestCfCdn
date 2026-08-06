import json
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TheoreticalPlatformContractTests(unittest.TestCase):
    def test_entrypoints_and_guidance_reference_only_the_core_package(self):
        consumers = (
            PROJECT_ROOT / "main.py",
            PROJECT_ROOT / "setup.ps1",
            PROJECT_ROOT / "setup.sh",
            PROJECT_ROOT / "scripts" / "git_sync.ps1",
            PROJECT_ROOT / "scripts" / "git_sync.sh",
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "AGENTS.md",
        ) + tuple((PROJECT_ROOT / "core").glob("*.py"))
        for path in consumers:
            text = path.read_text(encoding="utf-8-sig")
            with self.subTest(path=path.name):
                self.assertNotIn("bestcfcdn.", text)
                self.assertNotIn("bestcfcdn/", text)
                self.assertNotIn("bestcfcdn\\", text)
                self.assertNotIn("bestcfcdn_core.", text)
                self.assertNotIn("bestcfcdn_core/", text)
                self.assertNotIn("bestcfcdn_core\\", text)

        for path in (
            PROJECT_ROOT / "work-products" / "SPEC.md",
            PROJECT_ROOT / "work-products" / "plan.md",
            PROJECT_ROOT / "work-products" / "todo.md",
        ):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotIn("`bestcfcdn`", text)
                self.assertNotIn("`bestcfcdn_core`", text)

    def test_trilingual_docs_share_the_new_layout_and_schedule_contract(self):
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertEqual(6, readme.count("config/config.example.json"))
        self.assertEqual(3, readme.count("python -m core.github_sync"))
        self.assertEqual(3, readme.count("python -m core.scheduled_run"))
        self.assertEqual(3, readme.count("scripts/update_fork.*"))
        self.assertIn("00:00–18:00 每 3 小时，18:00–24:00 每 1.5 小时", readme)
        self.assertIn("00:00–18:00 每 3 小時，18:00–24:00 每 1.5 小時", readme)
        self.assertIn(
            "every three hours from 00:00 to 18:00 and every 90 minutes",
            readme,
        )

    def test_trilingual_chain_guidance_covers_the_same_safety_contract(self):
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        simplified = readme.split("## 🇨🇳 简体中文", 1)[1].split(
            "## 🇹🇼 繁體中文", 1
        )[0]
        traditional = readme.split("## 🇹🇼 繁體中文", 1)[1].split(
            "## 🇺🇸 English", 1
        )[0]
        english = readme.split("## 🇺🇸 English", 1)[1]

        for phrase in (
            "Xray 26.3.27",
            "WebSocket、gRPC 与 XHTTP `stream-one`",
            "前置真实 SOCKS HTTPS",
            "修复项目内 `.venv`/`.xray`",
            "不降级为直连",
            "首次运行不会生成私密订阅地址",
            "speed.cloudflare.com",
        ):
            self.assertIn(phrase, simplified)
        for phrase in (
            "Xray 26.3.27",
            "WebSocket、gRPC 與 XHTTP `stream-one`",
            "前置真實 SOCKS HTTPS",
            "修復專案內 `.venv`/`.xray`",
            "不降級為直連",
            "首次執行不會產生私密訂閱網址",
            "speed.cloudflare.com",
        ):
            self.assertIn(phrase, traditional)
        for phrase in (
            "Xray 26.3.27",
            "WebSocket, gRPC, and XHTTP `stream-one`",
            "preflight real SOCKS HTTPS",
            "repairs only project-local `.venv`/`.xray`",
            "never falls back to direct testing",
            "first run does not generate a private subscription URL",
            "speed.cloudflare.com",
        ):
            self.assertIn(phrase, english)

    def test_chain_template_and_guidance_use_xray_only(self):
        canonical = PROJECT_ROOT / "config" / "config.example.json"
        legacy_bridge = PROJECT_ROOT / "config.example.json"
        config = json.loads(canonical.read_text(encoding="utf-8-sig"))
        self.assertIs(config["CHAIN_PROXY_TEST_ENABLED"], False)
        self.assertEqual("", config["CHAIN_PROXY_SUBSCRIPTION_URL"])
        self.assertEqual("", config["CHAIN_PROXY_CORE_PATH"])
        core_comment = config["_comment_CHAIN_PROXY_CORE_PATH"]
        self.assertIn("Xray 26.3.27", core_comment)
        self.assertIn("Windows/Linux", core_comment)
        self.assertIn(".xray", core_comment)
        self.assertIn("WS、gRPC、XHTTP stream-one", core_comment)
        self.assertNotIn("sing-box", core_comment)
        self.assertIn(
            "CfGfwAX 链式模式会跳过其明确禁止的 speed.cloudflare.com",
            config["_comment_BANDWIDTH_URL_TEMPLATE"],
        )
        self.assertEqual(canonical.read_bytes(), legacy_bridge.read_bytes())

        guidance = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("temporary Xray runtime", guidance)
        self.assertIn("XHTTP `stream-one`", guidance)
        self.assertNotIn("temporary sing-box runtime", guidance)
        self.assertNotIn("XHTTP is not supported", guidance)
        self.assertNotIn("sing-box downloads", guidance)

    def test_runtime_configuration_guidance_uses_the_canonical_template(self):
        app = (PROJECT_ROOT / "core" / "app.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("config/config.example.json", app)
        self.assertNotIn("由 config.example.json 创建", app)
        self.assertNotIn("复制 config.example.json 为 config.json", app)

    def test_cross_repository_guidance_uses_the_migrated_focused_command(self):
        guidance_files = (
            PROJECT_ROOT / "AGENTS.md",
            PROJECT_ROOT.parent / "CfGfwAX" / "AGENTS.md",
            PROJECT_ROOT.parent / "CGAX-Pages" / "AGENTS.md",
        )
        for path in guidance_files:
            guidance = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                self.assertNotIn("tests.test_chain_proxy", guidance)
                self.assertIn("work-products/tests", guidance)
        command = (
            ".\\.venv\\Scripts\\python.exe -m unittest discover "
            "-s work-products/tests -p test_chain_proxy.py -v"
        )
        self.assertIn(command, guidance_files[1].read_text(encoding="utf-8"))
        self.assertIn(command, guidance_files[2].read_text(encoding="utf-8"))

    def test_windows_and_linux_use_the_same_grouped_template_and_modules(self):
        windows_setup = (PROJECT_ROOT / "setup.ps1").read_text(encoding="utf-8-sig")
        linux_setup = (PROJECT_ROOT / "setup.sh").read_text(encoding="utf-8")

        self.assertIn('"config\\config.example.json"', windows_setup)
        self.assertIn('"scripts\\update_fork.ps1"', windows_setup)
        self.assertIn('$SchedulerModule = "core.scheduled_run"', windows_setup)
        self.assertIn('"core\\scheduled_run.py"', windows_setup)
        self.assertNotIn('$LegacyPythonScriptPath', windows_setup)

        self.assertIn(
            'CONFIG_TEMPLATE_PATH="$SCRIPT_DIR/config/config.example.json"',
            linux_setup,
        )
        self.assertIn('UPDATE_HELPER="$SCRIPT_DIR/scripts/update_fork.sh"', linux_setup)
        self.assertIn('PYTHON_MODULE="core.scheduled_run"', linux_setup)
        self.assertIn('dir "/scheduled_run.py"', linux_setup)

    def test_linux_setup_does_not_change_tracked_helper_modes(self):
        linux_setup = (PROJECT_ROOT / "setup.sh").read_text(encoding="utf-8")

        self.assertIn('run_as_target bash "$UPDATE_HELPER"', linux_setup)
        self.assertIn("chmod +x setup.sh", linux_setup)
        self.assertNotIn(
            "chmod +x setup.sh scripts/git_sync.sh scripts/update_fork.sh",
            linux_setup,
        )

    def test_updaters_validate_the_parent_root_before_mutating(self):
        windows = (PROJECT_ROOT / "scripts" / "update_fork.ps1").read_text(
            encoding="utf-8-sig"
        )
        linux = (PROJECT_ROOT / "scripts" / "update_fork.sh").read_text(
            encoding="utf-8"
        )

        self.assertLess(windows.index("Assert-ProjectLayout"), windows.index("fetch"))
        for required in (".git", "main.py", "config\\config.example.json"):
            self.assertIn(required, windows)

        validation = linux.index("if [[ ! -d $PROJECT_ROOT/.git ]]")
        fetch = linux.index('fetch origin "$BRANCH"')
        self.assertLess(validation, fetch)
        self.assertIn(
            'REPOSITORY_PREFIX="$(git rev-parse --show-prefix)"', linux
        )
        for required in (
            "$PROJECT_ROOT/.git",
            "$PROJECT_ROOT/main.py",
            "$PROJECT_ROOT/config/config.example.json",
        ):
            self.assertIn(required, linux)

    def test_update_safety_contract_is_symmetric(self):
        windows = (PROJECT_ROOT / "scripts" / "update_fork.ps1").read_text(
            encoding="utf-8-sig"
        )
        linux = (PROJECT_ROOT / "scripts" / "update_fork.sh").read_text(
            encoding="utf-8"
        )

        for marker in (
            "--ff-only",
            "UPDATE_BACKUP_RETENTION",
            "bestcfcdn_backup_latest",
            "ip.legacy.txt",
            "config.json",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, windows)
                self.assertIn(marker, linux)
        self.assertIn("恢复本机配置与结果文件", windows)
        self.assertIn("恢复本机配置与结果文件", linux)

    def test_embedded_config_migrations_compile_on_the_host_python(self):
        windows = (PROJECT_ROOT / "scripts" / "update_fork.ps1").read_text(
            encoding="utf-8-sig"
        )
        windows_merge = windows.split("$mergeCode = @'", 1)[1].split(
            "\n'@", 1
        )[0]
        compile(windows_merge, "<scripts/update_fork.ps1 merge>", "exec")

        linux = (PROJECT_ROOT / "scripts" / "update_fork.sh").read_text(
            encoding="utf-8"
        )
        embedded = re.findall(r"<<'PY'\n(.*?)\nPY", linux, re.DOTALL)
        self.assertEqual(2, len(embedded))
        for index, source in enumerate(embedded):
            compile(source, f"<scripts/update_fork.sh embedded {index}>", "exec")

    def test_final_layout_keeps_only_the_required_legacy_template_bridge(self):
        canonical_template = PROJECT_ROOT / "config" / "config.example.json"
        legacy_bridge = PROJECT_ROOT / "config.example.json"
        self.assertTrue(canonical_template.is_file())
        self.assertTrue(legacy_bridge.is_file())
        self.assertEqual(canonical_template.read_bytes(), legacy_bridge.read_bytes())
        for name in (
            "scheduled_run.py",
            "update_fork.ps1",
            "update_fork.sh",
        ):
            with self.subTest(name=name):
                self.assertFalse((PROJECT_ROOT / name).exists())


if __name__ == "__main__":
    unittest.main()
