"""Proxy-experience scoring with bandwidth saturation and latency stability."""

import math
import statistics
from dataclasses import dataclass
from typing import Optional


DEFAULTS = {
    "PROXY_SCORE_BANDWIDTH_WEIGHT": 0.30,
    "PROXY_SCORE_HTTP_LATENCY_WEIGHT": 0.40,
    "PROXY_SCORE_JITTER_WEIGHT": 0.20,
    "PROXY_SCORE_TCP_LATENCY_WEIGHT": 0.10,
    "PROXY_SPEED_SCALE_MBPS": 40.0,
    "PROXY_HTTP_LATENCY_REFERENCE_MS": 180.0,
    "PROXY_JITTER_REFERENCE_MS": 50.0,
    "PROXY_TCP_LATENCY_REFERENCE_MS": 180.0,
    "PROXY_MIN_BANDWIDTH_MBPS": 8.0,
    "PROXY_MAX_HTTP_LATENCY_MS": 600.0,
    "PROXY_MAX_HTTP_JITTER_MS": 200.0,
    "PROXY_MAX_TCP_LATENCY_MS": 600.0,
}


@dataclass(frozen=True)
class ProxyScore:
    node: str
    score: float
    qualified: bool
    quality_issues: tuple
    bandwidth_mbps: float
    tcp_latency_ms: Optional[float]
    http_latency_ms: Optional[float]
    http_jitter_ms: Optional[float]


def _finite_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def summarize_latency_samples(samples):
    """Return the median and P90-minus-median tail jitter for valid samples."""
    valid_samples = [
        number
        for number in (_finite_number(value) for value in samples)
        if number is not None
    ]
    if not valid_samples:
        return None, None
    median = statistics.median(valid_samples)
    ordered = sorted(valid_samples)
    p90_index = max(0, math.ceil(len(ordered) * 0.9) - 1)
    return median, max(0.0, ordered[p90_index] - median)


def _setting(config, key, *, positive=False):
    value = _finite_number(config.get(key, DEFAULTS[key]))
    if value is None or (positive and value <= 0):
        requirement = "大于 0" if positive else "大于等于 0"
        raise ValueError(f"{key} 必须是{requirement}的有限数值")
    return value


def _speed_utility(speed_mbps, scale_mbps):
    return -math.expm1(-speed_mbps / scale_mbps)


def _latency_utility(latency_ms, reference_ms):
    ratio = latency_ms / reference_ms
    return 1.0 / (1.0 + ratio * ratio)


def rank_proxy_candidates(
    bandwidth_results,
    tcp_latency_map,
    http_latency_map,
    http_jitter_map,
    config,
):
    """Rank candidates for interactive proxy use; qualified nodes always come first."""
    if not bandwidth_results:
        return []

    weights = {
        "bandwidth": _setting(config, "PROXY_SCORE_BANDWIDTH_WEIGHT"),
        "http_latency": _setting(config, "PROXY_SCORE_HTTP_LATENCY_WEIGHT"),
        "jitter": _setting(config, "PROXY_SCORE_JITTER_WEIGHT"),
        "tcp_latency": _setting(config, "PROXY_SCORE_TCP_LATENCY_WEIGHT"),
    }
    scales = {
        "bandwidth": _setting(config, "PROXY_SPEED_SCALE_MBPS", positive=True),
        "http_latency": _setting(
            config, "PROXY_HTTP_LATENCY_REFERENCE_MS", positive=True
        ),
        "jitter": _setting(config, "PROXY_JITTER_REFERENCE_MS", positive=True),
        "tcp_latency": _setting(
            config, "PROXY_TCP_LATENCY_REFERENCE_MS", positive=True
        ),
    }
    thresholds = {
        "bandwidth": _setting(config, "PROXY_MIN_BANDWIDTH_MBPS"),
        "http_latency": _setting(config, "PROXY_MAX_HTTP_LATENCY_MS"),
        "jitter": _setting(config, "PROXY_MAX_HTTP_JITTER_MS"),
        "tcp_latency": _setting(config, "PROXY_MAX_TCP_LATENCY_MS"),
    }

    raw_metrics = []
    for node, raw_speed in bandwidth_results:
        speed = _finite_number(raw_speed) or 0.0
        tcp_seconds = _finite_number(tcp_latency_map.get(node))
        tcp_ms = tcp_seconds * 1000.0 if tcp_seconds is not None else None
        raw_metrics.append(
            {
                "node": node,
                "bandwidth": speed,
                "http_latency": _finite_number(http_latency_map.get(node)),
                "jitter": _finite_number(http_jitter_map.get(node)),
                "tcp_latency": tcp_ms,
            }
        )

    available = {
        "bandwidth": any(item["bandwidth"] > 0 for item in raw_metrics),
        "http_latency": any(item["http_latency"] is not None for item in raw_metrics),
        "jitter": any(item["jitter"] is not None for item in raw_metrics),
        "tcp_latency": any(item["tcp_latency"] is not None for item in raw_metrics),
    }
    effective_weight = sum(
        weights[name] for name, is_available in available.items() if is_available
    )
    if effective_weight <= 0:
        fallback_weights = {
            name: DEFAULTS[
                {
                    "bandwidth": "PROXY_SCORE_BANDWIDTH_WEIGHT",
                    "http_latency": "PROXY_SCORE_HTTP_LATENCY_WEIGHT",
                    "jitter": "PROXY_SCORE_JITTER_WEIGHT",
                    "tcp_latency": "PROXY_SCORE_TCP_LATENCY_WEIGHT",
                }[name]
            ]
            for name, is_available in available.items()
            if is_available
        }
        weights.update(fallback_weights)
        effective_weight = sum(fallback_weights.values())

    ranked = []
    for metrics in raw_metrics:
        utilities = {
            "bandwidth": _speed_utility(
                metrics["bandwidth"], scales["bandwidth"]
            ),
            "http_latency": (
                _latency_utility(metrics["http_latency"], scales["http_latency"])
                if metrics["http_latency"] is not None
                else 0.0
            ),
            "jitter": (
                _latency_utility(metrics["jitter"], scales["jitter"])
                if metrics["jitter"] is not None
                else 0.0
            ),
            "tcp_latency": (
                _latency_utility(metrics["tcp_latency"], scales["tcp_latency"])
                if metrics["tcp_latency"] is not None
                else 0.0
            ),
        }
        weighted_sum = sum(
            weights[name] * utilities[name]
            for name, is_available in available.items()
            if is_available
        )
        score = 100.0 * weighted_sum / effective_weight if effective_weight else 0.0

        issues = []
        if available["bandwidth"] and metrics["bandwidth"] < thresholds["bandwidth"]:
            issues.append("带宽低于门槛")
        for name, label in (
            ("http_latency", "HTTP延迟超过门槛"),
            ("jitter", "HTTP抖动超过门槛"),
            ("tcp_latency", "TCP延迟超过门槛"),
        ):
            value = metrics[name]
            if available[name] and value is None:
                issues.append(f"缺少{label.split('超过')[0]}指标")
            elif value is not None and thresholds[name] > 0 and value > thresholds[name]:
                issues.append(label)

        ranked.append(
            ProxyScore(
                node=metrics["node"],
                score=score,
                qualified=not issues,
                quality_issues=tuple(issues),
                bandwidth_mbps=metrics["bandwidth"],
                tcp_latency_ms=metrics["tcp_latency"],
                http_latency_ms=metrics["http_latency"],
                http_jitter_ms=metrics["jitter"],
            )
        )

    infinity = float("inf")
    ranked.sort(
        key=lambda item: (
            not item.qualified,
            -item.score,
            item.http_latency_ms if item.http_latency_ms is not None else infinity,
            item.http_jitter_ms if item.http_jitter_ms is not None else infinity,
            -item.bandwidth_mbps,
            item.tcp_latency_ms if item.tcp_latency_ms is not None else infinity,
            item.node,
        )
    )
    return ranked


def select_proxy_candidates(
    ranked_scores,
    *,
    use_global_mode,
    global_top_n,
    per_country_top_n,
):
    """Apply the output quota without losing the qualified-first global order."""
    if use_global_mode:
        return list(ranked_scores[: max(0, int(global_top_n))])

    country_counts = {}
    selected = []
    country_limit = max(0, int(per_country_top_n))
    for item in ranked_scores:
        country = item.node.rsplit("#", 1)[-1] if "#" in item.node else ""
        if not country or country_counts.get(country, 0) >= country_limit:
            continue
        selected.append(item)
        country_counts[country] = country_counts.get(country, 0) + 1
    return selected
