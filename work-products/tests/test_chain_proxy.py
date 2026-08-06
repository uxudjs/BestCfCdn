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
from urllib.parse import urlencode
from unittest import mock

import core.chain_proxy as chain_proxy
from core.chain_proxy import (
    ChainProxyError,
    extract_chain_template,
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


def vless_node(
    server,
    *,
    port=443,
    path=None,
    domain=DOMAIN,
    proxy_host="socks.example.com",
    extra=None,
):
    path = chain_path(proxy_host=proxy_host) if path is None else path
    query = {
        "security": "tls",
        "type": "ws",
        "host": domain,
        "sni": domain,
        "path": path,
        "encryption": "none",
    }
    query.update(extra or {})
    endpoint = server if port is None else f"{server}:{port}"
    return f"vless://{UUID}@{endpoint}?{urlencode(query)}#{server}"


class ChainProxyTests(unittest.TestCase):
    def test_subscription_result_preserves_three_stable_endpoints_for_mixed_and_base64(self):
        subscription = "\n".join(
            [
                vless_node("1.1.1.1"),
                vless_node("2.2.2.2", port=8443),
                vless_node("1.1.1.1"),
                vless_node("3.3.3.3"),
                vless_node("4.4.4.4"),
                vless_node("5.5.5.5", domain="other.example.com"),
            ]
        )

        mixed = chain_proxy.extract_chain_subscription(
            subscription,
            "https://proxy.example.com/sub?token=secret&target=mixed",
        )
        encoded = chain_proxy.extract_chain_subscription(
            base64.b64encode(subscription.encode()).decode(),
            "https://proxy.example.com/sub?token=secret&target=base64",
        )

        expected_endpoints = (
            ("1.1.1.1", 443),
            ("2.2.2.2", 8443),
            ("3.3.3.3", 443),
        )
        self.assertEqual(mixed.template, encoded.template)
        self.assertEqual(
            expected_endpoints,
            tuple((endpoint.server, endpoint.port) for endpoint in mixed.endpoints),
        )
        self.assertEqual(mixed.endpoints, encoded.endpoints)
        self.assertEqual(DOMAIN, mixed.source_id)

    def test_xhttp_stream_one_preserves_transport_and_tls_fields(self):
        path = chain_path() + "/"

        result = chain_proxy.extract_chain_subscription(
            vless_node(
                "198.51.100.13",
                path=path,
                extra={
                    "type": "xhttp",
                    "mode": "stream-one",
                    "ech": "ech.example+https://doh.example/dns-query?type=https",
                    "fragment": "1,40-60,30-50,tlshello",
                    "fp": "chrome",
                    "flow": "xtls-rprx-vision",
                    "allowInsecure": "1",
                },
            ),
            f"https://{DOMAIN}/subscribe?token=secret",
        )

        template = result.template
        self.assertEqual("tls", template.security)
        self.assertEqual(DOMAIN, template.server_name)
        self.assertEqual(DOMAIN, template.host)
        self.assertEqual(path, template.path)
        self.assertEqual("xhttp", template.transport)
        self.assertEqual("stream-one", template.mode)
        self.assertEqual("xtls-rprx-vision", template.flow)
        self.assertTrue(template.insecure)
        self.assertEqual("ech.example", template.ech_query_server_name)
        self.assertEqual("doh.example", template.ech_dns_server)
        self.assertEqual("/dns-query?type=https", template.ech_dns_path)
        self.assertEqual("1,40-60,30-50,tlshello", template.tls_fragment)
        self.assertEqual("chrome", template.fingerprint)

    def test_xhttp_requires_exact_stream_one_mode(self):
        for mode in (None, "packet-up", "Stream-One"):
            extra = {"type": "xhttp"}
            if mode is not None:
                extra["mode"] = mode
            with self.subTest(mode=mode), self.assertRaisesRegex(
                ChainProxyError, "mode=stream-one"
            ):
                chain_proxy.extract_chain_subscription(
                    vless_node("198.51.100.13", extra=extra),
                    f"https://{DOMAIN}/subscribe",
                )

    def test_xhttp_rejects_two_trailing_slashes_and_damaged_ciphertext(self):
        valid_path = chain_path()
        for path in (valid_path + "//", valid_path[:-1] + "x"):
            with self.subTest(path=path[-8:]), self.assertRaises(ChainProxyError):
                chain_proxy.extract_chain_subscription(
                    vless_node(
                        "198.51.100.13",
                        path=path,
                        extra={"type": "xhttp", "mode": "stream-one"},
                    ),
                    f"https://{DOMAIN}/subscribe",
                )

    def test_matching_node_without_a_valid_probe_endpoint_fails_closed(self):
        for port in (None, 70000):
            with self.subTest(port=port), self.assertRaises(ChainProxyError):
                chain_proxy.extract_chain_subscription(
                    vless_node("198.51.100.13", port=port),
                    f"https://{DOMAIN}/subscribe",
                )

    def test_subscription_result_repr_redacts_subscription_and_chain_secrets(self):
        path = chain_path()
        result = chain_proxy.extract_chain_subscription(
            vless_node("198.51.100.13", path=path),
            f"https://{DOMAIN}/subscribe?token=top-secret",
        )

        snapshot = repr(result)
        for secret in (UUID, path, "top-secret", "demo", "secret"):
            self.assertNotIn(secret, snapshot)

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

    def test_distinct_chain_templates_remain_bound_to_their_endpoints(self):
        subscription = "\n".join(
            [
                vless_node("1.1.1.1", proxy_host="first.example.com"),
                vless_node("2.2.2.2", proxy_host="second.example.com"),
            ]
        )

        result = chain_proxy.extract_chain_subscription(
            subscription, "https://proxy.example.com/sub?token=secret"
        )

        self.assertEqual(2, len(result.probes))
        self.assertNotEqual(result.probes[0].template, result.probes[1].template)
        self.assertEqual(
            ("1.1.1.1", "2.2.2.2"),
            tuple(probe.endpoint.server for probe in result.probes),
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

    def test_xray_ws_config_maps_each_inbound_to_its_candidate(self):
        template = extract_chain_template(
            vless_node("1.1.1.1"),
            "https://proxy.example.com/sub?token=secret",
        )
        ports = {
            "104.16.0.1:443#US": 31001,
            "104.16.0.2:8443#JP": 31002,
        }

        config = chain_proxy.build_xray_config(template, ports)

        self.assertEqual([31001, 31002], [item["port"] for item in config["inbounds"]])
        self.assertTrue(all(item["protocol"] == "socks" for item in config["inbounds"]))
        self.assertEqual(
            [("104.16.0.1", 443), ("104.16.0.2", 8443)],
            [
                (item["settings"]["address"], item["settings"]["port"])
                for item in config["outbounds"]
            ],
        )
        self.assertEqual(
            ["chain-out-0", "chain-out-1"],
            [item["outboundTag"] for item in config["routing"]["rules"]],
        )
        for outbound in config["outbounds"]:
            self.assertEqual(UUID, outbound["settings"]["id"])
            self.assertEqual("none", outbound["settings"]["encryption"])
            self.assertEqual("ws", outbound["streamSettings"]["network"])
            self.assertNotIn("method", outbound["streamSettings"])
            self.assertEqual(
                chain_path(),
                outbound["streamSettings"]["wsSettings"]["path"],
            )
            self.assertEqual(
                DOMAIN,
                outbound["streamSettings"]["wsSettings"]["host"],
            )

    def test_ech_fragment_fingerprint_and_flow_map_to_xray(self):
        template = extract_chain_template(
            vless_node(
                "198.51.100.10",
                extra={
                    "ech": "ech.example+https://doh.example/dns-query",
                    "fragment": "1,40-60,30-50,tlshello",
                    "fp": "chrome",
                    "flow": "xtls-rprx-vision",
                },
            ),
            f"https://{DOMAIN}/subscribe",
        )

        config = chain_proxy.build_xray_config(
            template, {"198.51.100.10:443": 19090}
        )
        outbound = config["outbounds"][0]
        tls = outbound["streamSettings"]["tlsSettings"]
        self.assertEqual(
            "ech.example+https://doh.example/dns-query",
            tls["echConfigList"],
        )
        self.assertEqual("chrome", tls["fingerprint"])
        self.assertNotIn("allowInsecure", tls)
        self.assertEqual("xtls-rprx-vision", outbound["settings"]["flow"])
        self.assertEqual(
            {"dialerProxy": "fragment-out-0"},
            outbound["streamSettings"]["sockopt"],
        )
        self.assertEqual(
            {
                "packets": "tlshello",
                "length": "40-60",
                "interval": "30-50",
            },
            config["outbounds"][1]["settings"]["fragment"],
        )

    def test_ech_without_an_explicit_query_name_uses_the_tls_name(self):
        template = extract_chain_template(
            vless_node(
                "198.51.100.14",
                extra={"ech": "https://doh.example/dns-query", "fragment": "3,1,tlshello"},
            ),
            f"https://{DOMAIN}/subscribe",
        )

        config = chain_proxy.build_xray_config(
            template, {"198.51.100.14:443": 19090}
        )
        tls = config["outbounds"][0]["streamSettings"]["tlsSettings"]
        self.assertEqual("https://doh.example/dns-query", tls["echConfigList"])
        self.assertEqual(
            {"packets": "tlshello", "length": "3", "interval": "1"},
            config["outbounds"][1]["settings"]["fragment"],
        )

    def test_grpc_template_maps_to_grpc_transport(self):
        service_name = chain_path()
        template = extract_chain_template(
            vless_node(
                "198.51.100.11",
                extra={
                    "type": "grpc",
                    "mode": "multi",
                    "authority": DOMAIN,
                    "serviceName": service_name,
                },
            ),
            f"https://{DOMAIN}/subscribe",
        )

        config = chain_proxy.build_xray_config(
            template, {"198.51.100.11:443": 19090}
        )
        self.assertEqual(
            {
                "authority": DOMAIN,
                "serviceName": service_name,
                "multiMode": True,
            },
            config["outbounds"][0]["streamSettings"]["grpcSettings"],
        )
        self.assertEqual("grpc", config["outbounds"][0]["streamSettings"]["network"])
        self.assertNotIn("method", config["outbounds"][0]["streamSettings"])

    def test_xhttp_template_maps_only_stream_one_without_mux(self):
        template = extract_chain_template(
            vless_node(
                "198.51.100.13",
                extra={"type": "xhttp", "mode": "stream-one"},
            ),
            f"https://{DOMAIN}/subscribe",
        )

        config = chain_proxy.build_xray_config(
            template, {"198.51.100.13:443": 19090}
        )
        stream = config["outbounds"][0]["streamSettings"]
        self.assertEqual("xhttp", stream["network"])
        self.assertNotIn("method", stream)
        self.assertEqual(
            {"host": DOMAIN, "path": chain_path(), "mode": "stream-one"},
            stream["xhttpSettings"],
        )
        self.assertNotIn("mux", config["outbounds"][0])

    def test_unmappable_fragment_and_grpc_mode_fail_closed(self):
        for fragment in ("enabled", "1,2", "0,40-60,30-50,tlshello"):
            with self.subTest(fragment=fragment), self.assertRaisesRegex(
                ChainProxyError, "fragment"
            ):
                template = extract_chain_template(
                    vless_node("198.51.100.10", extra={"fragment": fragment}),
                    f"https://{DOMAIN}/subscribe",
                )
                chain_proxy.build_xray_config(
                    template, {"198.51.100.10:443": 19090}
                )

        template = extract_chain_template(
            vless_node(
                "198.51.100.11",
                extra={
                    "type": "grpc",
                    "mode": "unsupported",
                    "authority": DOMAIN,
                    "serviceName": chain_path(),
                },
            ),
            f"https://{DOMAIN}/subscribe",
        )
        with self.assertRaisesRegex(ChainProxyError, "gRPC mode"):
            chain_proxy.build_xray_config(
                template, {"198.51.100.11:443": 19090}
            )

        template = extract_chain_template(
            vless_node(
                "198.51.100.12",
                extra={"allowInsecure": "1"},
            ),
            f"https://{DOMAIN}/subscribe",
        )
        with self.assertRaisesRegex(ChainProxyError, "allowInsecure=true"):
            chain_proxy.build_xray_config(
                template, {"198.51.100.12:443": 19090}
            )

    def test_invalid_ech_dns_is_rejected(self):
        with self.assertRaisesRegex(ChainProxyError, "HTTPS URL"):
            extract_chain_template(
                vless_node(
                    "198.51.100.12",
                    extra={"ech": "ech.example+http://doh.example/dns-query"},
                ),
                f"https://{DOMAIN}/subscribe",
            )

    def test_xray_runtime_checks_starts_and_cleans_up(self):
        template = extract_chain_template(
            vless_node("198.51.100.13"),
            f"https://{DOMAIN}/subscribe",
        )
        checked = mock.Mock(returncode=0, stdout="", stderr="")
        process = mock.Mock()
        process.poll.return_value = None

        with tempfile.TemporaryDirectory() as temp_parent, mock.patch(
            "core.chain_proxy.allocate_local_ports",
            return_value={"1.1.1.1:443": 19090},
        ), mock.patch(
            "core.chain_proxy.subprocess.run", return_value=checked
        ) as run, mock.patch(
            "core.chain_proxy.subprocess.Popen", return_value=process
        ) as popen, mock.patch(
            "core.chain_proxy.socket.create_connection"
        ):
            with chain_proxy.XrayRuntime(
                "xray.exe", template, ["1.1.1.1:443"], temp_parent
            ) as runtime:
                config_path = run.call_args.args[0][-1]
                self.assertTrue(os.path.isfile(config_path))
                self.assertEqual(19090, runtime.proxy_ports["1.1.1.1:443"])
                self.assertEqual(
                    ["xray.exe", "run", "-test", "-config", config_path],
                    run.call_args.args[0],
                )
                self.assertEqual(
                    ["xray.exe", "run", "-config", config_path],
                    popen.call_args.args[0],
                )
            self.assertFalse(os.path.exists(config_path))
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=5)

    def test_xray_runtime_redacts_secrets_on_config_failure(self):
        path = chain_path()
        template = extract_chain_template(
            vless_node("198.51.100.13", path=path),
            f"https://{DOMAIN}/subscribe",
        )
        checked = mock.Mock(
            returncode=23,
            stdout="",
            stderr=f"invalid UUID {UUID} and path {path}",
        )

        with tempfile.TemporaryDirectory() as temp_parent, mock.patch(
            "core.chain_proxy.allocate_local_ports",
            return_value={"198.51.100.13:443": 19090},
        ), mock.patch(
            "core.chain_proxy.subprocess.run", return_value=checked
        ):
            with self.assertRaises(ChainProxyError) as raised:
                with chain_proxy.XrayRuntime(
                    "xray.exe", template, ["198.51.100.13:443"], temp_parent
                ):
                    pass
        message = str(raised.exception)
        self.assertNotIn(UUID, message)
        self.assertNotIn(path, message)
        self.assertIn("***", message)

    def test_xray_manifest_covers_the_windows_linux_support_matrix(self):
        expected = {
            ("Windows", "AMD64"): ("Xray-windows-64.zip", 20913304, "d004c39288ce9ada487c6f398c7c545f7d749e44bdfdd59dbc9f865afba4e1ad"),
            ("Windows", "i686"): ("Xray-windows-32.zip", 20473037, "956a5ec00bce747c7936dc4ff7ac570df1c8030b0a4a8640f843488365084db3"),
            ("Windows", "ARM64"): ("Xray-windows-arm64-v8a.zip", 19316452, "35d4ed6ec21224fb22b07c2c3f672e2350cd536f2c74d309150175a76365ea88"),
            ("Linux", "x86_64"): ("Xray-linux-64.zip", 21136402, "23cd9af937744d97776ee35ecad4972cf4b2109d1e0fe6be9930467608f7c8ae"),
            ("Linux", "i386"): ("Xray-linux-32.zip", 20267274, "d1eeb0d9a9106eefd286fbb73595c2dfe1c48c56aa91ba1c9aefe04f188d0927"),
            ("Linux", "aarch64"): ("Xray-linux-arm64-v8a.zip", 19716427, "4d30283ae614e3057f730f67cd088a42be6fdf91f8639d82cb69e48cde80413c"),
            ("Linux", "armv7l"): ("Xray-linux-arm32-v7a.zip", 20201341, "c7265ae13c63ca0241a037df4ef960ad37938c8a67d984cc08834b2cfdf5654b"),
            ("Linux", "armv6l"): ("Xray-linux-arm32-v6.zip", 20221247, "0c6e751e2bba3f3ff09a793dd6a6bc45fd6fd89f49b49dfc0cf6d922dc123bec"),
            ("Linux", "armv5l"): ("Xray-linux-arm32-v5.zip", 20230102, "0da9a632e15e82504831f61bf6b46c21e3081bcc79ad46bdc16e7dc2f0dc9088"),
            ("Linux", "riscv64"): ("Xray-linux-riscv64.zip", 20199421, "627ea5870b6fd05d95b7f4ceb5a54d7f2664dd075b30a7ac46ee9a6f9653d6f8"),
            ("Linux", "s390x"): ("Xray-linux-s390x.zip", 20699974, "a209bcea3df9b0dc1ef5938695679ba1308ad9678a671279d7b1b6c5ceec09c7"),
            ("Linux", "ppc64le"): ("Xray-linux-ppc64le.zip", 19725091, "2f9ad6c4f35966b1e012c69d601a98bb8b63aba933d303ba6d7b5b67f2ab2acb"),
            ("Linux", "loongarch64"): ("Xray-linux-loong64.zip", 20282863, "4f9c917976d4e454740aa7b4e0ef9c13c950d91152aaa7926aaa652698e6e6c0"),
        }
        for environment, manifest in expected.items():
            with self.subTest(environment=environment):
                asset = chain_proxy._xray_asset(*environment)
                self.assertEqual(manifest, (asset.name, asset.size, asset.sha256))
                self.assertEqual(
                    f"https://github.com/XTLS/Xray-core/releases/download/v26.3.27/{asset.name}",
                    asset.url,
                )
                self.assertEqual(
                    "xray.exe" if environment[0] == "Windows" else "xray",
                    asset.executable_name,
                )

    def test_xray_manifest_rejects_platforms_outside_windows_linux(self):
        for environment in (("Darwin", "x86_64"), ("FreeBSD", "amd64")):
            with self.subTest(environment=environment), self.assertRaisesRegex(
                ChainProxyError, "Windows/Linux"
            ):
                chain_proxy._xray_asset(*environment)

    def test_xray_binary_validation_requires_identity_version_and_config_check(self):
        success = mock.Mock(returncode=0, stdout="Xray 26.3.27\n", stderr="")
        wrong_identity = mock.Mock(returncode=0, stdout="sing-box version 1.13\n", stderr="")
        wrong_version = mock.Mock(returncode=0, stdout="Xray 26.3.23\n", stderr="")
        check_failed = mock.Mock(returncode=23, stdout="", stderr="invalid config")

        with mock.patch("core.chain_proxy.subprocess.run", side_effect=[success, success]):
            self.assertEqual("xray.exe", chain_proxy._validate_xray_binary("xray.exe"))
        for version_result in (wrong_identity, wrong_version):
            with self.subTest(output=version_result.stdout), mock.patch(
                "core.chain_proxy.subprocess.run", return_value=version_result
            ), self.assertRaisesRegex(ChainProxyError, "身份或版本"):
                chain_proxy._validate_xray_binary("external.exe")
        with mock.patch(
            "core.chain_proxy.subprocess.run", side_effect=[success, check_failed]
        ), self.assertRaisesRegex(ChainProxyError, "配置检查"):
            chain_proxy._validate_xray_binary("external.exe")

    def test_xray_resolution_uses_config_local_path_and_path_in_order(self):
        with tempfile.TemporaryDirectory() as project_dir:
            configured = os.path.join(project_dir, "configured.exe")
            local = os.path.join(project_dir, ".xray", "xray.exe")
            on_path = os.path.join(project_dir, "path-xray.exe")
            os.makedirs(os.path.dirname(local))
            for path in (configured, local, on_path):
                Path(path).write_bytes(path.encode())

            validations = []

            def validate(path):
                validations.append(path)
                if path == configured:
                    raise ChainProxyError("invalid configured core")
                return path

            with mock.patch("core.chain_proxy.platform.system", return_value="Windows"), mock.patch(
                "core.chain_proxy.shutil.which", return_value=on_path
            ), mock.patch(
                "core.chain_proxy._validate_xray_binary", side_effect=validate
            ), mock.patch("core.chain_proxy._download_xray") as download:
                resolved = chain_proxy.resolve_xray_path(configured, project_dir)

            self.assertEqual(local, resolved)
            self.assertEqual([configured, local], validations)
            download.assert_not_called()

            os.remove(local)
            validations.clear()
            with mock.patch("core.chain_proxy.platform.system", return_value="Windows"), mock.patch(
                "core.chain_proxy.shutil.which", return_value=on_path
            ), mock.patch(
                "core.chain_proxy._validate_xray_binary", side_effect=validate
            ), mock.patch("core.chain_proxy._download_xray") as download:
                resolved = chain_proxy.resolve_xray_path(configured, project_dir)

            self.assertEqual(on_path, resolved)
            self.assertEqual([configured, on_path], validations)
            download.assert_not_called()

    def test_invalid_external_xray_is_untouched_when_project_copy_is_installed(self):
        with tempfile.TemporaryDirectory() as project_dir:
            external = os.path.join(project_dir, "external.exe")
            Path(external).write_bytes(b"external-unchanged")
            installed = os.path.join(project_dir, ".xray", "xray.exe")

            def validate(path):
                if path == external:
                    raise ChainProxyError("invalid external core")
                return path

            def download(_base_dir):
                os.makedirs(os.path.dirname(installed), exist_ok=True)
                Path(installed).write_bytes(b"installed")
                return installed

            with mock.patch("core.chain_proxy.platform.system", return_value="Windows"), mock.patch(
                "core.chain_proxy.shutil.which", return_value=None
            ), mock.patch(
                "core.chain_proxy._validate_xray_binary", side_effect=validate
            ), mock.patch(
                "core.chain_proxy._download_xray", side_effect=download
            ):
                resolved = chain_proxy.resolve_xray_path(external, project_dir)

            self.assertEqual(installed, resolved)
            self.assertEqual(b"external-unchanged", Path(external).read_bytes())

    def test_linked_project_xray_directory_is_rejected_before_download(self):
        with tempfile.TemporaryDirectory() as project_dir:
            install_dir = os.path.join(project_dir, ".xray")
            os.makedirs(install_dir)

            real_islink = os.path.islink

            def is_link(path):
                if os.path.abspath(path) == os.path.abspath(install_dir):
                    return True
                return real_islink(path)

            with mock.patch(
                "core.chain_proxy.os.path.islink", side_effect=is_link
            ), mock.patch(
                "core.chain_proxy.shutil.which", return_value=None
            ), mock.patch(
                "core.chain_proxy._download_xray", return_value="unexpected"
            ) as download, self.assertRaisesRegex(
                ChainProxyError, "链接|重解析"
            ):
                chain_proxy.resolve_xray_path("", project_dir)

            download.assert_not_called()

    def test_windows_reparse_point_is_treated_as_a_link_boundary(self):
        metadata = mock.Mock(st_file_attributes=0x400)
        with mock.patch(
            "core.chain_proxy.os.path.islink", return_value=False
        ), mock.patch("core.chain_proxy.os.lstat", return_value=metadata):
            self.assertTrue(chain_proxy._is_link_or_reparse(".xray"))

    def test_xray_archive_rejects_traversal_and_duplicate_executables(self):
        cases = {
            "traversal": [("../xray.exe", b"xray")],
            "duplicate": [("xray.exe", b"one"), ("nested/xray.exe", b"two")],
        }
        for name, members in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_dir:
                archive = os.path.join(temp_dir, "asset.zip")
                target = os.path.join(temp_dir, "candidate.exe")
                with zipfile.ZipFile(archive, "w") as bundle:
                    for member, payload in members:
                        bundle.writestr(member, payload)
                with self.assertRaises(ChainProxyError):
                    chain_proxy._extract_xray_archive(archive, target, "xray.exe")
                self.assertFalse(os.path.exists(target))

    def test_xray_download_validates_before_atomic_replacement(self):
        executable = b"new xray executable"
        archive_buffer = io.BytesIO()
        with zipfile.ZipFile(archive_buffer, "w") as bundle:
            bundle.writestr("Xray-windows-64/xray.exe", executable)
        archive = archive_buffer.getvalue()

        with tempfile.TemporaryDirectory() as project_dir:
            install_dir = os.path.join(project_dir, ".xray")
            os.makedirs(install_dir)
            target = os.path.join(install_dir, "xray.exe")
            Path(target).write_bytes(b"old xray executable")

            def download(_url, destination, expected_size, expected_digest):
                self.assertEqual(len(archive), expected_size)
                self.assertEqual(hashlib.sha256(archive).hexdigest(), expected_digest)
                Path(destination).write_bytes(archive)

            asset = mock.Mock(
                executable_name="xray.exe",
                size=len(archive),
                sha256=hashlib.sha256(archive).hexdigest(),
                url="https://github.com/XTLS/Xray-core/releases/download/v26.3.27/Xray-windows-64.zip",
            )
            with mock.patch("core.chain_proxy._xray_asset", return_value=asset), mock.patch(
                "core.chain_proxy._download_verified_asset", side_effect=download
            ), mock.patch(
                "core.chain_proxy._validate_xray_binary",
                side_effect=ChainProxyError("identity failed"),
            ):
                with self.assertRaisesRegex(ChainProxyError, "identity failed"):
                    chain_proxy._download_xray(project_dir)
            self.assertEqual(b"old xray executable", Path(target).read_bytes())

            with mock.patch("core.chain_proxy._xray_asset", return_value=asset), mock.patch(
                "core.chain_proxy._download_verified_asset", side_effect=download
            ), mock.patch(
                "core.chain_proxy._validate_xray_binary", side_effect=lambda path: path
            ):
                self.assertEqual(target, chain_proxy._download_xray(project_dir))
            self.assertEqual(executable, Path(target).read_bytes())


class ChainPreflightTests(unittest.TestCase):
    def _write_config(self, directory, **overrides):
        config = {
            "CHAIN_PROXY_TEST_ENABLED": True,
            "CHAIN_PROXY_SUBSCRIPTION_URL": (
                "https://proxy.example.com/sub?token=never-print"
            ),
            "CHAIN_PROXY_CORE_PATH": "",
            "BANDWIDTH_URL_TEMPLATE": (
                "https://speed.cloudflare.com/__down?bytes={bytes}"
            ),
            "FETCH_CONNECT_TIMEOUT": 5,
            "FETCH_TIMEOUT": 10,
            "HTTP_TEST_CONNECT_TIMEOUT": 5,
            "HTTP_TEST_TIMEOUT": 8,
            "BANDWIDTH_PROCESS_BUFFER": 2,
            "UNRELATED": {"preserve": "值"},
        }
        config.update(overrides)
        path = os.path.join(directory, "config.json")
        Path(path).write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def _subscription(self, count=3):
        return "\n".join(
            vless_node(f"198.51.100.{index}") for index in range(10, 10 + count)
        )

    def test_https_probe_uses_a_dedicated_non_speedtest_target(self):
        config = {
            "CHAIN_PROXY_PREFLIGHT_URL": "https://www.cloudflare.com/cdn-cgi/trace",
            "BANDWIDTH_URL_TEMPLATE": (
                "https://speed.cloudflare.com/__down?bytes={bytes}"
            ),
            "HTTP_TEST_CONNECT_TIMEOUT": 5,
            "HTTP_TEST_TIMEOUT": 8,
            "BANDWIDTH_PROCESS_BUFFER": 2,
        }
        completed = subprocess.CompletedProcess([], 0, stdout="204", stderr="")

        with mock.patch("core.chain_proxy.shutil.which", return_value="curl"), mock.patch(
            "core.chain_proxy.subprocess.run", return_value=completed
        ) as run:
            self.assertTrue(chain_proxy._check_socks_https(1080, config))

        command = run.call_args.args[0]
        self.assertEqual("https://www.cloudflare.com/cdn-cgi/trace", command[-1])
        self.assertNotIn("speed.cloudflare.com", " ".join(command))

    def test_https_probe_rejects_unsafe_dedicated_targets_before_curl(self):
        for target in (
            "http://www.cloudflare.com/cdn-cgi/trace",
            "https://user:pass@example.com/health",
            "",
        ):
            with self.subTest(target=target), mock.patch(
                "core.chain_proxy.shutil.which", return_value="curl"
            ), mock.patch(
                "core.chain_proxy.subprocess.run"
            ) as run, self.assertRaises(ChainProxyError) as raised:
                chain_proxy._check_socks_https(
                    1080,
                    {"CHAIN_PROXY_PREFLIGHT_URL": target},
                )

            self.assertEqual("ENVIRONMENT_ERROR", raised.exception.category)
            run.assert_not_called()

    def test_disabled_preflight_has_zero_subscription_or_xray_work(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = self._write_config(
                directory, CHAIN_PROXY_TEST_ENABLED=False
            )
            with mock.patch(
                "core.chain_proxy._fetch_chain_subscription"
            ) as fetch, mock.patch(
                "core.chain_proxy.resolve_xray_path"
            ) as resolve:
                result = chain_proxy.preflight_chain_proxy(config_path)

        self.assertIsNone(result)
        fetch.assert_not_called()
        resolve.assert_not_called()

    def test_preflight_requires_a_json_boolean_before_other_work(self):
        for value in ("true", 1, None):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                config_path = self._write_config(
                    directory, CHAIN_PROXY_TEST_ENABLED=value
                )
                with mock.patch(
                    "core.chain_proxy._fetch_chain_subscription"
                ) as fetch, self.assertRaises(ChainProxyError) as raised:
                    chain_proxy.preflight_chain_proxy(config_path)

                self.assertEqual("ENVIRONMENT_ERROR", raised.exception.category)
                fetch.assert_not_called()

    def test_preflight_rejects_unsafe_subscription_urls_before_fetch(self):
        for url in (
            "http://proxy.example.com/sub?token=secret",
            "https://user:pass@proxy.example.com/sub?token=secret",
            "",
        ):
            with self.subTest(url=url), tempfile.TemporaryDirectory() as directory:
                config_path = self._write_config(
                    directory, CHAIN_PROXY_SUBSCRIPTION_URL=url
                )
                with mock.patch(
                    "core.chain_proxy._fetch_chain_subscription"
                ) as fetch, self.assertRaises(ChainProxyError) as raised:
                    chain_proxy.preflight_chain_proxy(config_path)

                self.assertEqual("SUBSCRIPTION_ERROR", raised.exception.category)
                self.assertNotIn("secret", str(raised.exception))
                fetch.assert_not_called()

    def test_preflight_fetches_once_and_accepts_the_second_endpoint(self):
        attempts = []

        class Runtime:
            def __init__(self, _core_path, _template, candidates):
                attempts.append(candidates[0])
                self.proxy_ports = {candidates[0]: 19000 + len(attempts)}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

        with tempfile.TemporaryDirectory() as directory:
            config_path = self._write_config(directory)
            core_path = os.path.join(directory, ".xray", "xray.exe")
            with mock.patch(
                "core.chain_proxy._fetch_chain_subscription",
                return_value=self._subscription(),
            ) as fetch, mock.patch(
                "core.chain_proxy.resolve_xray_path", return_value=core_path
            ), mock.patch(
                "core.chain_proxy.XrayRuntime", Runtime
            ), mock.patch(
                "core.chain_proxy._check_socks_https",
                side_effect=[False, True],
            ) as check:
                result = chain_proxy.preflight_chain_proxy(config_path)

        fetch.assert_called_once()
        self.assertEqual(
            ["198.51.100.10:443", "198.51.100.11:443"],
            attempts,
        )
        self.assertEqual(2, check.call_count)
        self.assertEqual(2, result.attempted_endpoints)
        self.assertEqual(
            chain_proxy.ChainEndpoint("198.51.100.11", 443),
            result.successful_endpoint,
        )
        self.assertEqual(core_path, result.core_path)
        self.assertNotIn(UUID, repr(result))
        self.assertNotIn("never-print", repr(result))

    def test_preflight_preserves_each_randomized_cdn_host_with_its_endpoint(self):
        attempts = []

        class Runtime:
            def __init__(self, _core_path, template, candidates):
                attempts.append((template.server_name, candidates[0]))
                self.proxy_ports = {candidates[0]: 19000 + len(attempts)}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

        subscription = "\n".join(
            [
                vless_node("198.51.100.10", domain="edge-one.example.net"),
                vless_node("198.51.100.11", domain="edge-two.example.net"),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            config_path = self._write_config(directory)
            with mock.patch(
                "core.chain_proxy._fetch_chain_subscription",
                return_value=subscription,
            ) as fetch, mock.patch(
                "core.chain_proxy.resolve_xray_path", return_value="xray"
            ), mock.patch(
                "core.chain_proxy.XrayRuntime", Runtime
            ), mock.patch(
                "core.chain_proxy._check_socks_https",
                side_effect=[False, True],
            ):
                result = chain_proxy.preflight_chain_proxy(config_path)

        fetch.assert_called_once()
        self.assertEqual(
            [
                ("edge-one.example.net", "198.51.100.10:443"),
                ("edge-two.example.net", "198.51.100.11:443"),
            ],
            attempts,
        )
        self.assertEqual("edge-two.example.net", result.template.server_name)

    def test_preflight_tries_at_most_three_and_classifies_connectivity_failure(self):
        attempts = []

        class Runtime:
            def __init__(self, _core_path, _template, candidates):
                attempts.append(candidates[0])
                self.proxy_ports = {candidates[0]: 19000 + len(attempts)}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

        with tempfile.TemporaryDirectory() as directory:
            config_path = self._write_config(directory)
            with mock.patch(
                "core.chain_proxy._fetch_chain_subscription",
                return_value=self._subscription(4),
            ), mock.patch(
                "core.chain_proxy.resolve_xray_path", return_value="xray"
            ), mock.patch(
                "core.chain_proxy.XrayRuntime", Runtime
            ), mock.patch(
                "core.chain_proxy._check_socks_https", return_value=False
            ) as check, self.assertRaises(ChainProxyError) as raised:
                chain_proxy.preflight_chain_proxy(config_path)

        self.assertEqual("CONNECTIVITY_ERROR", raised.exception.category)
        self.assertEqual(3, len(attempts))
        self.assertEqual(3, check.call_count)
        self.assertNotIn("never-print", str(raised.exception))

    def test_preflight_classifies_xray_start_failure_as_core_error(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = self._write_config(directory)
            with mock.patch(
                "core.chain_proxy._fetch_chain_subscription",
                return_value=self._subscription(1),
            ), mock.patch(
                "core.chain_proxy.resolve_xray_path", return_value="xray"
            ), mock.patch(
                "core.chain_proxy.XrayRuntime",
                side_effect=ChainProxyError("invalid config"),
            ), self.assertRaises(ChainProxyError) as raised:
                chain_proxy.preflight_chain_proxy(config_path)

        self.assertEqual("CORE_ERROR", raised.exception.category)
        self.assertNotIn(UUID, str(raised.exception))

    def test_successful_preflight_migrates_only_a_nonempty_stale_core_path_once(self):
        class Runtime:
            def __init__(self, _core_path, _template, candidates):
                self.proxy_ports = {candidates[0]: 19090}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

        with tempfile.TemporaryDirectory() as directory:
            old_core = os.path.join(directory, ".sing-box", "sing-box.exe")
            os.makedirs(os.path.dirname(old_core))
            Path(old_core).write_bytes(b"legacy-unchanged")
            config_path = self._write_config(
                directory, CHAIN_PROXY_CORE_PATH=".sing-box/sing-box.exe"
            )
            xray_path = os.path.join(directory, ".xray", "xray.exe")
            common = (
                mock.patch(
                    "core.chain_proxy._fetch_chain_subscription",
                    return_value=self._subscription(1),
                ),
                mock.patch(
                    "core.chain_proxy.resolve_xray_path", return_value=xray_path
                ),
                mock.patch("core.chain_proxy.XrayRuntime", Runtime),
                mock.patch(
                    "core.chain_proxy._check_socks_https", return_value=True
                ),
            )
            with common[0], common[1], common[2], common[3]:
                chain_proxy.preflight_chain_proxy(config_path)

            migrated = json.loads(Path(config_path).read_text(encoding="utf-8"))
            self.assertEqual(".xray/xray.exe", migrated["CHAIN_PROXY_CORE_PATH"])
            self.assertEqual({"preserve": "值"}, migrated["UNRELATED"])
            self.assertEqual(b"legacy-unchanged", Path(old_core).read_bytes())

            with mock.patch(
                "core.chain_proxy._fetch_chain_subscription",
                return_value=self._subscription(1),
            ), mock.patch(
                "core.chain_proxy.resolve_xray_path", return_value=xray_path
            ), mock.patch(
                "core.chain_proxy.XrayRuntime", Runtime
            ), mock.patch(
                "core.chain_proxy._check_socks_https", return_value=True
            ), mock.patch(
                "core.chain_proxy._atomic_write_config"
            ) as write:
                chain_proxy.preflight_chain_proxy(config_path)
            write.assert_not_called()

    def test_cli_returns_nonzero_with_stable_category_and_no_secret(self):
        error = ChainProxyError(
            "订阅请求失败",
            category="SUBSCRIPTION_ERROR",
            recovery="检查订阅配置",
        )
        stderr = io.StringIO()
        with mock.patch(
            "core.chain_proxy.preflight_chain_proxy", side_effect=error
        ), mock.patch("sys.stderr", stderr):
            exit_code = chain_proxy.main(
                ["preflight", "--config", "config.json"]
            )

        self.assertEqual(1, exit_code)
        self.assertIn("SUBSCRIPTION_ERROR", stderr.getvalue())
        self.assertNotIn("never-print", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
