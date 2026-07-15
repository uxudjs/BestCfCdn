import unittest
from unittest import mock

import main


class MeasurementFlowTests(unittest.TestCase):
    def test_github_sync_child_process_forces_utf8_and_safe_decoding(self):
        process = mock.MagicMock()
        process.returncode = 1
        process.communicate.return_value = ("", "模拟错误")

        settings = {
            "GITHUB_SYNC_MAX_RETRIES": 1,
            "GIT_SYNC_PROCESS_TIMEOUT": 10,
            "OUTPUT_FILE": "ip.local.txt",
        }
        with mock.patch.dict(
            main.os.environ,
            {"PYTHONUTF8": "0", "PYTHONIOENCODING": "cp950"},
        ):
            with mock.patch.multiple(main, **settings), mock.patch(
                "main.subprocess.Popen", return_value=process
            ) as popen, mock.patch("main.send_wxpusher_notification"):
                main.sync_to_github()

        command = popen.call_args.args[0]
        options = popen.call_args.kwargs
        self.assertEqual(["-X", "utf8"], command[1:3])
        self.assertEqual("utf-8", options["encoding"])
        self.assertEqual("replace", options["errors"])
        self.assertTrue(options["text"])
        self.assertEqual("1", options["env"]["PYTHONUTF8"])
        self.assertEqual("utf-8", options["env"]["PYTHONIOENCODING"])
        process.communicate.assert_called_once_with(timeout=10)

    def test_tcp_latency_uses_median_successful_probe(self):
        socket_instance = mock.MagicMock()
        socket_context = mock.MagicMock()
        socket_context.__enter__.return_value = socket_instance
        socket_context.__exit__.return_value = False

        with mock.patch("main.socket.socket", return_value=socket_context), mock.patch(
            "main.time.perf_counter",
            side_effect=[0.0, 0.1, 1.0, 1.5, 2.0, 2.2],
        ):
            latency, successes = main.test_tcp_latency(
                "127.0.0.1", 443, timeout=1, probes=3
            )

        self.assertEqual(3, successes)
        self.assertAlmostEqual(0.2, latency)

    def test_http_sample_retries_transient_failure(self):
        response = mock.MagicMock()
        response.status_code = 400
        response.headers = {"server": "cloudflare"}
        request_results = [RuntimeError("temporary failure")] + [response] * 5

        with mock.patch(
            "main.requests.head", side_effect=request_results
        ) as request:
            with mock.patch(
                "main.time.perf_counter",
                side_effect=[0, 1, 2, 2.1, 3, 3.1, 4, 4.1, 5, 5.1],
            ), mock.patch("main.time.sleep"):
                node, valid, server, latency, jitter = main.check_http_server(
                    "104.16.0.1:443#US",
                    timeout=1,
                    max_retries=1,
                    retry_delay=0,
                    method="HEAD",
                    connect_timeout=1,
                    inner_retry_enabled=True,
                )

        self.assertEqual("104.16.0.1:443#US", node)
        self.assertTrue(valid)
        self.assertEqual("cloudflare", server)
        self.assertEqual(6, request.call_count)
        self.assertAlmostEqual(100, latency)
        self.assertAlmostEqual(900, jitter)

    def test_dns_per_country_limit_is_applied_after_ranking(self):
        list_response = mock.MagicMock()
        list_response.json.return_value = {"result": []}
        batch_response = mock.MagicMock()
        batch_response.json.return_value = {"success": True}

        settings = {
            "CF_ENABLED": True,
            "DNS_RECORD_TYPE": "TXT",
            "DNS_UPDATE_MAX_RETRIES": 1,
            "FILTER_IPV6_AVAILABILITY": False,
            "FILTER_BLOCKED_COUNTRIES_ENABLED": False,
            "DNS_IP_RISK_FILTER_ENABLED": False,
        }
        ranked = [
            ("104.16.0.1:443#US", 100),
            ("104.16.0.2:443#US", 90),
            ("104.16.0.3:443#JP", 80),
        ]

        with mock.patch.multiple(main, **settings):
            with mock.patch("main.requests.get", return_value=list_response), mock.patch(
                "main.requests.post", return_value=batch_response
            ) as post:
                main.batch_update_cloudflare_dns(
                    [],
                    full_bw_results=ranked,
                    target_count=5,
                    per_country_limit=1,
                )

        payload = post.call_args.kwargs["json"]
        self.assertEqual(
            ["104.16.0.1:443", "104.16.0.3:443"],
            [record["content"] for record in payload["posts"]],
        )


if __name__ == "__main__":
    unittest.main()
