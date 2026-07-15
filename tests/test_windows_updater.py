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
        compile(merge_code, "<update_fork.ps1 merge code>", "exec")

    def test_untracked_config_probe_does_not_emit_pathspec_error(self):
        script = (PROJECT_ROOT / "update_fork.ps1").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("function Test-GitTrackedPath", script)
        self.assertNotIn('"ls-files", "--error-unmatch"', script)


if __name__ == "__main__":
    unittest.main()
