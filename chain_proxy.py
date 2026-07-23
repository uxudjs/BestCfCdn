"""CfGfwAX 链式订阅解析与临时 sing-box 运行时。"""

import base64
import ipaddress
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, unquote, unquote_plus, urlsplit, urlunsplit
import hashlib
import io
import platform
import tarfile
import zipfile
from urllib.request import Request, urlopen


class ChainProxyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChainTemplate:
    uuid: str
    server_name: str
    host: str
    path: str
    flow: str = ""
    insecure: bool = False


def sing_box_subscription_url(subscription_url):
    """Return a request-only URL that asks CfGfwAX for native sing-box JSON."""
    try:
        parsed = urlsplit(str(subscription_url or "").strip())
    except ValueError as exc:
        raise ChainProxyError("CHAIN_PROXY_SUBSCRIPTION_URL 无效") from exc
    if not parsed.scheme or not parsed.netloc:
        raise ChainProxyError("CHAIN_PROXY_SUBSCRIPTION_URL 无效")

    rewritten = []
    target_added = False
    for field in parsed.query.split("&") if parsed.query else []:
        if unquote_plus(field.partition("=")[0]) == "target":
            if not target_added:
                rewritten.append("target=singbox")
                target_added = True
        else:
            rewritten.append(field)
    if not target_added:
        rewritten.append("target=singbox")
    return urlunsplit(parsed._replace(query="&".join(rewritten)))


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
    server_name = (query.get("sni") or query.get("host") or "").lower()
    host = (query.get("host") or server_name).lower()
    path = query.get("path", "")
    if expected_domain not in (server_name, host) or "/video/" not in path:
        return None
    if query.get("security", "").lower() != "tls":
        return None
    if query.get("type", "").lower() != "ws":
        return None
    if query.get("ech") or query.get("fragment"):
        raise ChainProxyError("链式测速暂不支持 ECH 或 TLS 分片模板")
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
    )


def _feature_enabled(value):
    if isinstance(value, dict):
        return value.get("enabled", True) is not False
    return bool(value)


def _parse_sing_box_template(outbound, expected_domain):
    if not isinstance(outbound, dict) or outbound.get("type") != "vless":
        return None
    tls = outbound.get("tls")
    transport = outbound.get("transport")
    if not isinstance(tls, dict) or not isinstance(transport, dict):
        return None

    headers = transport.get("headers")
    if not isinstance(headers, dict):
        headers = {}
    host = next(
        (str(value).lower() for key, value in headers.items() if key.lower() == "host"),
        "",
    )
    server_name = str(tls.get("server_name") or host).lower()
    path = transport.get("path")
    if (
        expected_domain not in (server_name, host)
        or not isinstance(path, str)
        or "/video/" not in path
        or tls.get("enabled") is not True
        or str(transport.get("type", "")).lower() != "ws"
    ):
        return None
    unsupported = (
        tls.get("ech"),
        tls.get("fragment"),
        outbound.get("tls_fragment"),
        outbound.get("tls_fragmentation"),
        outbound.get("fragment"),
        transport.get("tls_fragment"),
        transport.get("fragment"),
    )
    if any(_feature_enabled(value) for value in unsupported):
        raise ChainProxyError("链式测速暂不支持 ECH 或 TLS 分片模板")

    uuid = outbound.get("uuid")
    if not isinstance(uuid, str) or not uuid:
        raise ChainProxyError("sing-box 链式模板缺少 VLESS UUID")
    _validate_chain_path(path, uuid)
    return ChainTemplate(
        uuid=uuid,
        server_name=server_name,
        host=host or server_name,
        path=path,
        flow=str(outbound.get("flow") or ""),
        insecure=tls.get("insecure") is True,
    )


def _sing_box_templates(content, expected_domain):
    text = (content or "").lstrip("\ufeff").strip()
    if not text.startswith(("{", "[")):
        return None
    try:
        config = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ChainProxyError("sing-box JSON 订阅格式无效") from exc
    if not isinstance(config, dict) or not isinstance(config.get("outbounds"), list):
        raise ChainProxyError("sing-box JSON 订阅缺少 outbounds")
    return {
        template
        for outbound in config["outbounds"]
        if (template := _parse_sing_box_template(outbound, expected_domain))
        is not None
    }


def extract_chain_template(subscription_content, subscription_url):
    """归并同一逻辑配置的多条 CfGfwAX 地址，并拒绝歧义模板。"""
    try:
        expected_domain = (urlsplit(subscription_url).hostname or "").lower()
    except ValueError as exc:
        raise ChainProxyError("CHAIN_PROXY_SUBSCRIPTION_URL 无效") from exc
    if not expected_domain:
        raise ChainProxyError("CHAIN_PROXY_SUBSCRIPTION_URL 缺少域名")

    templates = _sing_box_templates(subscription_content, expected_domain)
    if templates is None:
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
        outbound = {
            "type": "vless",
            "tag": outbound_tag,
            "server": server,
            "server_port": server_port,
            "uuid": template.uuid,
            "network": "tcp",
            "tls": {
                "enabled": True,
                "server_name": template.server_name,
                "insecure": template.insecure,
            },
            "transport": {
                "type": "ws",
                "path": template.path,
                "headers": {"Host": template.host},
            },
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
    return {
        "log": {"level": "warn", "timestamp": False},
        "inbounds": inbounds,
        "outbounds": outbounds,
        "route": {"rules": rules},
    }


def _local_sing_box_path(base_dir=None, system_name=None):
    filename = (
        "sing-box.exe"
        if (system_name or platform.system()).lower() == "windows"
        else "sing-box"
    )
    return os.path.abspath(
        os.path.join(
            base_dir or os.path.dirname(__file__), ".runtime", "sing-box", filename
        )
    )


def _select_release_asset(release, system_name=None, machine=None):
    system_key = (system_name or platform.system()).lower()
    machine_key = (machine or platform.machine()).lower()
    systems = {"windows": ("windows", ".zip"), "linux": ("linux", ".tar.gz")}
    architectures = {
        "amd64": "amd64",
        "x86_64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    if system_key not in systems or machine_key not in architectures:
        raise ChainProxyError(
            f"当前平台不支持自动安装 sing-box：{system_name or platform.system()} "
            f"{machine or platform.machine()}"
        )
    release_system, extension = systems[system_key]
    suffix = f"-{release_system}-{architectures[machine_key]}{extension}"
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise ChainProxyError("sing-box 官方发布资产列表无效")
    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and str(asset.get("name", "")).startswith("sing-box-")
        and str(asset.get("name", "")).endswith(suffix)
    ]
    if len(matches) != 1:
        raise ChainProxyError(f"官方发布中未找到唯一的 sing-box 资产：*{suffix}")
    return matches[0]

_RELEASE_API = "https://api.github.com/repos/SagerNet/sing-box/releases/latest"
_MAX_RELEASE_BYTES = 4 * 1024 * 1024
_MAX_ARCHIVE_BYTES = 128 * 1024 * 1024


def _read_url(opener, url, limit):
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "BestCfCdn-sing-box-setup",
        },
    )
    try:
        with opener(request, timeout=30) as response:
            content = response.read(limit + 1)
    except (OSError, ValueError) as exc:
        raise ChainProxyError("无法下载 sing-box 官方发布信息或资产") from exc
    if len(content) > limit:
        raise ChainProxyError("sing-box 官方发布信息或资产超过大小限制")
    return content


def _download_verified_archive(opener, system_name, machine):
    try:
        release = json.loads(_read_url(opener, _RELEASE_API, _MAX_RELEASE_BYTES))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ChainProxyError("sing-box 官方发布信息不是有效 JSON") from exc
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        raise ChainProxyError("sing-box 最新发布不是稳定版本")

    asset = _select_release_asset(release, system_name, machine)
    digest = str(asset.get("digest", ""))
    expected = digest[7:].lower() if digest.startswith("sha256:") else ""
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise ChainProxyError("sing-box 官方资产缺少有效 SHA-256 摘要")
    download_url = str(asset.get("browser_download_url", ""))
    parsed = urlsplit(download_url)
    if parsed.scheme != "https" or parsed.hostname != "github.com" or not parsed.path.startswith(
        "/SagerNet/sing-box/releases/download/"
    ):
        raise ChainProxyError("sing-box 官方资产下载地址无效")

    archive = _read_url(opener, download_url, _MAX_ARCHIVE_BYTES)
    if hashlib.sha256(archive).hexdigest() != expected:
        raise ChainProxyError("sing-box 官方资产 SHA-256 校验失败")
    return asset["name"], archive


def _safe_archive_name(name, executable):
    normalized = str(name).replace("\\", "/")
    parts = normalized.split("/")
    return (
        not normalized.startswith("/")
        and parts[-1] == executable
        and all(part not in ("", ".", "..") and ":" not in part for part in parts)
    )


def _extract_core(archive_name, archive, system_name):
    executable = "sing-box.exe" if str(system_name).lower() == "windows" else "sing-box"
    try:
        if archive_name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(archive)) as package:
                candidates = []
                for member in package.infolist():
                    if str(member.filename).replace("\\", "/").split("/")[-1] != executable:
                        continue
                    file_type = (member.external_attr >> 16) & 0o170000
                    if (
                        not _safe_archive_name(member.filename, executable)
                        or member.is_dir()
                        or file_type not in (0, 0o100000)
                    ):
                        raise ChainProxyError("sing-box 归档包含不安全的可执行文件成员")
                    candidates.append(member)
                if len(candidates) != 1:
                    raise ChainProxyError("sing-box 归档未包含唯一的可执行文件")
                if candidates[0].file_size > _MAX_ARCHIVE_BYTES:
                    raise ChainProxyError("sing-box 可执行文件超过大小限制")
                with package.open(candidates[0]) as extracted:
                    content = extracted.read(_MAX_ARCHIVE_BYTES + 1)
        elif archive_name.endswith(".tar.gz"):
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
                candidates = []
                for member in package.getmembers():
                    if str(member.name).replace("\\", "/").split("/")[-1] != executable:
                        continue
                    if not _safe_archive_name(member.name, executable) or not member.isfile():
                        raise ChainProxyError("sing-box 归档包含不安全的可执行文件成员")
                    candidates.append(member)
                if len(candidates) != 1:
                    raise ChainProxyError("sing-box 归档未包含唯一的可执行文件")
                extracted = package.extractfile(candidates[0])
                content = extracted.read(_MAX_ARCHIVE_BYTES + 1) if extracted else b""
        else:
            raise ChainProxyError("sing-box 官方资产归档格式无效")
    except (zipfile.BadZipFile, tarfile.TarError, OSError) as exc:
        raise ChainProxyError("sing-box 官方资产归档损坏") from exc
    if not content or len(content) > _MAX_ARCHIVE_BYTES:
        raise ChainProxyError("sing-box 可执行文件为空或超过大小限制")
    return content


def _check_sing_box(core_path):
    try:
        checked = subprocess.run(
            [core_path, "version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ChainProxyError("无法执行 sing-box 版本检查") from exc
    output = f"{checked.stdout}\n{checked.stderr}".lower()
    if checked.returncode or "sing-box" not in output:
        raise ChainProxyError("sing-box 版本检查失败")


def _stage_config(config_path, config):
    descriptor, temporary = tempfile.mkstemp(
        prefix=".config-sing-box-", suffix=".tmp", dir=os.path.dirname(config_path)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            json.dump(config, file, ensure_ascii=False, indent=4)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary, os.stat(config_path).st_mode & 0o777)
        return temporary
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def prepare_sing_box(config_path, *, opener=None, system_name=None, machine=None):
    config_path = os.path.abspath(os.fspath(config_path))
    try:
        with open(config_path, "r", encoding="utf-8-sig") as file:
            config = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ChainProxyError("无法读取 config.json") from exc
    if not isinstance(config, dict):
        raise ChainProxyError("config.json 顶层必须是对象")
    if config.get("CHAIN_PROXY_TEST_ENABLED") is not True:
        return None

    base_dir = os.path.dirname(config_path)
    local_path = _local_sing_box_path(base_dir, system_name)
    candidates = []
    requested = str(config.get("CHAIN_PROXY_CORE_PATH", "") or "").strip()
    if requested:
        expanded = os.path.expanduser(os.path.expandvars(requested))
        candidates.append(
            os.path.abspath(os.path.join(base_dir, expanded))
            if not os.path.isabs(expanded)
            else os.path.abspath(expanded)
        )
    candidates.append(local_path)
    found = shutil.which("sing-box")
    if found:
        candidates.append(os.path.abspath(found))

    seen = set()
    for candidate in candidates:
        normalized = os.path.normcase(candidate)
        if normalized in seen or not os.path.isfile(candidate):
            continue
        seen.add(normalized)
        try:
            _check_sing_box(candidate)
        except ChainProxyError:
            continue
        config_value = (
            os.path.relpath(candidate, base_dir)
            if os.path.normcase(candidate) == os.path.normcase(local_path)
            else candidate
        )
        if config.get("CHAIN_PROXY_CORE_PATH") != config_value:
            updated = dict(config)
            updated["CHAIN_PROXY_CORE_PATH"] = config_value
            temporary = ""
            try:
                temporary = _stage_config(config_path, updated)
                os.replace(temporary, config_path)
            except OSError as exc:
                raise ChainProxyError("无法原子写入 sing-box 配置路径") from exc
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
        return candidate

    archive_name, archive = _download_verified_archive(
        opener or urlopen, system_name or platform.system(), machine or platform.machine()
    )
    core = _extract_core(archive_name, archive, system_name or platform.system())
    target_dir = os.path.dirname(local_path)
    os.makedirs(target_dir, exist_ok=True)
    descriptor, candidate_path = tempfile.mkstemp(prefix=".sing-box-", dir=target_dir)
    config_temporary = ""
    backup_path = ""
    installed = False
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(core)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(candidate_path, 0o755)
        _check_sing_box(candidate_path)

        updated = dict(config)
        updated["CHAIN_PROXY_CORE_PATH"] = os.path.relpath(local_path, base_dir)
        config_temporary = _stage_config(config_path, updated)
        if os.path.exists(local_path):
            backup_descriptor, backup_path = tempfile.mkstemp(
                prefix=".sing-box-backup-", dir=target_dir
            )
            os.close(backup_descriptor)
            os.unlink(backup_path)
            os.replace(local_path, backup_path)
        os.replace(candidate_path, local_path)
        candidate_path = ""
        installed = True
        os.replace(config_temporary, config_path)
        config_temporary = ""
        if backup_path:
            os.unlink(backup_path)
            backup_path = ""
        return local_path
    except ChainProxyError:
        raise
    except OSError as exc:
        if installed:
            try:
                os.unlink(local_path)
            except OSError:
                pass
        if backup_path:
            try:
                os.replace(backup_path, local_path)
                backup_path = ""
            except OSError as rollback_exc:
                raise ChainProxyError(
                    f"sing-box 安装失败且旧核心回滚失败；备份保留在 {backup_path}"
                ) from rollback_exc
        raise ChainProxyError("无法原子安装 sing-box 或写入配置") from exc
    finally:
        for temporary in (candidate_path, config_temporary):
            if temporary and os.path.exists(temporary):
                try:
                    os.unlink(temporary)
                except OSError:
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
    local = _local_sing_box_path(base_dir)
    if os.path.isfile(local):
        return local
    found = shutil.which(requested or "sing-box")
    if not found:
        raise ChainProxyError(
            "未找到 sing-box；请安装后加入 PATH，或设置 CHAIN_PROXY_CORE_PATH"
        )
    return found


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

    def _write_config(self, config_path):
        with open(config_path, "w", encoding="utf-8", newline="\n") as file:
            json.dump(self.config, file, ensure_ascii=False)
        try:
            os.chmod(config_path, 0o600)
        except OSError:
            pass

    def _check_config(self, config_path):
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
            raise ChainProxyError("无法执行 sing-box 配置检查") from exc
        if checked.returncode:
            detail = self._redact(checked.stderr or checked.stdout)
            raise ChainProxyError(
                f"sing-box 配置检查失败：{detail or '未知错误'}"
            )

    def check(self):
        with tempfile.TemporaryDirectory(
            prefix="bestcfcdn-chain-check-", dir=self.temp_parent
        ) as directory:
            config_path = os.path.join(directory, "config.json")
            self._write_config(config_path)
            self._check_config(config_path)

    def __enter__(self):
        self._temp = tempfile.TemporaryDirectory(
            prefix="bestcfcdn-chain-", dir=self.temp_parent
        )
        config_path = os.path.join(self._temp.name, "config.json")
        log_path = os.path.join(self._temp.name, "sing-box.log")
        self._write_config(config_path)
        try:
            self._check_config(config_path)
        except ChainProxyError:
            self.__exit__(None, None, None)
            raise

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


def check_sing_box_config(core_path, template, temp_parent=None):
    """Validate the shared chain template without starting sing-box."""
    try:
        runtime = SingBoxRuntime(
            core_path,
            template,
            ["127.0.0.1:443#PRECHECK"],
            temp_parent=temp_parent,
        )
        runtime.check()
    except OSError as exc:
        raise ChainProxyError("无法创建 sing-box 检查所需的临时配置") from exc


def _main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] != "--prepare-sing-box":
        print("usage: chain_proxy.py --prepare-sing-box CONFIG", file=sys.stderr)
        return 2
    try:
        core_path = prepare_sing_box(argv[1])
    except ChainProxyError as exc:
        print(f"❌ sing-box 准备失败：{exc}", file=sys.stderr)
        return 1
    if core_path:
        print(f"✅ sing-box 已就绪：{core_path}")
    else:
        print("ℹ️ 链式测速未启用，跳过 sing-box 准备。")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
