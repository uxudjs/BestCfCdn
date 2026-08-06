import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from core import app as main


class MeasurementFlowTests(unittest.TestCase):
    @staticmethod
    def bandwidth_stdout(
        *, http_code=200, http_version="1.1", size=2097152,
        time_starttransfer=0.2, time_total=2.2
    ):
        return (
            f"{main._BANDWIDTH_WRITE_OUT_MARKER}{http_code}\t{http_version}\t"
            f"{size}\t{time_starttransfer}\t{time_total}\n"
        )

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
                "core.app.subprocess.Popen", return_value=process
            ) as popen, mock.patch("core.app.send_wxpusher_notification"):
                main.sync_to_github()

        command = popen.call_args.args[0]
        options = popen.call_args.kwargs
        self.assertEqual(["-X", "utf8"], command[1:3])
        self.assertEqual(["-m", "core.github_sync"], command[3:5])
        self.assertEqual("utf-8", options["encoding"])
        self.assertEqual("replace", options["errors"])
        self.assertTrue(options["text"])
        self.assertEqual("1", options["env"]["PYTHONUTF8"])
        self.assertEqual("utf-8", options["env"]["PYTHONIOENCODING"])
        self.assertEqual(main.os.path.dirname(main.CONFIG_FILE), options["cwd"])
        process.communicate.assert_called_once_with(timeout=10)

    def test_tcp_latency_uses_median_successful_probe(self):
        socket_instance = mock.MagicMock()
        socket_context = mock.MagicMock()
        socket_context.__enter__.return_value = socket_instance
        socket_context.__exit__.return_value = False

        with mock.patch("core.app.socket.socket", return_value=socket_context), mock.patch(
            "core.app.time.perf_counter",
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
            "core.app.requests.head", side_effect=request_results
        ) as request:
            with mock.patch(
                "core.app.time.perf_counter",
                side_effect=[0, 1, 2, 2.1, 3, 3.1, 4, 4.1, 5, 5.1],
            ), mock.patch("core.app.time.sleep"):
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

    def test_chain_http_accepts_two_successes_out_of_three(self):
        def chain_stdout(code, start):
            return f"{main._CHAIN_WRITE_OUT_MARKER}{code}\t{start}\t{start + 0.1}\n"

        completed = [
            subprocess.CompletedProcess([], 0, stdout=chain_stdout(200, 0.3), stderr=""),
            subprocess.CompletedProcess([], 7, stdout="", stderr="failed to connect"),
            subprocess.CompletedProcess([], 0, stdout=chain_stdout(200, 0.5), stderr=""),
        ]
        with mock.patch.multiple(
            main,
            CHAIN_PROXY_MIN_SUCCESS_RATE=0.66,
            HTTP_TEST_CONNECT_TIMEOUT=1,
            HTTP_TEST_TIMEOUT=2,
            BANDWIDTH_PROCESS_BUFFER=1,
        ), mock.patch("core.app.subprocess.run", side_effect=completed) as run:
            node, valid, _, latency, jitter, success_rate = main.measure_chain_http(
                "104.16.0.1:443#US", 31001, "curl.exe", samples=3
            )

        self.assertEqual("104.16.0.1:443#US", node)
        self.assertTrue(valid)
        self.assertAlmostEqual(2 / 3, success_rate)
        self.assertAlmostEqual(400, latency)
        self.assertAlmostEqual(100, jitter)
        command = run.call_args.args[0]
        self.assertEqual(
            "socks5h://127.0.0.1:31001",
            command[command.index("--proxy") + 1],
        )
        self.assertEqual("", command[command.index("--noproxy") + 1])
        self.assertNotIn("--connect-to", command)

    def test_bandwidth_curl_automatically_negotiates_http_version(self):
        def fake_run(command, **kwargs):
            if any(flag in command for flag in ("--http2", "--http1.1", "--http3")):
                return subprocess.CompletedProcess(
                    command,
                    2,
                    stdout="",
                    stderr="installed libcurl version does not support this",
                )
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=self.bandwidth_stdout(),
                stderr="",
            )

        with mock.patch("core.app.subprocess.run", side_effect=fake_run) as run:
            result = main.measure_bandwidth_curl(
                "104.16.0.1:443#US", curl_path="curl.exe"
            )

        self.assertTrue(result.valid)
        command = run.call_args.args[0]
        self.assertFalse(
            any(flag in command for flag in ("--http2", "--http1.1", "--http3"))
        )
        self.assertIn("--show-error", command)
        self.assertNotIn("--insecure", command)
        self.assertEqual("utf-8", run.call_args.kwargs["encoding"])
        self.assertEqual("replace", run.call_args.kwargs["errors"])

    def test_bandwidth_curl_maps_nonstandard_candidate_port(self):
        completed = subprocess.CompletedProcess(
            [], 0, stdout=self.bandwidth_stdout(), stderr=""
        )
        with mock.patch("core.app.subprocess.run", return_value=completed) as run:
            result = main.measure_bandwidth_curl(
                "104.16.0.1:8443#US", curl_path="curl.exe"
            )

        self.assertTrue(result.valid)
        command = run.call_args.args[0]
        connect_to = command[command.index("--connect-to") + 1]
        self.assertEqual("speed.cloudflare.com:443:104.16.0.1:8443", connect_to)

    def test_bandwidth_curl_uses_chain_proxy_without_direct_override(self):
        completed = subprocess.CompletedProcess(
            [], 0, stdout=self.bandwidth_stdout(), stderr=""
        )
        with mock.patch("core.app.subprocess.run", return_value=completed) as run:
            result = main.measure_bandwidth_curl(
                "104.16.0.1:443#US",
                curl_path="curl.exe",
                proxy_url="socks5h://127.0.0.1:31001",
            )

        self.assertTrue(result.valid)
        command = run.call_args.args[0]
        self.assertEqual(
            "socks5h://127.0.0.1:31001",
            command[command.index("--proxy") + 1],
        )
        self.assertEqual("", command[command.index("--noproxy") + 1])
        self.assertNotIn("--connect-to", command)

    def test_bandwidth_timeout_with_useful_partial_sample_is_valid(self):
        completed = subprocess.CompletedProcess(
            [],
            28,
            stdout=self.bandwidth_stdout(size=524288, time_total=8.0),
            stderr="operation timed out",
        )
        with mock.patch("core.app.subprocess.run", return_value=completed):
            result = main.measure_bandwidth_curl(
                "104.16.0.1:443#US", curl_path="curl.exe"
            )

        self.assertTrue(result.valid)
        self.assertTrue(result.partial)
        self.assertGreater(result.speed_mbps, 0)

    def test_bandwidth_timeout_with_tiny_sample_is_rejected(self):
        completed = subprocess.CompletedProcess(
            [],
            28,
            stdout=self.bandwidth_stdout(size=65536, time_total=8.0),
            stderr="operation timed out",
        )
        with mock.patch("core.app.subprocess.run", return_value=completed):
            result = main.measure_bandwidth_curl(
                "104.16.0.1:443#US", curl_path="curl.exe"
            )

        self.assertFalse(result.valid)
        self.assertTrue(result.retryable)
        self.assertIn("curl 28", result.reason)

    def test_bandwidth_partial_threshold_is_not_silently_lowered(self):
        completed = subprocess.CompletedProcess(
            [],
            28,
            stdout=self.bandwidth_stdout(size=1048576, time_total=8.0),
            stderr="operation timed out",
        )
        with mock.patch.multiple(
            main, BANDWIDTH_MIN_PARTIAL_MB=3.0
        ), mock.patch("core.app.subprocess.run", return_value=completed):
            result = main.measure_bandwidth_curl(
                "104.16.0.1:443#US", curl_path="curl.exe"
            )

        self.assertFalse(result.valid)
        self.assertIn("curl 28", result.reason)

    def test_bandwidth_http_error_body_is_never_measured(self):
        completed = subprocess.CompletedProcess(
            [],
            0,
            stdout=self.bandwidth_stdout(http_code=503),
            stderr="",
        )
        with mock.patch("core.app.subprocess.run", return_value=completed):
            result = main.measure_bandwidth_curl(
                "104.16.0.1:443#US", curl_path="curl.exe"
            )

        self.assertFalse(result.valid)
        self.assertEqual("HTTP 503", result.reason)
        self.assertTrue(result.retryable)

    def test_bandwidth_cloudflare_5xx_is_retryable(self):
        completed = subprocess.CompletedProcess(
            [],
            0,
            stdout=self.bandwidth_stdout(http_code=522),
            stderr="",
        )
        with mock.patch("core.app.subprocess.run", return_value=completed):
            result = main.measure_bandwidth_curl(
                "104.16.0.1:443#US", curl_path="curl.exe"
            )

        self.assertFalse(result.valid)
        self.assertEqual("HTTP 522", result.reason)
        self.assertTrue(result.retryable)

    def test_bandwidth_connection_error_uses_curl_reason_and_can_retry(self):
        completed = subprocess.CompletedProcess(
            [],
            7,
            stdout=self.bandwidth_stdout(
                http_code=0, size=0, time_starttransfer=0, time_total=5
            ),
            stderr="failed to connect",
        )
        with mock.patch("core.app.subprocess.run", return_value=completed):
            result = main.measure_bandwidth_curl(
                "104.16.0.1:443#US", curl_path="curl.exe"
            )

        self.assertFalse(result.valid)
        self.assertEqual("连接失败（curl 7）", result.reason)
        self.assertTrue(result.retryable)

    def test_bandwidth_process_timeout_is_reported(self):
        with mock.patch(
            "core.app.subprocess.run",
            side_effect=subprocess.TimeoutExpired("curl", 10),
        ):
            result = main.measure_bandwidth_curl(
                "104.16.0.1:443#US", curl_path="curl.exe"
            )

        self.assertFalse(result.valid)
        self.assertEqual("curl 子进程超时", result.reason)
        self.assertTrue(result.retryable)

    def test_bandwidth_filter_aggregates_failure_reasons(self):
        candidates = [
            "104.16.0.1:443#US",
            "104.16.0.2:443#US",
            "104.16.0.3:443#US",
        ]

        def fake_measure(node, curl_path, target, settings):
            if node.endswith("1:443#US"):
                return main.BandwidthMeasurement(node=node, speed_mbps=20.0)
            return main._failed_bandwidth_measurement(
                node, "HTTP 503", retryable=True, http_code=503
            )

        output = io.StringIO()
        with mock.patch("core.app.shutil.which", return_value="curl.exe"), mock.patch(
            "core.app.measure_bandwidth_curl", side_effect=fake_measure
        ), redirect_stdout(output):
            measurements = main.bandwidth_filter(candidates)

        self.assertEqual(1, sum(item.valid for item in measurements))
        self.assertIn("HTTP 503 ×2", output.getvalue())
        self.assertIn("本轮有效结果：1/3", output.getvalue())

    def test_bandwidth_retry_keeps_successes_and_retests_only_transient_failures(self):
        node_a = "104.16.0.1:443#US"
        node_b = "104.16.0.2:443#US"
        node_c = "104.16.0.3:443#US"

        def fake_filter(candidates):
            if candidates == [node_a, node_b, node_c]:
                return [
                    main.BandwidthMeasurement(node=node_a, speed_mbps=30.0),
                    main._failed_bandwidth_measurement(
                        node_b, "连接失败（curl 7）", retryable=True
                    ),
                    main._failed_bandwidth_measurement(
                        node_c, "TLS 证书校验失败（curl 60）"
                    ),
                ]
            self.assertEqual([node_b], candidates)
            return [main.BandwidthMeasurement(node=node_b, speed_mbps=20.0)]

        with mock.patch.multiple(
            main, BANDWIDTH_RETRY_MAX=2, BANDWIDTH_RETRY_DELAY=0
        ), mock.patch(
            "core.app.bandwidth_filter", side_effect=fake_filter
        ) as bandwidth_filter, mock.patch("core.app.time.sleep") as sleep:
            results, failures, rounds = main.bandwidth_filter_with_retry(
                [node_a, node_b, node_c]
            )

        self.assertEqual([(node_a, 30.0), (node_b, 20.0)], results)
        self.assertEqual([node_c], list(failures))
        self.assertEqual(2, rounds)
        self.assertEqual(2, bandwidth_filter.call_count)
        sleep.assert_called_once_with(0)

    def test_bandwidth_nonretryable_failure_stops_after_actual_first_round(self):
        node = "104.16.0.1:443#US"
        failure = main._failed_bandwidth_measurement(
            node, "TLS 证书校验失败（curl 60）"
        )
        with mock.patch.multiple(
            main, BANDWIDTH_RETRY_MAX=2, BANDWIDTH_RETRY_DELAY=0
        ), mock.patch(
            "core.app.bandwidth_filter", return_value=[failure]
        ) as bandwidth_filter, mock.patch("core.app.time.sleep") as sleep:
            results, failures, rounds = main.bandwidth_filter_with_retry([node])

        self.assertEqual([], results)
        self.assertEqual([node], list(failures))
        self.assertEqual(1, rounds)
        bandwidth_filter.assert_called_once_with([node])
        sleep.assert_not_called()

    def test_availability_all_failures_do_not_restore_unverified_candidates(self):
        candidates = ["104.16.0.1:443#US"]
        with mock.patch.multiple(
            main,
            TEST_AVAILABILITY=True,
            AVAILABILITY_RETRY_MAX=2,
            AVAILABILITY_RETRY_DELAY=0,
        ), mock.patch(
            "core.app.availability_filter_candidates", return_value=([], {}, {})
        ), mock.patch("core.app.time.sleep"), mock.patch(
            "core.app.send_wxpusher_notification"
        ):
            passed, ip_info, exit_details = main.availability_filter_with_retry(
                candidates
            )

        self.assertEqual([], passed)
        self.assertEqual({}, ip_info)
        self.assertEqual({}, exit_details)

    def test_http_all_failures_do_not_restore_unverified_candidates(self):
        candidates = ["104.16.0.1:443#US"]
        settings = {
            "HTTP_TEST_MAX_ROUNDS": 2,
            "HTTP_TEST_ROUND_DELAY": 0,
            "HTTP_TEST_WORKERS": 1,
        }
        with mock.patch.multiple(main, **settings), mock.patch(
            "core.app.check_http_server",
            return_value=(candidates[0], False, "invalid", 0.0, 0.0),
        ), mock.patch("core.app.time.sleep"), mock.patch(
            "core.app.send_wxpusher_notification"
        ):
            passed, latency_map, jitter_map = main.http_server_filter(
                candidates, {"HTTP_TEST_ENABLED": True}
            )

        self.assertEqual([], passed)
        self.assertEqual({}, latency_map)
        self.assertEqual({}, jitter_map)

    def test_run_stops_before_publish_when_availability_rejects_every_candidate(self):
        node = "104.16.0.1:443#US"
        settings = {
            "ADDITIONAL_SOURCES": [{"enabled": True, "url": "test-source"}],
            "PRE_FILTER_PORT_ENABLED": False,
            "PRE_FILTER_BLOCKED_ENABLED": False,
            "FILTER_COUNTRIES_ENABLED": False,
            "USE_GLOBAL_MODE": True,
            "BANDWIDTH_CANDIDATES": 1,
            "MAX_WORKERS": 1,
            "TEST_AVAILABILITY": True,
            "CHAIN_PROXY_TEST_ENABLED": False,
            "HTTP_TEST_ENABLED": True,
        }
        with mock.patch.multiple(main, **settings), mock.patch(
            "core.app.fetch_additional_source", return_value=[node]
        ), mock.patch("core.app.calibrate_regions"), mock.patch(
            "core.app.test_node", return_value=(node, 0.01, "US", 1.0)
        ), mock.patch(
            "core.app.availability_filter_with_retry", return_value=([], {}, {})
        ), mock.patch("core.app.http_server_filter") as http_filter, mock.patch(
            "core.app.write_ip_txt"
        ) as write_output, mock.patch(
            "core.app.batch_update_cloudflare_dns"
        ) as update_dns, mock.patch("core.app.sync_to_github") as sync_github:
            with self.assertRaises(SystemExit) as caught:
                main._run()

        self.assertEqual(1, caught.exception.code)
        http_filter.assert_not_called()
        write_output.assert_not_called()
        update_dns.assert_not_called()
        sync_github.assert_not_called()

    def test_chain_preflight_failure_stops_before_candidates_tcp_and_outputs(self):
        error = main.ChainProxyError(
            "真实代理连接失败",
            category="CONNECTIVITY_ERROR",
        )
        settings = {
            "CHAIN_PROXY_TEST_ENABLED": True,
            "ADDITIONAL_SOURCES": [{"enabled": True, "url": "test-source"}],
        }
        with mock.patch.multiple(main, **settings), mock.patch(
            "core.app.preflight_chain_proxy", side_effect=error
        ) as preflight, mock.patch(
            "core.app.fetch_additional_source"
        ) as fetch, mock.patch(
            "core.app.calibrate_regions"
        ) as calibrate, mock.patch(
            "core.app.test_node"
        ) as tcp, mock.patch(
            "core.app.write_ip_txt"
        ) as write_output, mock.patch(
            "core.app.batch_update_cloudflare_dns"
        ) as update_dns, mock.patch(
            "core.app.sync_to_github"
        ) as sync_github, mock.patch(
            "core.app.send_wxpusher_notification"
        ):
            with self.assertRaises(SystemExit) as caught:
                main._run()

        self.assertEqual(1, caught.exception.code)
        preflight.assert_called_once_with(main.CONFIG_FILE)
        fetch.assert_not_called()
        calibrate.assert_not_called()
        tcp.assert_not_called()
        write_output.assert_not_called()
        update_dns.assert_not_called()
        sync_github.assert_not_called()

    def test_direct_mode_with_missing_config_skips_disk_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            missing_config = main.os.path.join(directory, "config.json")
            settings = {
                "CONFIG_FILE": missing_config,
                "CHAIN_PROXY_TEST_ENABLED": False,
                "ADDITIONAL_SOURCES": [],
            }
            with mock.patch.multiple(main, **settings), mock.patch(
                "core.app.preflight_chain_proxy",
                side_effect=AssertionError("disabled direct mode touched preflight"),
            ) as preflight:
                with self.assertRaises(SystemExit) as caught:
                    main._run()

        self.assertEqual(1, caught.exception.code)
        preflight.assert_not_called()

    def test_chain_measurement_reuses_preflight_template_and_core(self):
        node = "104.16.0.1:443#US"
        template = object()
        preflight_result = mock.Mock(template=template, core_path="xray.exe")
        settings = {
            "CHAIN_PROXY_TEST_ENABLED": True,
            "ADDITIONAL_SOURCES": [{"enabled": True, "url": "test-source"}],
            "PRE_FILTER_PORT_ENABLED": False,
            "PRE_FILTER_BLOCKED_ENABLED": False,
            "FILTER_COUNTRIES_ENABLED": False,
            "USE_GLOBAL_MODE": True,
            "BANDWIDTH_CANDIDATES": 1,
            "MAX_WORKERS": 1,
        }
        stop = main.ChainProxyError("stop after reuse proof")
        with mock.patch.multiple(main, **settings), mock.patch(
            "core.app.preflight_chain_proxy", return_value=preflight_result
        ) as preflight, mock.patch(
            "core.app.fetch_additional_source", return_value=[node]
        ), mock.patch(
            "core.app.calibrate_regions"
        ), mock.patch(
            "core.app.test_node", return_value=(node, 0.01, "US", 1.0)
        ), mock.patch(
            "core.app.XrayRuntime", side_effect=stop
        ) as runtime, mock.patch(
            "core.app.fetch_chain_template", create=True
        ) as legacy_fetch, mock.patch(
            "core.app.resolve_xray_path", create=True
        ) as legacy_resolve, mock.patch(
            "core.app.send_wxpusher_notification"
        ):
            with self.assertRaises(SystemExit) as caught:
                main._run()

        self.assertEqual(1, caught.exception.code)
        preflight.assert_called_once_with(main.CONFIG_FILE)
        runtime.assert_called_once_with(
            "xray.exe",
            template,
            [node],
        )
        legacy_fetch.assert_not_called()
        legacy_resolve.assert_not_called()

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
            with mock.patch("core.app.requests.get", return_value=list_response), mock.patch(
                "core.app.requests.post", return_value=batch_response
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

    def test_dns_risk_filter_all_failures_preserve_existing_records(self):
        settings = {
            "CF_ENABLED": True,
            "DNS_RECORD_TYPE": "A",
            "FILTER_IPV6_AVAILABILITY": False,
            "FILTER_BLOCKED_COUNTRIES_ENABLED": False,
            "DNS_IP_RISK_FILTER_ENABLED": True,
            "DNS_IP_RISK_MAX_LEVEL": "低风险",
        }
        ranked = [("104.16.0.1:443#US", 100)]

        with mock.patch.multiple(main, **settings), mock.patch(
            "core.app.get_ip_risk_level", return_value="未知"
        ), mock.patch("core.app.requests.get") as get, mock.patch(
            "core.app.requests.post"
        ) as post, mock.patch("core.app.send_wxpusher_notification"):
            main.batch_update_cloudflare_dns(
                ["104.16.0.1"], full_bw_results=ranked, target_count=1
            )

        get.assert_not_called()
        post.assert_not_called()

    def test_dns_ranked_results_removed_by_filters_do_not_fallback_to_ip_list(self):
        settings = {
            "CF_ENABLED": True,
            "DNS_RECORD_TYPE": "A",
            "FILTER_IPV6_AVAILABILITY": False,
            "FILTER_BLOCKED_COUNTRIES_ENABLED": False,
            "DNS_IP_RISK_FILTER_ENABLED": False,
        }
        ranked = [("104.16.0.1:80#US", 100)]

        with mock.patch.multiple(main, **settings), mock.patch(
            "core.app.requests.get"
        ) as get, mock.patch("core.app.requests.post") as post, mock.patch(
            "core.app.send_wxpusher_notification"
        ):
            main.batch_update_cloudflare_dns(
                ["104.16.0.1"], full_bw_results=ranked, target_count=1
            )

        get.assert_not_called()
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
