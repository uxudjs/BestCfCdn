import base64
import json
import unittest
from urllib.parse import urlencode

from chain_proxy import (
    ChainProxyError,
    build_sing_box_config,
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
    return f"vless://{UUID}@{server}:443?{urlencode(query)}#{server}"


class ChainProxyTests(unittest.TestCase):
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

    def test_ech_fragment_and_fingerprint_map_to_sing_box(self):
        template = extract_chain_template(
            vless_node(
                "198.51.100.10",
                extra={
                    "ech": "ech.example+https://doh.example/dns-query",
                    "fragment": "1,40-60,30-50,tlshello",
                    "fp": "chrome",
                },
            ),
            f"https://{DOMAIN}/subscribe",
        )

        config = build_sing_box_config(template, {"198.51.100.10:443": 19090})
        tls = config["outbounds"][0]["tls"]
        self.assertEqual(tls["ech"], {"enabled": True, "query_server_name": "ech.example"})
        self.assertTrue(tls["fragment"])
        self.assertEqual(tls["utls"], {"enabled": True, "fingerprint": "chrome"})
        self.assertEqual(config["dns"]["final"], "chain-ech-doh")
        self.assertEqual(config["dns"]["servers"][1]["path"], "/dns-query")

    def test_ech_without_an_explicit_query_name_uses_the_tls_name(self):
        template = extract_chain_template(
            vless_node(
                "198.51.100.14",
                extra={"ech": "https://doh.example/dns-query", "fragment": "3,1,tlshello"},
            ),
            f"https://{DOMAIN}/subscribe",
        )

        tls = build_sing_box_config(template, {"198.51.100.14:443": 19090})[
            "outbounds"
        ][0]["tls"]
        self.assertEqual(tls["ech"], {"enabled": True})
        self.assertTrue(tls["fragment"])

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

        config = build_sing_box_config(template, {"198.51.100.11:443": 19090})
        self.assertEqual(
            config["outbounds"][0]["transport"],
            {"type": "grpc", "service_name": service_name},
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

    def test_xhttp_template_is_rejected_with_an_actionable_error(self):
        with self.assertRaisesRegex(ChainProxyError, "XHTTP"):
            extract_chain_template(
                vless_node(
                    "198.51.100.13",
                    extra={"type": "xhttp", "mode": "stream-one"},
                ),
                f"https://{DOMAIN}/subscribe",
            )


if __name__ == "__main__":
    unittest.main()
