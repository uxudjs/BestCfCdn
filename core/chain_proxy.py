"""CfGfwAX 链式订阅解析与临时 Xray 运行时。"""

import argparse
import base64
import hashlib
import ipaddress
import json
import math
import os
import platform
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass, field
from urllib.error import URLError
from urllib.parse import parse_qsl, unquote, urlsplit
from urllib.request import Request, urlopen

from core.paths import PROJECT_ROOT


class ChainProxyError(RuntimeError):
    def __init__(
        self,
        message,
        *,
        category="CORE_ERROR",
        stage="",
        recovery="",
    ):
        super().__init__(message)
        self.category = category
        self.stage = stage
        self.recovery = recovery


XRAY_VERSION = "26.3.27"
XRAY_RELEASE_BASE = (
    "https://github.com/XTLS/Xray-core/releases/download/v" + XRAY_VERSION
)


@dataclass(frozen=True)
class XrayAsset:
    name: str
    executable_name: str
    size: int
    sha256: str

    @property
    def url(self):
        return f"{XRAY_RELEASE_BASE}/{self.name}"


def _xray_asset_entry(system, architecture, size, sha256):
    executable = "xray.exe" if system == "windows" else "xray"
    return XrayAsset(
        name=f"Xray-{system}-{architecture}.zip",
        executable_name=executable,
        size=size,
        sha256=sha256,
    )


XRAY_ASSETS = {
    ("windows", "32"): _xray_asset_entry(
        "windows", "32", 20473037,
        "956a5ec00bce747c7936dc4ff7ac570df1c8030b0a4a8640f843488365084db3",
    ),
    ("windows", "64"): _xray_asset_entry(
        "windows", "64", 20913304,
        "d004c39288ce9ada487c6f398c7c545f7d749e44bdfdd59dbc9f865afba4e1ad",
    ),
    ("windows", "arm64-v8a"): _xray_asset_entry(
        "windows", "arm64-v8a", 19316452,
        "35d4ed6ec21224fb22b07c2c3f672e2350cd536f2c74d309150175a76365ea88",
    ),
    ("linux", "32"): _xray_asset_entry(
        "linux", "32", 20267274,
        "d1eeb0d9a9106eefd286fbb73595c2dfe1c48c56aa91ba1c9aefe04f188d0927",
    ),
    ("linux", "64"): _xray_asset_entry(
        "linux", "64", 21136402,
        "23cd9af937744d97776ee35ecad4972cf4b2109d1e0fe6be9930467608f7c8ae",
    ),
    ("linux", "arm32-v5"): _xray_asset_entry(
        "linux", "arm32-v5", 20230102,
        "0da9a632e15e82504831f61bf6b46c21e3081bcc79ad46bdc16e7dc2f0dc9088",
    ),
    ("linux", "arm32-v6"): _xray_asset_entry(
        "linux", "arm32-v6", 20221247,
        "0c6e751e2bba3f3ff09a793dd6a6bc45fd6fd89f49b49dfc0cf6d922dc123bec",
    ),
    ("linux", "arm32-v7a"): _xray_asset_entry(
        "linux", "arm32-v7a", 20201341,
        "c7265ae13c63ca0241a037df4ef960ad37938c8a67d984cc08834b2cfdf5654b",
    ),
    ("linux", "arm64-v8a"): _xray_asset_entry(
        "linux", "arm64-v8a", 19716427,
        "4d30283ae614e3057f730f67cd088a42be6fdf91f8639d82cb69e48cde80413c",
    ),
    ("linux", "loong64"): _xray_asset_entry(
        "linux", "loong64", 20282863,
        "4f9c917976d4e454740aa7b4e0ef9c13c950d91152aaa7926aaa652698e6e6c0",
    ),
    ("linux", "ppc64le"): _xray_asset_entry(
        "linux", "ppc64le", 19725091,
        "2f9ad6c4f35966b1e012c69d601a98bb8b63aba933d303ba6d7b5b67f2ab2acb",
    ),
    ("linux", "riscv64"): _xray_asset_entry(
        "linux", "riscv64", 20199421,
        "627ea5870b6fd05d95b7f4ceb5a54d7f2664dd075b30a7ac46ee9a6f9653d6f8",
    ),
    ("linux", "s390x"): _xray_asset_entry(
        "linux", "s390x", 20699974,
        "a209bcea3df9b0dc1ef5938695679ba1308ad9678a671279d7b1b6c5ceec09c7",
    ),
}


MAX_CORE_DOWNLOAD_BYTES = 128 * 1024 * 1024
MAX_CHAIN_SUBSCRIPTION_BYTES = 2 * 1024 * 1024


def _subprocess_creation_flags():
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


@dataclass(frozen=True)
class ChainEndpoint:
    server: str
    port: int


@dataclass(frozen=True)
class ChainTemplate:
    uuid: str = field(repr=False)
    server_name: str
    host: str
    path: str = field(repr=False)
    security: str = "tls"
    flow: str = ""
    insecure: bool = False
    transport: str = "ws"
    mode: str = ""
    ech_query_server_name: str = ""
    ech_dns_server: str = ""
    ech_dns_port: int = 443
    ech_dns_path: str = ""
    tls_fragment: str = ""
    fingerprint: str = ""


@dataclass(frozen=True)
class ChainProbe:
    template: ChainTemplate = field(repr=False)
    endpoint: ChainEndpoint


@dataclass(frozen=True)
class ChainSubscription:
    probes: tuple[ChainProbe, ...]
    source_id: str

    @property
    def template(self):
        return self.probes[0].template

    @property
    def endpoints(self):
        return tuple(probe.endpoint for probe in self.probes)


@dataclass(frozen=True)
class ChainPreflightResult:
    template: ChainTemplate = field(repr=False)
    core_path: str
    successful_endpoint: ChainEndpoint
    attempted_endpoints: int
    source_id: str


def _parse_ech_settings(value):
    query_server_name, separator, resolver = value.partition("+")
    if not separator:
        resolver, query_server_name = query_server_name, ""
    if not resolver:
        raise ChainProxyError("ECH 参数缺少 DNS 查询地址")

    try:
        parsed = urlsplit(resolver)
        port = parsed.port or 443
    except ValueError as exc:
        raise ChainProxyError("ECH DNS 查询地址端口无效") from exc
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ChainProxyError("ECH DNS 查询地址必须是无认证信息的 HTTPS URL")

    path = parsed.path or "/dns-query"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return query_server_name.lower(), parsed.hostname.lower(), port, path


def _subscription_lines(content):
    text = (content or "").strip()
    if "://" not in text:
        try:
            compact = "".join(text.split())
            text = base64.urlsafe_b64decode(
                compact + "=" * (-len(compact) % 4)
            ).decode("utf-8-sig")
        except (ValueError, UnicodeDecodeError):
            pass
    return [line.strip() for line in text.splitlines() if line.strip()]


def _decode_chain_path(path, uuid):
    encoded = path.split("/video/", 1)[1].split("?", 1)[0]
    mixed = base64.b64decode(encoded, validate=True)
    key = uuid.encode("utf-8")
    decoded = bytes(
        value ^ key[index % len(key)] for index, value in enumerate(mixed)
    )
    return json.loads(decoded.decode("utf-8"))


def _validate_chain_path(path, uuid, allow_single_trailing_slash=False):
    decode_errors = (IndexError, ValueError, UnicodeDecodeError, ZeroDivisionError)
    try:
        chain = _decode_chain_path(path, uuid)
    except decode_errors as exc:
        bare_path = path.split("?", 1)[0]
        if (
            not allow_single_trailing_slash
            or not bare_path.endswith("/")
            or bare_path.endswith("//")
        ):
            raise ChainProxyError("CfGfwAX /video/ 链式参数无法验证") from exc
        try:
            chain = _decode_chain_path(bare_path[:-1], uuid)
        except decode_errors as retry_exc:
            raise ChainProxyError("CfGfwAX /video/ 链式参数无法验证") from retry_exc

    if not isinstance(chain, dict):
        raise ChainProxyError("CfGfwAX /video/ 链式参数无法验证")
    if chain.get("type") != "socks5":
        raise ChainProxyError("CfGfwAX 链式模板不是 SOCKS5")
    if chain.get("global", True) is not True:
        raise ChainProxyError("CfGfwAX SOCKS5 未启用全局代理")

    hostname = chain.get("hostname")
    port = chain.get("port")
    if (
        not isinstance(hostname, str)
        or not hostname.strip()
        or isinstance(port, bool)
        or not isinstance(port, int)
        or not 1 <= port <= 65535
    ):
        raise ChainProxyError("CfGfwAX SOCKS5 链式参数不完整")


def _parse_allow_insecure(query):
    value = query.get("allowInsecure", query.get("insecure", "0")).strip().lower()
    if value in {"", "0", "false"}:
        return False
    if value in {"1", "true"}:
        return True
    raise ChainProxyError("CfGfwAX allowInsecure 参数无效")


def _parse_vless_node(uri):
    try:
        parsed = urlsplit(uri)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    except ValueError:
        return None
    if parsed.scheme.lower() != "vless" or not parsed.username:
        return None

    transport = query.get("type", "").lower()
    if transport in {"ws", "xhttp"}:
        endpoint_host = query.get("host") or ""
        path = query.get("path", "")
    elif transport == "grpc":
        endpoint_host = query.get("authority") or query.get("host") or ""
        path = query.get("serviceName", "")
    else:
        return None

    server_name = (query.get("sni") or endpoint_host or "").lower()
    host = endpoint_host.lower()
    if (
        not endpoint_host
        or not path
        or "/video/" not in path
    ):
        return None

    security = query.get("security", "").lower()
    if security != "tls":
        return None
    mode = query.get("mode", "")
    if transport == "xhttp" and mode != "stream-one":
        raise ChainProxyError("CfGfwAX XHTTP 仅支持显式 mode=stream-one")

    ech_query_server_name = ech_dns_server = ech_dns_path = ""
    ech_dns_port = 443
    if ech_value := query.get("ech"):
        (
            ech_query_server_name,
            ech_dns_server,
            ech_dns_port,
            ech_dns_path,
        ) = _parse_ech_settings(ech_value)

    uuid = unquote(parsed.username)
    _validate_chain_path(
        path,
        uuid,
        allow_single_trailing_slash=transport == "xhttp",
    )

    try:
        server = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ChainProxyError("CfGfwAX 订阅端点端口无效") from exc
    if not server or port is None or not 1 <= port <= 65535:
        raise ChainProxyError("CfGfwAX 订阅端点缺少有效 server:port")

    template = ChainTemplate(
        uuid=uuid,
        server_name=server_name,
        host=host,
        path=path,
        security=security,
        flow=query.get("flow", ""),
        insecure=_parse_allow_insecure(query),
        transport=transport,
        mode=mode,
        ech_query_server_name=ech_query_server_name,
        ech_dns_server=ech_dns_server,
        ech_dns_port=ech_dns_port,
        ech_dns_path=ech_dns_path,
        tls_fragment=query.get("fragment", "").strip(),
        fingerprint=query.get("fp", "").strip(),
    )
    return template, ChainEndpoint(server=server.lower(), port=port)


def extract_chain_subscription(subscription_content, subscription_url):
    """解析 CfGfwAX 逻辑模板、预检端点和脱敏来源。"""
    try:
        expected_domain = (urlsplit(subscription_url).hostname or "").lower()
    except ValueError as exc:
        raise ChainProxyError("CHAIN_PROXY_SUBSCRIPTION_URL 无效") from exc
    if not expected_domain:
        raise ChainProxyError("CHAIN_PROXY_SUBSCRIPTION_URL 缺少域名")

    nodes = []
    for line in _subscription_lines(subscription_content):
        if node := _parse_vless_node(line):
            nodes.append(node)
    if not nodes:
        raise ChainProxyError(
            "订阅中未找到包含 /video/ 的 VLESS+TLS 链式节点"
        )

    probes = []
    seen = set()
    for template, endpoint in nodes:
        probe = ChainProbe(template=template, endpoint=endpoint)
        if probe in seen:
            continue
        seen.add(probe)
        probes.append(probe)
        if len(probes) == 3:
            break
    if not probes:
        raise ChainProxyError("订阅中没有可用于前置连接的有效端点")

    return ChainSubscription(
        probes=tuple(probes),
        source_id=expected_domain,
    )


def extract_chain_template(subscription_content, subscription_url):
    """兼容旧调用方，仅返回经过验证的逻辑模板。"""
    return extract_chain_subscription(subscription_content, subscription_url).template


def _candidate_address(node):
    address = node.split("#", 1)[0]
    try:
        host, port_text = address.rsplit(":", 1)
        ipaddress.IPv4Address(host)
        port = int(port_text)
    except (ValueError, TypeError) as exc:
        raise ChainProxyError(f"候选节点格式无效：{node}") from exc
    if not 1 <= port <= 65535:
        raise ChainProxyError(f"候选节点端口无效：{node}")
    return host, port


def _xray_ech_config_list(template):
    if not template.ech_dns_server:
        return ""
    port = f":{template.ech_dns_port}" if template.ech_dns_port != 443 else ""
    resolver = f"https://{template.ech_dns_server}{port}{template.ech_dns_path}"
    if template.ech_query_server_name:
        return f"{template.ech_query_server_name}+{resolver}"
    return resolver


def _xray_fragment_settings(value):
    if not value:
        return None
    parts = [part.strip() for part in value.split(",")]
    if len(parts) == 4:
        if parts[0] != "1":
            raise ChainProxyError("CfGfwAX fragment 启用标记无法无损映射")
        parts = parts[1:]
    if len(parts) != 3 or not all(parts):
        raise ChainProxyError("CfGfwAX fragment 参数无法无损映射")
    length, interval, packets = parts
    if packets not in {"tlshello", "1-3", "1-2", "1"}:
        raise ChainProxyError("CfGfwAX fragment packets 无法无损映射")
    return {"packets": packets, "length": length, "interval": interval}


def _xray_stream_settings(template):
    if template.insecure:
        raise ChainProxyError(
            "CfGfwAX allowInsecure=true 无法无损映射到 Xray 26.3.27"
        )
    tls = {
        "serverName": template.server_name,
    }
    if ech_config := _xray_ech_config_list(template):
        tls["echConfigList"] = ech_config
    if template.fingerprint:
        tls["fingerprint"] = template.fingerprint

    stream = {
        "network": template.transport,
        "security": template.security,
        "tlsSettings": tls,
    }
    if template.transport == "ws":
        if template.mode:
            raise ChainProxyError("CfGfwAX WS mode 无法无损映射")
        stream["wsSettings"] = {"host": template.host, "path": template.path}
    elif template.transport == "grpc":
        if template.mode not in {"", "gun", "multi"}:
            raise ChainProxyError("CfGfwAX gRPC mode 无法无损映射")
        stream["grpcSettings"] = {
            "authority": template.host,
            "serviceName": template.path,
            "multiMode": template.mode == "multi",
        }
    elif template.transport == "xhttp":
        if template.mode != "stream-one":
            raise ChainProxyError("CfGfwAX XHTTP 仅支持显式 mode=stream-one")
        stream["xhttpSettings"] = {
            "host": template.host,
            "path": template.path,
            "mode": template.mode,
        }
    else:
        raise ChainProxyError("CfGfwAX 传输无法映射到 Xray")
    return stream


def build_xray_config(template, proxy_ports):
    inbounds = []
    outbounds = []
    rules = []
    fragment = _xray_fragment_settings(template.tls_fragment)
    for index, (node, listen_port) in enumerate(proxy_ports.items()):
        server, server_port = _candidate_address(node)
        inbound_tag = f"chain-in-{index}"
        outbound_tag = f"chain-out-{index}"
        inbound = {
            "tag": inbound_tag,
            "listen": "127.0.0.1",
            "port": int(listen_port),
            "protocol": "socks",
            "settings": {"auth": "noauth", "udp": False},
        }
        settings = {
            "address": server,
            "port": server_port,
            "id": template.uuid,
            "encryption": "none",
        }
        if template.flow:
            settings["flow"] = template.flow
        stream = _xray_stream_settings(template)
        if fragment:
            fragment_tag = f"fragment-out-{index}"
            stream["sockopt"] = {"dialerProxy": fragment_tag}
        outbound = {
            "tag": outbound_tag,
            "protocol": "vless",
            "settings": settings,
            "streamSettings": stream,
        }
        inbounds.append(inbound)
        outbounds.append(outbound)
        if fragment:
            outbounds.append(
                {
                    "tag": fragment_tag,
                    "protocol": "freedom",
                    "settings": {"fragment": fragment},
                }
            )
        rules.append(
            {
                "type": "field",
                "inboundTag": [inbound_tag],
                "outboundTag": outbound_tag,
            }
        )
    return {
        "log": {"loglevel": "warning"},
        "inbounds": inbounds,
        "outbounds": outbounds,
        "routing": {"rules": rules},
    }


def _xray_asset(system=None, machine=None):
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    systems = {"windows": "windows", "linux": "linux"}
    architectures = {
        "x86_64": "64",
        "amd64": "64",
        "i386": "32",
        "i686": "32",
        "x86": "32",
        "aarch64": "arm64-v8a",
        "arm64": "arm64-v8a",
        "armv7l": "arm32-v7a",
        "armv6l": "arm32-v6",
        "armv5l": "arm32-v5",
        "riscv64": "riscv64",
        "s390x": "s390x",
        "ppc64le": "ppc64le",
        "loongarch64": "loong64",
        "loong64": "loong64",
    }
    key = (systems.get(system), architectures.get(machine))
    asset = XRAY_ASSETS.get(key)
    if not asset:
        raise ChainProxyError(
            f"Xray 自动安装仅支持当前 Windows/Linux 矩阵：{system}/{machine}"
        )
    return asset


def _validate_xray_binary(core_path):
    try:
        version = subprocess.run(
            [core_path, "version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=_subprocess_creation_flags(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ChainProxyError("无法验证 Xray 身份或版本") from exc
    output = (version.stdout or version.stderr or "").strip()
    tokens = output.split()
    if (
        version.returncode
        or len(tokens) < 2
        or tokens[0] != "Xray"
        or tokens[1] != XRAY_VERSION
    ):
        raise ChainProxyError(f"核心不是固定版本 Xray {XRAY_VERSION}，身份或版本无效")

    config_path = ""
    try:
        config = tempfile.NamedTemporaryFile(
            mode="w",
            prefix="xray-check-",
            suffix=".json",
            encoding="utf-8",
            newline="\n",
            delete=False,
        )
        config_path = config.name
        with config:
            config.write("{}")
        checked = subprocess.run(
            [core_path, "run", "-test", "-config", config_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=_subprocess_creation_flags(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ChainProxyError("无法执行 Xray 配置检查") from exc
    finally:
        if config_path:
            try:
                os.remove(config_path)
            except FileNotFoundError:
                pass
    if checked.returncode:
        raise ChainProxyError("Xray 配置检查能力验证失败")
    return core_path


def _extract_xray_archive(archive_path, destination, executable_name):
    try:
        with zipfile.ZipFile(archive_path) as bundle:
            members = []
            for member in bundle.infolist():
                normalized = member.filename.replace("\\", "/")
                parts = normalized.split("/")
                if (
                    normalized.startswith("/")
                    or any(part == ".." for part in parts)
                    or (parts and ":" in parts[0])
                ):
                    raise ChainProxyError("Xray 压缩包包含不安全路径")
                if (
                    not member.is_dir()
                    and parts[-1].lower() == executable_name.lower()
                ):
                    members.append(member)
            if len(members) != 1:
                raise ChainProxyError("Xray 压缩包内的可执行文件不唯一")
            with bundle.open(members[0]) as source, open(destination, "wb") as target:
                _copy_limited(source, target)
    except zipfile.BadZipFile as exc:
        raise ChainProxyError("Xray 压缩包格式无效") from exc


def _is_link_or_reparse(path):
    if os.path.islink(path):
        return True
    try:
        item = os.lstat(path)
    except FileNotFoundError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(item, "st_file_attributes", 0) & reparse_flag)


def _project_xray_directory(base_dir, *, create=False):
    project_dir = os.path.abspath(base_dir)
    install_dir = os.path.join(project_dir, ".xray")
    if os.path.lexists(install_dir):
        if _is_link_or_reparse(install_dir):
            raise ChainProxyError("项目 .xray 是链接或重解析点，拒绝使用")
        if not os.path.isdir(install_dir):
            raise ChainProxyError("项目 .xray 已存在但不是目录")
    elif create:
        os.makedirs(install_dir)

    project_real = os.path.realpath(project_dir)
    install_real = os.path.realpath(install_dir)
    try:
        if os.path.commonpath((project_real, install_real)) != project_real:
            raise ChainProxyError("项目 .xray 真实路径越出项目目录")
    except ValueError as exc:
        raise ChainProxyError("项目 .xray 真实路径无效") from exc
    if os.path.lexists(install_dir) and _is_link_or_reparse(install_dir):
        raise ChainProxyError("项目 .xray 是链接或重解析点，拒绝使用")
    return install_dir


def _download_xray(base_dir):
    install_dir = _project_xray_directory(base_dir, create=True)
    asset = _xray_asset()
    archive_path = executable_temp = ""
    try:
        archive = tempfile.NamedTemporaryFile(
            prefix="download-",
            suffix=".zip",
            dir=install_dir,
            delete=False,
        )
        archive_path = archive.name
        archive.close()
        _download_verified_asset(
            asset.url,
            archive_path,
            asset.size,
            asset.sha256,
        )

        executable = tempfile.NamedTemporaryFile(
            prefix="xray-",
            suffix=".exe" if asset.executable_name.endswith(".exe") else "",
            dir=install_dir,
            delete=False,
        )
        executable_temp = executable.name
        executable.close()
        _extract_xray_archive(
            archive_path,
            executable_temp,
            asset.executable_name,
        )
        mode = os.stat(executable_temp).st_mode
        os.chmod(
            executable_temp,
            mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
        )
        _validate_xray_binary(executable_temp)
        install_dir = _project_xray_directory(base_dir)
        target = os.path.join(install_dir, asset.executable_name)
        os.replace(executable_temp, target)
        executable_temp = ""
        return target
    except (OSError, URLError, TypeError, ValueError) as exc:
        raise ChainProxyError(f"自动安装 Xray 失败：{exc}") from exc
    finally:
        for path in (archive_path, executable_temp):
            if path:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass


def resolve_xray_path(configured_path="", base_dir=None):
    project_dir = os.path.abspath(base_dir or PROJECT_ROOT)
    requested = str(configured_path or "").strip()
    if requested:
        expanded = os.path.expanduser(os.path.expandvars(requested))
        if not os.path.isabs(expanded):
            expanded = os.path.join(project_dir, expanded)
        expanded = os.path.abspath(expanded)
        if os.path.isfile(expanded):
            try:
                return _validate_xray_binary(expanded)
            except ChainProxyError:
                pass

    executable_name = "xray.exe" if platform.system() == "Windows" else "xray"
    local_path = os.path.join(
        _project_xray_directory(project_dir), executable_name
    )
    if os.path.isfile(local_path):
        try:
            return _validate_xray_binary(local_path)
        except ChainProxyError:
            pass
    found = shutil.which("xray")
    if found:
        try:
            return _validate_xray_binary(found)
        except ChainProxyError:
            pass
    return _download_xray(project_dir)


def _copy_limited(source, destination):
    total = 0
    while chunk := source.read(1024 * 1024):
        total += len(chunk)
        if total > MAX_CORE_DOWNLOAD_BYTES:
            raise ChainProxyError("Xray 下载或解压内容超过安全大小限制")
        destination.write(chunk)


def _download_verified_asset(url, destination, expected_size, expected_digest):
    curl_path = shutil.which("curl")
    if curl_path:
        try:
            downloaded = subprocess.run(
                [
                    curl_path,
                    "--location",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--retry",
                    "5",
                    "--retry-delay",
                    "2",
                    "--retry-all-errors",
                    "--continue-at",
                    "-",
                    "--max-filesize",
                    str(MAX_CORE_DOWNLOAD_BYTES),
                    "--output",
                    destination,
                    url,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
                creationflags=_subprocess_creation_flags(),
            )
        except (OSError, subprocess.TimeoutExpired):
            downloaded = None
        if downloaded and downloaded.returncode == 0:
            actual_size = os.path.getsize(destination)
            if actual_size != expected_size:
                raise ChainProxyError(
                    f"Xray 下载不完整：预期 {expected_size} 字节，"
                    f"实际 {actual_size} 字节"
                )
            hasher = hashlib.sha256()
            with open(destination, "rb") as archive:
                while chunk := archive.read(1024 * 1024):
                    hasher.update(chunk)
            actual_digest = hasher.hexdigest()
            if actual_digest.lower() != expected_digest.lower():
                raise ChainProxyError("Xray 下载文件 SHA-256 校验失败")
            return

    last_size = 0
    for attempt in range(1, 6):
        hasher = hashlib.sha256()
        total = 0
        try:
            with open(destination, "wb") as archive, urlopen(
                Request(url, headers={"User-Agent": "BestCfCdn"}),
                timeout=120,
            ) as response:
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_CORE_DOWNLOAD_BYTES:
                        raise ChainProxyError("Xray 下载内容超过安全大小限制")
                    archive.write(chunk)
                    hasher.update(chunk)
        except (OSError, URLError):
            if attempt == 5:
                raise
            continue
        last_size = total
        if total != expected_size:
            if attempt < 5:
                continue
            raise ChainProxyError(
                f"Xray 下载不完整：预期 {expected_size} 字节，"
                f"实际 {last_size} 字节，已重试 5 次"
            )
        if hasher.hexdigest().lower() != expected_digest.lower():
            raise ChainProxyError("Xray 下载文件 SHA-256 校验失败")
        return


def allocate_local_ports(nodes):
    sockets = []
    ports = {}
    try:
        for node in nodes:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
            ports[node] = sock.getsockname()[1]
    finally:
        for sock in sockets:
            sock.close()
    return ports


class XrayRuntime:
    def __init__(self, core_path, template, candidates, temp_parent=None):
        self.core_path = core_path
        self.proxy_ports = allocate_local_ports(candidates)
        self.config = build_xray_config(template, self.proxy_ports)
        self._secrets = (template.uuid, template.path)
        self.temp_parent = temp_parent
        self._temp = None
        self._process = None
        self._log = None

    def _redact(self, message):
        text = str(message or "")
        for value in self._secrets:
            if value:
                text = text.replace(value, "***")
        return text.strip()[-500:]

    def __enter__(self):
        self._temp = tempfile.TemporaryDirectory(
            prefix="bestcfcdn-chain-", dir=self.temp_parent
        )
        config_path = os.path.join(self._temp.name, "config.json")
        log_path = os.path.join(self._temp.name, "xray.log")
        with open(config_path, "w", encoding="utf-8", newline="\n") as file:
            json.dump(self.config, file, ensure_ascii=False)
        try:
            os.chmod(config_path, 0o600)
        except OSError:
            pass

        try:
            checked = subprocess.run(
                [self.core_path, "run", "-test", "-config", config_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                creationflags=_subprocess_creation_flags(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.__exit__(None, None, None)
            raise ChainProxyError("无法执行 Xray 配置检查") from exc
        if checked.returncode:
            detail = self._redact(checked.stderr or checked.stdout)
            self.__exit__(None, None, None)
            raise ChainProxyError(f"Xray 配置检查失败：{detail or '未知错误'}")

        self._log = open(log_path, "w+", encoding="utf-8")
        try:
            self._process = subprocess.Popen(
                [self.core_path, "run", "-config", config_path],
                stdout=self._log,
                stderr=self._log,
                creationflags=_subprocess_creation_flags(),
            )
            first_port = next(iter(self.proxy_ports.values()))
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if self._process.poll() is not None:
                    break
                try:
                    with socket.create_connection(("127.0.0.1", first_port), 0.2):
                        return self
                except OSError:
                    time.sleep(0.05)
            self._log.seek(0)
            detail = self._redact(self._log.read())
            raise ChainProxyError(f"Xray 启动失败：{detail or '监听端口未就绪'}")
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type, exc, traceback):
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        if self._log:
            self._log.close()
            self._log = None
        if self._temp:
            self._temp.cleanup()
            self._temp = None
        self._process = None


def _preflight_error(message, category, stage, recovery):
    return ChainProxyError(
        message,
        category=category,
        stage=stage,
        recovery=recovery,
    )


def _load_preflight_config(config_path):
    try:
        with open(config_path, "r", encoding="utf-8-sig") as config_file:
            config = json.load(config_file)
    except FileNotFoundError as exc:
        raise _preflight_error(
            "链式预检配置文件不存在",
            "ENVIRONMENT_ERROR",
            "config",
            "先运行 setup 或创建 config.json",
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise _preflight_error(
            "链式预检配置文件无法读取",
            "ENVIRONMENT_ERROR",
            "config",
            "检查 config.json 的权限和 JSON 格式",
        ) from exc
    if not isinstance(config, dict):
        raise _preflight_error(
            "链式预检配置根节点必须是 JSON 对象",
            "ENVIRONMENT_ERROR",
            "config",
            "修正 config.json",
        )
    enabled = config.get("CHAIN_PROXY_TEST_ENABLED", False)
    if type(enabled) is not bool:
        raise _preflight_error(
            "CHAIN_PROXY_TEST_ENABLED 必须是 JSON 布尔值",
            "ENVIRONMENT_ERROR",
            "config",
            "使用 true 或 false，不要使用字符串或数字",
        )
    return config, enabled


def _validate_subscription_url(value):
    url = str(value or "").strip()
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise _preflight_error(
            "CHAIN_PROXY_SUBSCRIPTION_URL 无效",
            "SUBSCRIPTION_ERROR",
            "subscription",
            "配置无认证信息的 HTTPS CfGfwAX mixed/base64 订阅",
        ) from exc
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise _preflight_error(
            "CHAIN_PROXY_SUBSCRIPTION_URL 必须是无认证信息的 HTTPS URL",
            "SUBSCRIPTION_ERROR",
            "subscription",
            "配置无认证信息的 HTTPS CfGfwAX mixed/base64 订阅",
        )
    return url


def _positive_timeout(config, key, default):
    value = config.get(key, default)
    if isinstance(value, bool):
        value = None
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = None
    if value is None or not math.isfinite(value) or value <= 0:
        raise _preflight_error(
            f"{key} 必须是大于 0 的秒数",
            "ENVIRONMENT_ERROR",
            "config",
            "修正链式预检超时配置",
        )
    return value


def _fetch_chain_subscription(url, config):
    timeout = max(
        _positive_timeout(config, "FETCH_CONNECT_TIMEOUT", 5),
        _positive_timeout(config, "FETCH_TIMEOUT", 10),
    )
    request = Request(
        url,
        headers={"User-Agent": "BestCfCdn-chain-preflight"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            content = response.read(MAX_CHAIN_SUBSCRIPTION_BYTES + 1)
    except (OSError, URLError) as exc:
        raise _preflight_error(
            "无法获取 CfGfwAX 链式订阅",
            "SUBSCRIPTION_ERROR",
            "subscription",
            "检查订阅地址、Token 和网络",
        ) from exc
    if len(content) > MAX_CHAIN_SUBSCRIPTION_BYTES:
        raise _preflight_error(
            "CfGfwAX 链式订阅超过 2 MiB",
            "SUBSCRIPTION_ERROR",
            "subscription",
            "检查订阅服务是否返回预期内容",
        )
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _preflight_error(
            "CfGfwAX 链式订阅不是有效 UTF-8",
            "SUBSCRIPTION_ERROR",
            "subscription",
            "检查订阅服务输出",
        ) from exc


def _check_socks_https(proxy_port, config):
    curl_path = shutil.which("curl")
    if not curl_path:
        raise _preflight_error(
            "链式预检需要 curl，但当前系统未找到",
            "ENVIRONMENT_ERROR",
            "connectivity",
            "安装 curl 后重试",
        )
    target = config.get(
        "CHAIN_PROXY_PREFLIGHT_URL",
        "https://www.cloudflare.com/cdn-cgi/trace",
    )
    try:
        target = str(target)
        parsed = urlsplit(target)
    except ValueError as exc:
        raise _preflight_error(
            "CHAIN_PROXY_PREFLIGHT_URL 无效",
            "ENVIRONMENT_ERROR",
            "config",
            "修正 CHAIN_PROXY_PREFLIGHT_URL",
        ) from exc
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise _preflight_error(
            "CHAIN_PROXY_PREFLIGHT_URL 必须是无认证信息的 HTTPS URL",
            "ENVIRONMENT_ERROR",
            "config",
            "修正 CHAIN_PROXY_PREFLIGHT_URL",
        )
    connect_timeout = _positive_timeout(
        config, "HTTP_TEST_CONNECT_TIMEOUT", 5
    )
    request_timeout = _positive_timeout(config, "HTTP_TEST_TIMEOUT", 8)
    process_buffer = _positive_timeout(config, "BANDWIDTH_PROCESS_BUFFER", 2)
    null_device = "NUL" if sys.platform == "win32" else "/dev/null"
    try:
        result = subprocess.run(
            [
                curl_path,
                "--silent",
                "--show-error",
                "--output",
                null_device,
                "--write-out",
                "%{http_code}",
                "--proxy",
                f"socks5h://127.0.0.1:{int(proxy_port)}",
                "--noproxy",
                "",
                "--connect-timeout",
                str(connect_timeout),
                "--max-time",
                str(request_timeout),
                target,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=request_timeout + process_buffer,
            creationflags=_subprocess_creation_flags(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    status = (result.stdout or "").strip()[-3:]
    return result.returncode == 0 and status.isdigit() and 200 <= int(status) < 300


def _atomic_write_config(config_path, config, mode):
    parent = os.path.dirname(os.path.abspath(config_path))
    temp_path = ""
    try:
        handle = tempfile.NamedTemporaryFile(
            mode="w",
            prefix=".config-",
            suffix=".json",
            dir=parent,
            encoding="utf-8",
            newline="\n",
            delete=False,
        )
        temp_path = handle.name
        with handle:
            json.dump(config, handle, ensure_ascii=False, indent=4)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, config_path)
        temp_path = ""
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except FileNotFoundError:
                pass


def _migrate_core_path(config_path, config, core_path):
    configured = str(config.get("CHAIN_PROXY_CORE_PATH") or "").strip()
    if not configured:
        return False
    project_dir = os.path.dirname(os.path.abspath(config_path))
    local_dir = os.path.realpath(os.path.join(project_dir, ".xray"))
    resolved_core = os.path.realpath(core_path)
    try:
        if os.path.commonpath((local_dir, resolved_core)) != local_dir:
            return False
    except ValueError:
        return False
    relative = os.path.relpath(resolved_core, project_dir).replace(os.sep, "/")
    if configured.replace("\\", "/") == relative:
        return False
    migrated = dict(config)
    migrated["CHAIN_PROXY_CORE_PATH"] = relative
    try:
        mode = stat.S_IMODE(os.stat(config_path).st_mode)
        _atomic_write_config(config_path, migrated, mode)
    except OSError as exc:
        raise _preflight_error(
            "Xray 已验证，但无法原子更新 CHAIN_PROXY_CORE_PATH",
            "ENVIRONMENT_ERROR",
            "migration",
            "检查 config.json 权限后重试",
        ) from exc
    config["CHAIN_PROXY_CORE_PATH"] = relative
    return True


def preflight_chain_proxy(config_path):
    config_path = os.path.abspath(config_path)
    config, enabled = _load_preflight_config(config_path)
    if not enabled:
        return None
    subscription_url = _validate_subscription_url(
        config.get("CHAIN_PROXY_SUBSCRIPTION_URL")
    )
    content = _fetch_chain_subscription(subscription_url, config)
    try:
        subscription = extract_chain_subscription(content, subscription_url)
    except ChainProxyError as exc:
        raise _preflight_error(
            "CfGfwAX 链式订阅不符合项目契约",
            "SUBSCRIPTION_ERROR",
            "subscription",
            "检查 mixed/base64 VLESS、全局 SOCKS5 与传输字段",
        ) from exc
    try:
        core_path = resolve_xray_path(
            config.get("CHAIN_PROXY_CORE_PATH", ""),
            os.path.dirname(config_path),
        )
    except ChainProxyError as exc:
        raise _preflight_error(
            "Xray 固定版本发现或验证失败",
            "CORE_ERROR",
            "core",
            "检查核心路径或重新运行 setup",
        ) from exc

    for attempted, probe in enumerate(subscription.probes[:3], start=1):
        endpoint = probe.endpoint
        candidate = f"{endpoint.server}:{endpoint.port}"
        try:
            with XrayRuntime(
                core_path,
                probe.template,
                [candidate],
            ) as runtime:
                proxy_port = runtime.proxy_ports[candidate]
                connected = _check_socks_https(proxy_port, config)
        except ChainProxyError as exc:
            if exc.category == "ENVIRONMENT_ERROR":
                raise
            raise _preflight_error(
                "Xray 配置检查或本地运行时启动失败",
                "CORE_ERROR",
                "core",
                "检查固定版本与订阅字段兼容性",
            ) from exc
        if connected:
            _migrate_core_path(config_path, config, core_path)
            return ChainPreflightResult(
                template=probe.template,
                core_path=core_path,
                successful_endpoint=endpoint,
                attempted_endpoints=attempted,
                source_id=subscription.source_id,
            )
    raise _preflight_error(
        "Xray 已启动，但真实 SOCKS HTTPS 连接全部失败",
        "CONNECTIVITY_ERROR",
        "connectivity",
        "检查 CfGfwAX 节点、全局 SOCKS5 与出口连通性",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m core.chain_proxy")
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight_parser = subparsers.add_parser("preflight")
    preflight_parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    try:
        result = preflight_chain_proxy(args.config)
    except ChainProxyError as exc:
        detail = f"{exc.category}: {exc}"
        if exc.recovery:
            detail += f"；建议：{exc.recovery}"
        print(detail, file=sys.stderr)
        return 1
    if result is None:
        print("CHAIN_PREFLIGHT_DISABLED")
    else:
        print(
            f"CHAIN_PREFLIGHT_OK source={result.source_id} "
            f"attempts={result.attempted_endpoints}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
