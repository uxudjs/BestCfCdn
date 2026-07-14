import unittest

from proxy_scoring import (
    rank_proxy_candidates,
    select_proxy_candidates,
    summarize_latency_samples,
)


def metrics_config(**overrides):
    config = {
        "PROXY_SCORE_BANDWIDTH_WEIGHT": 0.30,
        "PROXY_SCORE_HTTP_LATENCY_WEIGHT": 0.40,
        "PROXY_SCORE_JITTER_WEIGHT": 0.20,
        "PROXY_SCORE_TCP_LATENCY_WEIGHT": 0.10,
        "PROXY_SPEED_SCALE_MBPS": 40,
        "PROXY_HTTP_LATENCY_REFERENCE_MS": 180,
        "PROXY_JITTER_REFERENCE_MS": 50,
        "PROXY_TCP_LATENCY_REFERENCE_MS": 180,
        "PROXY_MIN_BANDWIDTH_MBPS": 8,
        "PROXY_MAX_HTTP_LATENCY_MS": 600,
        "PROXY_MAX_HTTP_JITTER_MS": 200,
        "PROXY_MAX_TCP_LATENCY_MS": 600,
    }
    config.update(overrides)
    return config


class ProxyScoringTests(unittest.TestCase):
    def test_latency_summary_uses_median_and_tail_jitter(self):
        median, jitter = summarize_latency_samples([10, 20, 30, 40, 200])
        self.assertEqual(30, median)
        self.assertEqual(170, jitter)

    def test_responsive_node_beats_raw_bandwidth_node(self):
        bandwidth = [("fast", 200), ("responsive", 30)]
        tcp = {"fast": 0.2, "responsive": 0.05}
        http = {"fast": 300, "responsive": 80}
        jitter = {"fast": 80, "responsive": 15}

        ranked = rank_proxy_candidates(bandwidth, tcp, http, jitter, metrics_config())

        self.assertEqual("responsive", ranked[0].node)
        self.assertGreater(ranked[0].score, ranked[1].score)

    def test_bandwidth_weight_can_change_ranking(self):
        bandwidth = [("fast", 150), ("responsive", 30)]
        tcp = {"fast": 0.1, "responsive": 0.04}
        http = {"fast": 300, "responsive": 40}
        jitter = {"fast": 40, "responsive": 5}
        latency_first = rank_proxy_candidates(
            bandwidth, tcp, http, jitter, metrics_config()
        )
        bandwidth_first = rank_proxy_candidates(
            bandwidth,
            tcp,
            http,
            jitter,
            metrics_config(
                PROXY_SCORE_BANDWIDTH_WEIGHT=0.80,
                PROXY_SCORE_HTTP_LATENCY_WEIGHT=0.10,
                PROXY_SCORE_JITTER_WEIGHT=0.05,
                PROXY_SCORE_TCP_LATENCY_WEIGHT=0.05,
            ),
        )

        self.assertEqual("responsive", latency_first[0].node)
        self.assertEqual("fast", bandwidth_first[0].node)

    def test_bandwidth_has_diminishing_returns(self):
        config = metrics_config()
        ranked = rank_proxy_candidates(
            [("10", 10), ("50", 50), ("100", 100), ("200", 200)],
            {},
            {},
            {},
            config,
        )
        score = {item.node: item.score for item in ranked}
        self.assertGreater(score["50"] - score["10"], score["200"] - score["100"])

    def test_quality_floor_precedes_higher_scoring_unqualified_node(self):
        ranked = rank_proxy_candidates(
            [("qualified", 20), ("too_slow", 7)],
            {"qualified": 0.15, "too_slow": 0.01},
            {"qualified": 250, "too_slow": 5},
            {"qualified": 50, "too_slow": 1},
            metrics_config(),
        )
        self.assertTrue(ranked[0].qualified)
        self.assertEqual("qualified", ranked[0].node)
        self.assertFalse(ranked[1].qualified)

    def test_missing_http_metrics_redistribute_weights(self):
        ranked = rank_proxy_candidates(
            [("lower_tcp", 20), ("higher_tcp", 20)],
            {"lower_tcp": 0.03, "higher_tcp": 0.3},
            {},
            {},
            metrics_config(),
        )
        self.assertEqual("lower_tcp", ranked[0].node)
        self.assertGreater(ranked[0].score, ranked[1].score)

    def test_ties_are_deterministic(self):
        ranked = rank_proxy_candidates(
            [("b", 20), ("a", 20)], {}, {}, {}, metrics_config()
        )
        self.assertEqual(["a", "b"], [item.node for item in ranked])

    def test_per_country_quota_preserves_qualified_first_order(self):
        ranked = rank_proxy_candidates(
            [("a:443#US", 20), ("b:443#JP", 7), ("c:443#US", 30)],
            {
                "a:443#US": 0.1,
                "b:443#JP": 0.05,
                "c:443#US": 0.08,
            },
            {
                "a:443#US": 100,
                "b:443#JP": 80,
                "c:443#US": 90,
            },
            {
                "a:443#US": 10,
                "b:443#JP": 10,
                "c:443#US": 10,
            },
            metrics_config(),
        )

        selected = select_proxy_candidates(
            ranked,
            use_global_mode=False,
            global_top_n=5,
            per_country_top_n=1,
        )

        self.assertEqual(["c:443#US", "b:443#JP"], [item.node for item in selected])
        self.assertTrue(selected[0].qualified)
        self.assertFalse(selected[1].qualified)


if __name__ == "__main__":
    unittest.main()
