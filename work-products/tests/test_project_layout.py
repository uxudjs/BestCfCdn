import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ProjectLayoutTests(unittest.TestCase):
    def test_internal_package_uses_an_unambiguous_name(self):
        self.assertTrue((PROJECT_ROOT / "core" / "__init__.py").is_file())
        self.assertFalse((PROJECT_ROOT / "bestcfcdn").exists())
        self.assertFalse((PROJECT_ROOT / "bestcfcdn_core").exists())

    def test_package_init_has_no_import_time_behavior(self):
        package_init = PROJECT_ROOT / "core" / "__init__.py"
        tree = ast.parse(package_init.read_text(encoding="utf-8"))
        executable_statements = [
            node
            for node in tree.body
            if not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
        ]
        self.assertEqual([], executable_statements)

    def test_runtime_paths_remain_at_repository_root(self):
        from core import paths

        expected = {
            "PROJECT_ROOT": PROJECT_ROOT,
            "CONFIG_FILE": PROJECT_ROOT / "config.json",
            "CONFIG_TEMPLATE_FILE": PROJECT_ROOT / "config" / "config.example.json",
            "LOCAL_OUTPUT_FILE": PROJECT_ROOT / "ip.local.txt",
            "REMOTE_OUTPUT_FILE": PROJECT_ROOT / "ip.txt",
            "TOKEN_FILE": PROJECT_ROOT / "valid_tokens.txt",
            "IPINFO_CACHE_FILE": PROJECT_ROOT / "ipinfo_cache.txt",
            "LOG_FILE": PROJECT_ROOT / "cfnb.log",
            "CRON_LOG_FILE": PROJECT_ROOT / "cron.log",
            "SCHEDULE_LOCK_FILE": PROJECT_ROOT / ".cfnb_schedule.lock",
            "SING_BOX_DIR": PROJECT_ROOT / ".sing-box",
        }

        for name, expected_path in expected.items():
            with self.subTest(name=name):
                self.assertEqual(expected_path, getattr(paths, name))
                self.assertNotEqual(PROJECT_ROOT / "core", expected_path.parent)

    def test_local_state_implementation_lives_only_in_the_package(self):
        self.assertTrue((PROJECT_ROOT / "core" / "local_state.py").is_file())
        self.assertFalse((PROJECT_ROOT / "local_state.py").exists())

    def test_proxy_scoring_implementation_lives_only_in_the_package(self):
        self.assertTrue((PROJECT_ROOT / "core" / "proxy_scoring.py").is_file())
        self.assertFalse((PROJECT_ROOT / "proxy_scoring.py").exists())

    def test_chain_proxy_implementation_lives_only_in_the_package(self):
        self.assertTrue((PROJECT_ROOT / "core" / "chain_proxy.py").is_file())
        self.assertFalse((PROJECT_ROOT / "chain_proxy.py").exists())

    def test_github_sync_module_and_scripts_use_the_grouped_layout(self):
        self.assertTrue((PROJECT_ROOT / "core" / "github_sync.py").is_file())
        self.assertFalse((PROJECT_ROOT / "github_sync.py").exists())
        for name in ("git_sync.ps1", "git_sync.sh"):
            with self.subTest(name=name):
                self.assertTrue((PROJECT_ROOT / "scripts" / name).is_file())
                self.assertFalse((PROJECT_ROOT / name).exists())

    def test_scheduled_run_implementation_lives_only_in_the_package(self):
        self.assertTrue((PROJECT_ROOT / "core" / "scheduled_run.py").is_file())
        self.assertFalse((PROJECT_ROOT / "scheduled_run.py").exists())

    def test_main_is_a_thin_public_entrypoint(self):
        self.assertTrue((PROJECT_ROOT / "core" / "app.py").is_file())
        wrapper = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("from core.app import main", wrapper)
        self.assertNotIn("def bandwidth_filter", wrapper)
        self.assertNotIn("def sync_to_github", wrapper)

        import main
        from core import app

        self.assertIs(app.main, main.main)

    def test_windows_updater_lives_only_under_scripts(self):
        implementation = PROJECT_ROOT / "scripts" / "update_fork.ps1"
        self.assertTrue(implementation.is_file())
        self.assertFalse((PROJECT_ROOT / "update_fork.ps1").exists())

    def test_linux_updater_lives_only_under_scripts(self):
        implementation = PROJECT_ROOT / "scripts" / "update_fork.sh"
        self.assertTrue(implementation.is_file())
        self.assertFalse((PROJECT_ROOT / "update_fork.sh").exists())

    def test_final_root_entrypoint_allowlist_is_locked(self):
        root_entrypoints = {
            path.name
            for pattern in ("*.py", "*.ps1", "*.sh")
            for path in PROJECT_ROOT.glob(pattern)
        }
        self.assertEqual({"main.py", "setup.ps1", "setup.sh"}, root_entrypoints)
        canonical_template = PROJECT_ROOT / "config" / "config.example.json"
        legacy_bridge = PROJECT_ROOT / "config.example.json"
        self.assertTrue(canonical_template.is_file())
        self.assertTrue(legacy_bridge.is_file())
        self.assertEqual(canonical_template.read_bytes(), legacy_bridge.read_bytes())

    def test_cache_candidates_are_limited_to_the_approved_whitelist(self):
        from core.paths import is_removable_cache_candidate

        removable = (
            PROJECT_ROOT / "__pycache__" / "module.cpython-313.pyc",
            PROJECT_ROOT / "core" / "__pycache__",
            PROJECT_ROOT / ".pytest_cache",
            PROJECT_ROOT / ".mypy_cache" / "state.json",
            PROJECT_ROOT / ".ruff_cache" / "state.json",
            PROJECT_ROOT / "ipinfo_cache.txt",
        )
        protected = (
            PROJECT_ROOT / ".venv" / "module.pyc",
            PROJECT_ROOT / ".codegraph" / "module.pyc",
            PROJECT_ROOT / ".sing-box" / "module.pyc",
            PROJECT_ROOT / ".agents" / "module.pyc",
            PROJECT_ROOT / "config.json",
            PROJECT_ROOT / "ip.txt",
            PROJECT_ROOT / "ip.local.txt",
            PROJECT_ROOT / "valid_tokens.txt",
            PROJECT_ROOT / "cfnb.log",
            PROJECT_ROOT / "cron.log",
            PROJECT_ROOT / "notes.py",
            PROJECT_ROOT.parent / "outside.pyc",
            PROJECT_ROOT.parent / "bestcfcdn_backup_latest" / "module.pyc",
        )

        for candidate in removable:
            with self.subTest(removable=candidate):
                self.assertTrue(is_removable_cache_candidate(candidate))
        for candidate in protected:
            with self.subTest(protected=candidate):
                self.assertFalse(is_removable_cache_candidate(candidate))


if __name__ == "__main__":
    unittest.main()
