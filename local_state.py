"""Resolve local-only runtime files without overlapping GitHub aggregate data."""

import os


DEFAULT_LOCAL_OUTPUT_FILE = "ip.local.txt"
DEFAULT_REMOTE_OUTPUT_FILE = "ip.txt"


def _absolute_project_path(path, config_path):
    if os.path.isabs(path):
        return os.path.normpath(path)
    project_dir = os.path.dirname(os.path.abspath(config_path))
    return os.path.normpath(os.path.join(project_dir, path))


def resolve_local_output(config, config_path, warning_callback=None):
    """Return an absolute local output path that cannot alias the remote aggregate."""
    output_value = str(config.get("OUTPUT_FILE", DEFAULT_LOCAL_OUTPUT_FILE)).strip()
    if not output_value:
        output_value = DEFAULT_LOCAL_OUTPUT_FILE

    output_path = _absolute_project_path(output_value, config_path)
    remote_value = str(
        config.get("GITHUB_SYNC_REMOTE_PATH", DEFAULT_REMOTE_OUTPUT_FILE)
    ).strip()
    if remote_value and not os.path.isabs(remote_value):
        remote_path = _absolute_project_path(remote_value, config_path)
        if os.path.normcase(output_path) == os.path.normcase(remote_path):
            output_path = _absolute_project_path(DEFAULT_LOCAL_OUTPUT_FILE, config_path)
            if warning_callback:
                warning_callback(
                    f"OUTPUT_FILE 与远端汇总文件 {remote_value} 重名，"
                    f"已自动改用本机文件 {DEFAULT_LOCAL_OUTPUT_FILE}"
                )
    return output_path
