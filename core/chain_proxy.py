"""CfGfwAX 链式订阅解析与临时 sing-box 运行时。"""

import base64
import hashlib
import ipaddress
import json
import os
import platform
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from dataclasses import dataclass
from urllib.error import URLError
from urllib.parse import parse_qsl, unquote, urlsplit
from urllib.request import Request, urlopen

from core.paths import PROJECT_ROOT


class ChainProxyError(RuntimeError):
    pass


SING_BOX_RELEASE_API = (
    "https://api.github.com/repos/SagerNet/sing-box/releases/latest"
)
MAX_CORE_DOWNLOAD_BYTES = 128 * 1024 * 1024


@dataclass(frozen=True)
class ChainTemplate:
    uuid: str
    server_name: str
    host: str
    path: str
    flow: str = ""
    insecure: bool = False
    transport: str = "ws"
    ech_query_server_name: str = ""
    ech_dns_server: str = ""
    ech_dns_port: int = 443
    ech_dns_path: str = ""
    tls_fragment: bool = False
    fingerprint: str = ""


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


def _validate_chain_path(path, uuid):
    try:
        encoded = path.split("/video/", 1)[1].split("?", 1)[0]
        mixed = base64.b64decode(encoded, validate=True)
        key = uuid.encode("utf-8")
        decoded = bytes(
            value ^ key[index % len(key)] for index, value in enumerate(mixed)
        )
        chain = json.loads(decoded.decode("utf-8"))
    except (IndexError, ValueError, UnicodeDecodeError, ZeroDivisionError) as exc:
        raise ChainProxyError("CfGfwAX /video/ 链式参数无法验证") from exc
    if not isinstance(chain, dict):
        raise ChainProxyError("CfGfwAX /video/ 链式参数无法验证")
    if chain.get("type") != "socks5":
        raise ChainProxyError("CfGfwAX 链式模板不是 SOCKS5")
    if chain.get("global", True) is not True:
        raise ChainProxyError("CfGfwAX SOCKS5 未启用全局代理")
    if not chain.get("hostname") or not chain.get("port"):
        raise ChainProxyError("CfGfwAX SOCKS5 链式参数不完整")


def _parse_vless_template(uri, expected_domain):
    try:
        parsed = urlsplit(uri)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    except ValueError:
        return None
    if parsed.scheme.lower() != "vless" or not parsed.username:
        return None
    transport = query.get("type", "").lower()
    if transport == "ws":
        endpoint_host = query.get("host") or ""
        path = query.get("path", "")
    elif transport == "grpc":
        endpoint_host = query.get("authority") or query.get("host") or ""
        path = query.get("serviceName", "")
    else:
        endpoint_host = query.get("host") or ""
        path = query.get("path", "")

    server_name = (query.get("sni") or endpoint_host or "").lower()
    host = (endpoint_host or server_name).lower()
    if expected_domain not in (server_name, host) or "/video/" not in path:
        return None
    if query.get("security", "").lower() != "tls":
        return None
    if transport == "xhttp":
        raise ChainProxyError("链式测速当前核心不支持 CfGfwAX XHTTP 传输，请切换为 WebSocket 或 gRPC")
    if transport not in {"ws", "grpc"}:
        return None

    ech_query_server_name = ech_dns_server = ech_dns_path = ""
    ech_dns_port = 443
    if ech_value := query.get("ech"):
        ech_query_server_name, ech_dns_server, ech_dns_port, ech_dns_path = _parse_ech_settings(ech_value)
    uuid = unquote(parsed.username)
    _validate_chain_path(path, uuid)
    return ChainTemplate(
        uuid=uuid,
        server_name=server_name,
        host=host,
        path=path,
        flow=query.get("flow", ""),
        insecure=query.get("allowInsecure", query.get("insecure", "0"))
        in ("1", "true"),
        transport=transport,
        ech_query_server_name=ech_query_server_name,
        ech_dns_server=ech_dns_server,
        ech_dns_port=ech_dns_port,
        ech_dns_path=ech_dns_path,
        tls_fragment=query.get("fragment", "").strip().lower()
        not in {"", "0", "false", "off", "none"},
        fingerprint=query.get("fp", "").strip(),
    )


def extract_chain_template(subscription_content, subscription_url):
    """归并同一逻辑配置的多条 CfGfwAX 地址，并拒绝歧义模板。"""
    try:
        expected_domain = (urlsplit(subscription_url).hostname or "").lower()
    except ValueError as exc:
        raise ChainProxyError("CHAIN_PROXY_SUBSCRIPTION_URL 无效") from exc
    if not expected_domain:
        raise ChainProxyError("CHAIN_PROXY_SUBSCRIPTION_URL 缺少域名")

    templates = {
        template
        for line in _subscription_lines(subscription_content)
        if (template := _parse_vless_template(line, expected_domain)) is not None
    }
    if not templates:
        raise ChainProxyError(
            "订阅中未找到匹配域名、包含 /video/ 的 VLESS+WS+TLS 链式节点"
        )
    if len(templates) > 1:
        raise ChainProxyError("订阅中存在多个不同的链式代理模板，无法自动选择")
    return templates.pop()


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


def build_sing_box_config(template, proxy_ports):
    inbounds = []
    outbounds = []
    rules = []
    for index, (node, listen_port) in enumerate(proxy_ports.items()):
        server, server_port = _candidate_address(node)
        inbound_tag = f"chain-in-{index}"
        outbound_tag = f"chain-out-{index}"
        inbound = {
            "type": "socks",
            "tag": inbound_tag,
            "listen": "127.0.0.1",
            "listen_port": int(listen_port),
        }
        tls = {
            "enabled": True,
            "server_name": template.server_name,
            "insecure": template.insecure,
        }
        if template.ech_dns_server:
            tls["ech"] = {"enabled": True}
            if template.ech_query_server_name:
                tls["ech"]["query_server_name"] = template.ech_query_server_name
        if template.tls_fragment:
            tls["fragment"] = True
        if template.fingerprint:
            tls["utls"] = {"enabled": True, "fingerprint": template.fingerprint}
        transport = (
            {
                "type": "ws",
                "path": template.path,
                "headers": {"Host": template.host},
            }
            if template.transport == "ws"
            else {"type": "grpc", "service_name": template.path}
        )
        outbound = {
            "type": "vless",
            "tag": outbound_tag,
            "server": server,
            "server_port": server_port,
            "uuid": template.uuid,
            "network": "tcp",
            "tls": tls,
            "transport": transport,
        }
        if template.flow:
            outbound["flow"] = template.flow
        inbounds.append(inbound)
        outbounds.append(outbound)
        rules.append(
            {
                "inbound": [inbound_tag],
                "action": "route",
                "outbound": outbound_tag,
            }
        )
    config = {
        "log": {"level": "warn", "timestamp": False},
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {"rules": rules},
    }
    if template.ech_dns_server:
        config["dns"] = {
            "servers": [
                {"tag": "chain-ech-bootstrap", "type": "local"},
                {
                    "tag": "chain-ech-doh",
                    "type": "https",
                    "server": template.ech_dns_server,
                    "server_port": template.ech_dns_port,
                    "path": template.ech_dns_path,
                    "tls": {"enabled": True, "server_name": template.ech_dns_server},
                    "domain_resolver": "chain-ech-bootstrap",
                },
            ],
            "final": "chain-ech-doh",
        }
    return config


def _sing_box_asset(version, system=None, machine=None):
    system = (system or platform.system()).lower()
    machine = (machine or platform.machine()).lower()
    systems = {"windows": "windows", "linux": "linux", "darwin": "darwin"}
    architectures = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "i386": "386",
        "i686": "386",
        "x86": "386",
        "aarch64": "arm64",
        "arm64": "arm64",
        "armv7l": "armv7",
        "armv6l": "armv6",
        "armv5l": "armv5",
        "riscv64": "riscv64",
        "s390x": "s390x",
        "ppc64le": "ppc64le",
        "loongarch64": "loong64",
        "loong64": "loong64",
    }
    os_name = systems.get(system)
    arch = architectures.get(machine)
    if not os_name or not arch:
        raise ChainProxyError(
            f"sing-box 暂不支持自动下载到当前设备：{system}/{machine}"
        )
    if os_name in {"windows", "darwin"} and arch not in {"amd64", "arm64", "386"}:
        raise ChainProxyError(
            f"sing-box 暂不支持自动下载到当前设备：{system}/{machine}"
        )
    extension = "zip" if os_name == "windows" else "tar.gz"
    return (
        f"sing-box-{version}-{os_name}-{arch}.{extension}",
        "sing-box.exe" if os_name == "windows" else "sing-box",
    )


def _copy_limited(source, destination):
    total = 0
    while chunk := source.read(1024 * 1024):
        total += len(chunk)
        if total > MAX_CORE_DOWNLOAD_BYTES:
            raise ChainProxyError("sing-box 下载或解压内容超过安全大小限制")
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
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                ),
            )
        except (OSError, subprocess.TimeoutExpired):
            downloaded = None
        if downloaded and downloaded.returncode == 0:
            actual_size = os.path.getsize(destination)
            if actual_size != expected_size:
                raise ChainProxyError(
                    f"sing-box 下载不完整：预期 {expected_size} 字节，"
                    f"实际 {actual_size} 字节"
                )
            hasher = hashlib.sha256()
            with open(destination, "rb") as archive:
                while chunk := archive.read(1024 * 1024):
                    hasher.update(chunk)
            actual_digest = hasher.hexdigest()
            if actual_digest.lower() != expected_digest.lower():
                raise ChainProxyError("sing-box 下载文件 SHA-256 校验失败")
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
                        raise ChainProxyError("sing-box 下载内容超过安全大小限制")
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
                f"sing-box 下载不完整：预期 {expected_size} 字节，"
                f"实际 {last_size} 字节，已重试 5 次"
            )
        if hasher.hexdigest().lower() != expected_digest.lower():
            raise ChainProxyError("sing-box 下载文件 SHA-256 校验失败")
        return


def _download_sing_box(base_dir):
    install_dir = os.path.join(base_dir, ".sing-box")
    os.makedirs(install_dir, exist_ok=True)
    archive_path = executable_temp = ""
    try:
        request = Request(
            SING_BOX_RELEASE_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "BestCfCdn",
            },
        )
        with urlopen(request, timeout=30) as response:
            release_bytes = response.read(1024 * 1024 + 1)
        if len(release_bytes) > 1024 * 1024:
            raise ChainProxyError("sing-box 发布信息超过安全大小限制")
        release = json.loads(release_bytes.decode("utf-8"))
        if not isinstance(release, dict) or not isinstance(
            release.get("assets"), list
        ):
            raise ChainProxyError("sing-box 官方发布信息格式无效")
        version = str(release.get("tag_name", "")).removeprefix("v")
        version_parts = version.split(".")
        if (
            len(version_parts) < 2
            or not all(part.isdigit() for part in version_parts)
            or tuple(map(int, version_parts[:2])) < (1, 13)
        ):
            raise ChainProxyError("sing-box 官方稳定版版本信息无效或低于 1.13")

        asset_name, executable_name = _sing_box_asset(version)
        asset = next(
            (
                item
                for item in release["assets"]
                if isinstance(item, dict)
                if item.get("name") == asset_name
            ),
            None,
        )
        if not asset:
            raise ChainProxyError(f"sing-box 官方发布缺少当前设备资产：{asset_name}")
        download_url = str(asset.get("browser_download_url", ""))
        parsed_url = urlsplit(download_url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != "github.com"
            or not parsed_url.path.startswith(
                "/SagerNet/sing-box/releases/download/"
            )
        ):
            raise ChainProxyError("sing-box 官方资产下载地址无效")
        digest = str(asset.get("digest", ""))
        if not digest.startswith("sha256:") or len(digest) != 71:
            raise ChainProxyError("sing-box 官方资产缺少有效 SHA-256 摘要")
        expected_size = asset.get("size")
        if (
            not isinstance(expected_size, int)
            or expected_size <= 0
            or expected_size > MAX_CORE_DOWNLOAD_BYTES
        ):
            raise ChainProxyError("sing-box 官方资产大小信息无效")

        archive = tempfile.NamedTemporaryFile(
            prefix="download-", suffix=f"-{asset_name}", dir=install_dir, delete=False
        )
        archive_path = archive.name
        archive.close()
        _download_verified_asset(
            download_url, archive_path, expected_size, digest[7:]
        )

        executable = tempfile.NamedTemporaryFile(
            prefix="sing-box-", dir=install_dir, delete=False
        )
        executable_temp = executable.name
        with executable:
            if asset_name.endswith(".zip"):
                with zipfile.ZipFile(archive_path) as bundle:
                    members = [
                        name
                        for name in bundle.namelist()
                        if not name.endswith("/")
                        and name.replace("\\", "/").rsplit("/", 1)[-1]
                        == executable_name
                    ]
                    if len(members) != 1:
                        raise ChainProxyError("sing-box 压缩包内的可执行文件不唯一")
                    with bundle.open(members[0]) as source:
                        _copy_limited(source, executable)
            else:
                with tarfile.open(archive_path, "r:gz") as bundle:
                    members = [
                        member
                        for member in bundle.getmembers()
                        if member.isfile()
                        and member.name.replace("\\", "/").rsplit("/", 1)[-1]
                        == executable_name
                    ]
                    if len(members) != 1:
                        raise ChainProxyError("sing-box 压缩包内的可执行文件不唯一")
                    with bundle.extractfile(members[0]) as source:
                        _copy_limited(source, executable)

        mode = os.stat(executable_temp).st_mode
        os.chmod(
            executable_temp,
            mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
        )
        target = os.path.join(install_dir, executable_name)
        if not os.path.isfile(target):
            try:
                os.replace(executable_temp, target)
                executable_temp = ""
            except PermissionError:
                if not os.path.isfile(target):
                    raise
        return target
    except ChainProxyError:
        raise
    except (
        OSError,
        URLError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        tarfile.TarError,
        zipfile.BadZipFile,
    ) as exc:
        raise ChainProxyError(f"自动下载 sing-box 失败：{exc}") from exc
    finally:
        for path in (archive_path, executable_temp):
            if path:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass


def resolve_sing_box_path(configured_path="", base_dir=None):
    requested = str(configured_path or "").strip()
    if requested:
        expanded = os.path.expanduser(os.path.expandvars(requested))
        if base_dir and not os.path.isabs(expanded):
            expanded = os.path.join(base_dir, expanded)
        expanded = os.path.abspath(expanded)
        if os.path.isfile(expanded):
            return expanded
        found = shutil.which(requested)
    else:
        found = shutil.which("sing-box")
    if found:
        return found

    project_dir = os.path.abspath(base_dir or PROJECT_ROOT)
    executable_name = "sing-box.exe" if platform.system() == "Windows" else "sing-box"
    local_path = os.path.join(project_dir, ".sing-box", executable_name)
    if os.path.isfile(local_path):
        return local_path
    print("未找到 sing-box，正在根据当前设备下载官方稳定版...")
    local_path = _download_sing_box(project_dir)
    print(f"sing-box 已安装到：{local_path}")
    return local_path


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


class SingBoxRuntime:
    def __init__(self, core_path, template, candidates, temp_parent=None):
        self.core_path = core_path
        self.proxy_ports = allocate_local_ports(candidates)
        self.config = build_sing_box_config(template, self.proxy_ports)
        self.temp_parent = temp_parent
        self._temp = None
        self._process = None
        self._log = None

    @staticmethod
    def _creationflags():
        return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    def _redact(self, message):
        text = str(message or "")
        for outbound in self.config["outbounds"]:
            for value in (outbound.get("uuid"), outbound["transport"].get("path")):
                if value:
                    text = text.replace(value, "***")
        return text.strip()[-500:]

    def __enter__(self):
        self._temp = tempfile.TemporaryDirectory(
            prefix="bestcfcdn-chain-", dir=self.temp_parent
        )
        config_path = os.path.join(self._temp.name, "config.json")
        log_path = os.path.join(self._temp.name, "sing-box.log")
        with open(config_path, "w", encoding="utf-8", newline="\n") as file:
            json.dump(self.config, file, ensure_ascii=False)
        try:
            os.chmod(config_path, 0o600)
        except OSError:
            pass

        try:
            checked = subprocess.run(
                [self.core_path, "check", "-c", config_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                creationflags=self._creationflags(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.__exit__(None, None, None)
            raise ChainProxyError("无法执行 sing-box 配置检查") from exc
        if checked.returncode:
            detail = self._redact(checked.stderr or checked.stdout)
            self.__exit__(None, None, None)
            raise ChainProxyError(f"sing-box 配置检查失败：{detail or '未知错误'}")

        self._log = open(log_path, "w+", encoding="utf-8")
        try:
            self._process = subprocess.Popen(
                [self.core_path, "run", "-c", config_path],
                stdout=self._log,
                stderr=self._log,
                creationflags=self._creationflags(),
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
            raise ChainProxyError(f"sing-box 启动失败：{detail or '监听端口未就绪'}")
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
