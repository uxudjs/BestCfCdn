#!/usr/bin/env python3
"""并发安全地把当前终端的优选节点合并到 GitHub ip.txt。"""

import argparse
import base64
import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import quote

import requests

from local_state import resolve_local_output


NODE_LINE_RE = re.compile(
    r"^(?P<endpoint>(?:\d{1,3}\.){3}\d{1,3}:\d+)#"
    r"(?P<label>\S+)(?P<suffix>.*)$"
)


def load_config(path):
    with open(path, "r", encoding="utf-8-sig") as config_file:
        return json.load(config_file)


def validate_config(config):
    token = str(config.get("GITHUB_SYNC_TOKEN", "")).strip()
    repository = str(config.get("GITHUB_SYNC_REPOSITORY", "")).strip()
    branch = str(config.get("GITHUB_SYNC_BRANCH", "main")).strip()
    remote_path = str(config.get("GITHUB_SYNC_REMOTE_PATH", "ip.txt")).strip()
    field_id = str(config.get("GITHUB_SYNC_FIELD_ID", "")).strip()
    top_n = int(config.get("GITHUB_SYNC_TOP_N", 5))
    retries = int(config.get("GITHUB_SYNC_CONFLICT_RETRIES", 5))

    placeholders = ("your_", "请填写")
    if not token or token.startswith(placeholders):
        raise ValueError("请在 config.json 中填写 GITHUB_SYNC_TOKEN")
    if not repository or repository.startswith(placeholders) or repository.count("/") != 1:
        raise ValueError("GITHUB_SYNC_REPOSITORY 必须为 owner/repo 格式")
    if not branch:
        raise ValueError("GITHUB_SYNC_BRANCH 不能为空")
    if not remote_path or remote_path.startswith("/") or ".." in remote_path.split("/"):
        raise ValueError("GITHUB_SYNC_REMOTE_PATH 必须是仓库内的安全相对路径")
    if not field_id or field_id.startswith(placeholders):
        raise ValueError("请为 GITHUB_SYNC_FIELD_ID 设置唯一终端名称")
    if any(char in field_id for char in ("|", "#", "\r", "\n")) or any(
        char.isspace() for char in field_id
    ):
        raise ValueError("GITHUB_SYNC_FIELD_ID 不能包含空白、|、# 或换行符")
    if top_n < 1 or top_n > 100:
        raise ValueError("GITHUB_SYNC_TOP_N 必须在 1 到 100 之间")
    if retries < 1:
        raise ValueError("GITHUB_SYNC_CONFLICT_RETRIES 必须大于等于 1")

    return token, repository, branch, remote_path, field_id, top_n, retries


def prepare_local_nodes(path, field_id, top_n):
    nodes = []
    seen = set()
    with open(path, "r", encoding="utf-8-sig") as input_file:
        for raw_line in input_file:
            line = raw_line.strip()
            match = NODE_LINE_RE.match(line)
            if not match:
                continue
            endpoint = match.group("endpoint")
            if endpoint in seen:
                continue
            seen.add(endpoint)
            label = match.group("label").split("|", 1)[0]
            suffix = match.group("suffix")
            nodes.append(f"{endpoint}#{label}|{field_id}{suffix}")
            if len(nodes) >= top_n:
                break
    if not nodes:
        raise ValueError(f"{path} 中没有可上报的有效 IPv4 节点")
    return nodes


def belongs_to_field(line, field_id):
    match = NODE_LINE_RE.match(line.strip())
    if not match:
        return False
    label = match.group("label")
    return "|" in label and label.rsplit("|", 1)[1] == field_id


def merge_nodes(remote_content, field_id, local_nodes):
    remote_lines = [line.strip() for line in remote_content.splitlines() if line.strip()]
    insertion_index = None
    kept_lines = []
    for line in remote_lines:
        if belongs_to_field(line, field_id):
            if insertion_index is None:
                insertion_index = len(kept_lines)
            continue
        kept_lines.append(line)
    if insertion_index is None:
        insertion_index = len(kept_lines)
    merged = kept_lines[:insertion_index] + local_nodes + kept_lines[insertion_index:]
    return "\n".join(merged) + "\n"


def github_headers(token):
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "BestCfCdn-multi-terminal-sync",
    }


def fetch_remote(session, api_url, branch, timeout):
    response = session.get(api_url, params={"ref": branch}, timeout=timeout)
    if response.status_code == 404:
        return "", None
    response.raise_for_status()
    payload = response.json()
    if payload.get("type") != "file":
        raise RuntimeError("GITHUB_SYNC_REMOTE_PATH 不是普通文件")
    content = base64.b64decode(payload.get("content", "")).decode("utf-8-sig")
    return content, payload["sha"]


def update_remote(session, api_url, branch, field_id, content, sha, timeout):
    payload = {
        "message": f"Update {field_id} nodes at {datetime.now():%Y-%m-%d %H:%M:%S}",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    return session.put(api_url, json=payload, timeout=timeout)


def sync(config_path, input_path=None):
    config = load_config(config_path)
    token, repository, branch, remote_path, field_id, top_n, retries = validate_config(config)
    if input_path is None:
        input_path = resolve_local_output(config, config_path, print)
    local_nodes = prepare_local_nodes(input_path, field_id, top_n)
    timeout = (10, 30)
    encoded_path = "/".join(quote(part, safe="") for part in remote_path.split("/"))
    api_url = f"https://api.github.com/repos/{repository}/contents/{encoded_path}"

    with requests.Session() as session:
        session.headers.update(github_headers(token))
        for attempt in range(1, retries + 1):
            remote_content, sha = fetch_remote(session, api_url, branch, timeout)
            merged_content = merge_nodes(remote_content, field_id, local_nodes)
            response = update_remote(
                session, api_url, branch, field_id, merged_content, sha, timeout
            )
            if response.status_code in (200, 201):
                print(
                    f"✅ 已安全同步 {field_id} 的 {len(local_nodes)} 个节点到 "
                    f"{repository}/{remote_path}"
                )
                return 0
            if response.status_code in (409, 422) and attempt < retries:
                print(f"远端文件已被其他终端更新，重新拉取合并（{attempt}/{retries}）...")
                time.sleep(min(attempt, 3))
                continue
            try:
                detail = response.json().get("message", response.text)
            except ValueError:
                detail = response.text
            raise RuntimeError(f"GitHub 更新失败（HTTP {response.status_code}）：{detail}")
    return 1


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.path.join(script_dir, "config.json"))
    parser.add_argument(
        "--input",
        help="本机优选结果文件；省略时读取 config.json 的 OUTPUT_FILE",
    )
    args = parser.parse_args()
    try:
        return sync(args.config, args.input)
    except (OSError, ValueError, RuntimeError, requests.RequestException) as exc:
        print(f"❌ GitHub 多终端同步失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
