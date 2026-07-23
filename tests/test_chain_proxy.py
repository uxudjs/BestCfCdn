import base64
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from chain_proxy import (
    ChainProxyError,
    _select_release_asset,
    build_sing_box_config,
    check_sing_box_config,
    extract_chain_template,
    prepare_sing_box,
    resolve_sing_box_path,
    sing_box_subscription_url,
)


UUID = "11111111-1111-4111-8111-111111111111"
DOMAIN = "proxy.example.com"


def chain_path(*, proxy_host="socks.example.com", global_proxy=True):
    payload = json.dumps(
        {
            "type": "socks5",
            "global": global_proxy,
            "username": "demo",
            "password": "secret",
            "hostname": proxy_host,
            "port": 1080,
        },
        separators=(",", ":"),
    ).encode()
    key = UUID.encode()
    mixed = bytes(value ^ key[index % len(key)] for index, value in enumerate(payload))
    return "/video/" + base64.b64encode(mixed).decode()


def vless_node(server, *, path=None, domain=DOMAIN, proxy_host="socks.example.com"):
    path = chain_path(proxy_host=proxy_host) if path is None else path
    return (
        f"vless://{UUID}@{server}:443?security=tls&type=ws&"
        f"host={domain}&sni={domain}&path={path}&encryption=none#{server}"
    )


def sing_box_outbound(
    server,
    *,
    path=None,
    domain=DOMAIN,
    proxy_host="socks.example.com",
    tls=None,
    extra=None,
):
    outbound = {
        "type": "vless",
        "tag": str(server),
        "server": server,
        "server_port": 443,
        "uuid": UUID,
        "tls": {
            "enabled": True,
            "server_name": domain,
            **(tls or {}),
        },
        "transport": {
            "type": "ws",
            "path": chain_path(proxy_host=proxy_host) if path is None else path,
            "headers": {"Host": domain},
        },
    }
    outbound.update(extra or {})
    return outbound


class ChainProxyTests(unittest.TestCase):
    def test_subscription_url_requests_sing_box_without_losing_other_parts(self):
        cases = {
            "https://proxy.example.com/sub/path?token=a%2Bb&foo=1#section":
                "https://proxy.example.com/sub/path?token=a%2Bb&foo=1&target=singbox#section",
            "https://proxy.example.com/sub?target=mixed&token=secret":
                "https://proxy.example.com/sub?target=singbox&token=secret",
            "https://proxy.example.com/sub?flag&note=one%20two&target=clash&note=three":
                "https://proxy.example.com/sub?flag&note=one%20two&target=singbox&note=three",
            "https://proxy.example.com/sub?token=secret&target=clash&empty=":
                "https://proxy.example.com/sub?token=secret&target=singbox&empty=",
        }

        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(expected, sing_box_subscription_url(source))

    def test_sing_box_json_collapses_addresses_and_ignores_control_outbounds(self):
        subscription = json.dumps(
            {
                "outbounds": [
                    {"type": "direct", "tag": "DIRECT"},
                    {"type": "selector", "tag": "PROXY", "outbounds": ["one"]},
                    sing_box_outbound("1.1.1.1"),
                    sing_box_outbound("2.2.2.2"),
                    sing_box_outbound("3.3.3.3", domain="other.example.com"),
                ]
            }
        )

        template = extract_chain_template(
            subscription, "https://proxy.example.com/sub?token=secret"
        )

        self.assertEqual(UUID, template.uuid)
        self.assertEqual(DOMAIN, template.server_name)
        self.assertEqual(chain_path(), template.path)

    def test_sing_box_json_distinct_templates_fail_closed(self):
        subscription = json.dumps(
            {
                "outbounds": [
                    sing_box_outbound("1.1.1.1", proxy_host="first.example.com"),
                    sing_box_outbound("2.2.2.2", proxy_host="second.example.com"),
                ]
            }
        )

        with self.assertRaisesRegex(ChainProxyError, "多个不同的链式代理模板"):
            extract_chain_template(
                subscription, "https://proxy.example.com/sub?token=secret"
            )

    def test_sing_box_json_non_global_socks5_fails_closed(self):
        subscription = json.dumps(
            {
                "outbounds": [
                    sing_box_outbound(
                        "1.1.1.1", path=chain_path(global_proxy=False)
                    )
                ]
            }
        )

        with self.assertRaisesRegex(ChainProxyError, "未启用全局代理"):
            extract_chain_template(
                subscription, "https://proxy.example.com/sub?token=secret"
            )

    def test_sing_box_json_rejects_ech_and_tls_fragment(self):
        unsafe = {
            "ECH": sing_box_outbound(
                "1.1.1.1", tls={"ech": {"enabled": True}}
            ),
            "TLS 分片": sing_box_outbound(
                "1.1.1.1", extra={"tls_fragment": {"enabled": True}}
            ),
        }

        for label, outbound in unsafe.items():
            with self.subTest(label=label), self.assertRaisesRegex(
                ChainProxyError, "ECH 或 TLS 分片"
            ):
                extract_chain_template(
                    json.dumps({"outbounds": [outbound]}),
                    "https://proxy.example.com/sub?token=secret",
                )

    def test_malformed_sing_box_json_fails_closed(self):
        with self.assertRaisesRegex(ChainProxyError, "sing-box JSON"):
            extract_chain_template(
                '{"outbounds":[',
                "https://proxy.example.com/sub?token=secret",
            )

    def test_multiple_addresses_collapse_to_one_logical_template(self):
        subscription = "\n".join(
            [
                vless_node("1.1.1.1"),
                vless_node("2.2.2.2"),
                vless_node("3.3.3.3", domain="other.example.com"),
            ]
        )

        template = extract_chain_template(
            subscription,
            "https://proxy.example.com/sub?token=secret&target=mixed",
        )

        self.assertEqual(UUID, template.uuid)
        self.assertEqual(DOMAIN, template.server_name)
        self.assertEqual(chain_path(), template.path)

    def test_base64_subscription_is_supported(self):
        encoded = base64.b64encode(vless_node("1.1.1.1").encode()).decode()

        template = extract_chain_template(
            encoded, "https://proxy.example.com/sub?token=secret"
        )

        self.assertEqual(UUID, template.uuid)

    def test_distinct_chain_templates_fail_closed(self):
        subscription = "\n".join(
            [
                vless_node("1.1.1.1", proxy_host="first.example.com"),
                vless_node("2.2.2.2", proxy_host="second.example.com"),
            ]
        )

        with self.assertRaisesRegex(ChainProxyError, "多个不同的链式代理模板"):
            extract_chain_template(
                subscription, "https://proxy.example.com/sub?token=secret"
            )

    def test_non_chain_subscription_fails_closed(self):
        with self.assertRaisesRegex(ChainProxyError, "未找到"):
            extract_chain_template(
                vless_node("1.1.1.1", path="/ordinary"),
                "https://proxy.example.com/sub?token=secret",
            )

    def test_non_global_socks5_fails_closed(self):
        with self.assertRaisesRegex(ChainProxyError, "未启用全局代理"):
            extract_chain_template(
                vless_node("1.1.1.1", path=chain_path(global_proxy=False)),
                "https://proxy.example.com/sub?token=secret",
            )

    def test_invalid_chain_payload_fails_closed(self):
        with self.assertRaisesRegex(ChainProxyError, "无法验证"):
            extract_chain_template(
                vless_node("1.1.1.1", path="/video/not-valid-base64"),
                "https://proxy.example.com/sub?token=secret",
            )

    def test_sing_box_config_maps_each_inbound_to_its_candidate(self):
        template = extract_chain_template(
            vless_node("1.1.1.1"),
            "https://proxy.example.com/sub?token=secret",
        )
        ports = {
            "104.16.0.1:443#US": 31001,
            "104.16.0.2:8443#JP": 31002,
        }

        config = build_sing_box_config(template, ports)

        self.assertEqual([31001, 31002], [item["listen_port"] for item in config["inbounds"]])
        self.assertEqual(
            [("104.16.0.1", 443), ("104.16.0.2", 8443)],
            [(item["server"], item["server_port"]) for item in config["outbounds"]],
        )
        self.assertEqual(
            ["chain-out-0", "chain-out-1"],
            [item["outbound"] for item in config["route"]["rules"]],
        )
        self.assertTrue(all(item["transport"]["path"].startswith("/video/") for item in config["outbounds"]))

    def test_sing_box_preflight_checks_config_without_starting_and_redacts(self):
        template = extract_chain_template(
            vless_node("1.1.1.1"),
            "https://proxy.example.com/sub?token=secret",
        )
        failed = subprocess.CompletedProcess(
            [], 1, stdout="", stderr=f"invalid {UUID} {template.path}"
        )

        with patch("chain_proxy.subprocess.run", return_value=failed) as run, patch(
            "chain_proxy.subprocess.Popen"
        ) as popen, self.assertRaisesRegex(
            ChainProxyError, "配置检查失败"
        ) as raised:
            check_sing_box_config("sing-box", template)

        self.assertIn("check", run.call_args.args[0])
        popen.assert_not_called()
        self.assertNotIn(UUID, str(raised.exception))
        self.assertNotIn(template.path, str(raised.exception))

    def test_sing_box_preflight_wraps_temporary_config_failure(self):
        template = extract_chain_template(
            vless_node("1.1.1.1"),
            "https://proxy.example.com/sub?token=secret",
        )
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(
            ChainProxyError, "临时配置"
        ):
            check_sing_box_config(
                "sing-box",
                template,
                temp_parent=Path(directory) / "missing",
            )


class SingBoxSetupTests(unittest.TestCase):
    @staticmethod
    def _zip(binary=b"sing-box"):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as file:
            file.writestr("sing-box-test-windows-amd64/sing-box.exe", binary)
        return archive.getvalue()

    @staticmethod
    def _opener(archive, digest=None):
        digest = digest or hashlib.sha256(archive).hexdigest()
        release = {
            "prerelease": False,
            "draft": False,
            "assets": [
                {
                    "name": "sing-box-test-windows-amd64.zip",
                    "browser_download_url": "https://github.com/SagerNet/sing-box/releases/download/v1.2.3/sing-box-test-windows-amd64.zip",
                    "digest": f"sha256:{digest}",
                }
            ],
        }

        def open_url(request, timeout=0):
            url = getattr(request, "full_url", request)
            if url.endswith("/releases/latest"):
                return io.BytesIO(json.dumps(release).encode())
            if url == "https://github.com/SagerNet/sing-box/releases/download/v1.2.3/sing-box-test-windows-amd64.zip":
                return io.BytesIO(archive)
            raise AssertionError(f"unexpected URL: {url}")

        return open_url

    def test_resolve_prefers_configured_then_project_local_then_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configured = root / "configured.exe"
            local = root / ".runtime" / "sing-box" / "sing-box.exe"
            path_core = root / "path" / "sing-box.exe"
            for candidate in (configured, local, path_core):
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_bytes(b"core")

            with patch("chain_proxy.shutil.which", return_value=str(path_core)):
                self.assertEqual(
                    str(configured.resolve()),
                    resolve_sing_box_path("configured.exe", directory),
                )
                configured.unlink()
                self.assertEqual(str(local.resolve()), resolve_sing_box_path("", directory))
                local.unlink()
                self.assertEqual(str(path_core), resolve_sing_box_path("", directory))

    def test_select_release_asset_maps_supported_platforms(self):
        release = {
            "assets": [
                {"name": "sing-box-1.2.3-linux-arm64.tar.gz"},
                {"name": "sing-box-1.2.3-windows-amd64.zip"},
            ]
        }

        self.assertEqual(
            "sing-box-1.2.3-windows-amd64.zip",
            _select_release_asset(release, "Windows", "AMD64")["name"],
        )
        self.assertEqual(
            "sing-box-1.2.3-linux-arm64.tar.gz",
            _select_release_asset(release, "Linux", "aarch64")["name"],
        )
        with self.assertRaisesRegex(ChainProxyError, "资产"):
            _select_release_asset({"assets": None}, "Windows", "AMD64")
        with self.assertRaisesRegex(ChainProxyError, "不支持"):
            _select_release_asset(release, "Darwin", "arm64")

    def test_prepare_installs_verified_core_and_updates_only_path(self):
        archive = self._zip()
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text(
                json.dumps({"CHAIN_PROXY_TEST_ENABLED": True, "keep": "value"}),
                encoding="utf-8",
            )
            completed = type("Result", (), {"returncode": 0, "stdout": "sing-box 1.2.3", "stderr": ""})()

            with patch("chain_proxy.subprocess.run", return_value=completed):
                core_path = prepare_sing_box(
                    config_path,
                    opener=self._opener(archive),
                    system_name="Windows",
                    machine="AMD64",
                )

            self.assertEqual(b"sing-box", Path(core_path).read_bytes())
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual("value", config["keep"])
            self.assertEqual(
                os.path.join(".runtime", "sing-box", "sing-box.exe"),
                config["CHAIN_PROXY_CORE_PATH"],
            )

            with patch("chain_proxy.urlopen", side_effect=AssertionError("downloaded twice")), patch(
                "chain_proxy.subprocess.run", return_value=completed
            ):
                self.assertEqual(core_path, prepare_sing_box(config_path))

    def test_prepare_rejects_digest_mismatch_without_changing_config(self):
        archive = self._zip()
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            original = json.dumps({"CHAIN_PROXY_TEST_ENABLED": True, "keep": "value"})
            config_path.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(ChainProxyError, "SHA-256"):
                prepare_sing_box(
                    config_path,
                    opener=self._opener(archive, digest="0" * 64),
                    system_name="Windows",
                    machine="AMD64",
                )

            self.assertEqual(original, config_path.read_text(encoding="utf-8"))
            self.assertFalse((Path(directory) / ".runtime" / "sing-box").exists())

    def test_prepare_rejects_unsafe_archive_member(self):
        archive_file = io.BytesIO()
        with zipfile.ZipFile(archive_file, "w") as archive:
            archive.writestr("../sing-box.exe", b"sing-box")
        archive = archive_file.getvalue()

        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text(
                json.dumps({"CHAIN_PROXY_TEST_ENABLED": True}), encoding="utf-8"
            )
            with self.assertRaisesRegex(ChainProxyError, "归档"):
                prepare_sing_box(
                    config_path,
                    opener=self._opener(archive),
                    system_name="Windows",
                    machine="AMD64",
                )


    def test_prepare_rejects_failed_version_check_without_installing(self):
        archive = self._zip()
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            original = json.dumps({"CHAIN_PROXY_TEST_ENABLED": True})
            config_path.write_text(original, encoding="utf-8")
            failed = type("Result", (), {"returncode": 1, "stdout": "", "stderr": "bad"})()

            with patch("chain_proxy.subprocess.run", return_value=failed), self.assertRaisesRegex(
                ChainProxyError, "版本"
            ):
                prepare_sing_box(
                    config_path,
                    opener=self._opener(archive),
                    system_name="Windows",
                    machine="AMD64",
                )

            self.assertEqual(original, config_path.read_text(encoding="utf-8"))
            self.assertFalse((Path(directory) / ".runtime" / "sing-box" / "sing-box.exe").exists())

    def test_prepare_rolls_back_core_when_config_replace_fails(self):
        archive = self._zip()
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            original = json.dumps({"CHAIN_PROXY_TEST_ENABLED": True})
            config_path.write_text(original, encoding="utf-8")
            completed = type("Result", (), {"returncode": 0, "stdout": "sing-box 1.2.3", "stderr": ""})()
            real_replace = os.replace

            def replace(source, destination):
                if os.path.abspath(destination) == os.path.abspath(config_path):
                    raise OSError("config locked")
                return real_replace(source, destination)

            with patch("chain_proxy.subprocess.run", return_value=completed), patch(
                "chain_proxy.os.replace", side_effect=replace
            ), self.assertRaisesRegex(ChainProxyError, "配置"):
                prepare_sing_box(
                    config_path,
                    opener=self._opener(archive),
                    system_name="Windows",
                    machine="AMD64",
                )

            self.assertEqual(original, config_path.read_text(encoding="utf-8"))
            self.assertFalse((Path(directory) / ".runtime" / "sing-box" / "sing-box.exe").exists())
    def test_prepare_is_noop_when_chain_proxy_is_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            original = json.dumps({"CHAIN_PROXY_TEST_ENABLED": False})
            config_path.write_text(original, encoding="utf-8")

            self.assertIsNone(
                prepare_sing_box(
                    config_path,
                    opener=lambda *args, **kwargs: self.fail("network accessed"),
                )
            )
            self.assertEqual(original, config_path.read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
