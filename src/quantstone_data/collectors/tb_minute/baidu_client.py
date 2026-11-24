from __future__ import annotations

import os
from pathlib import Path

from ..wind_l2_sz.baidu import _cookies  # reuse cookie parsing


def _load_setting(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value.strip()
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == name and value.strip():
                return value.strip()
    return None


def _api():
    try:
        from baidupcs_py.baidupcs import BaiduPCSApi
    except ImportError as error:
        raise RuntimeError(
            "分钟采集器缺少 BaiduPCS-Py，请安装项目的 wind-l2 可选依赖"
        ) from error
    cookie = _load_setting("MINUTE_BAIDUPCS_COOKIE") or _load_setting(
        "WIND_L2_BAIDUPCS_COOKIE"
    )
    if not cookie:
        raise RuntimeError("未配置 WIND_L2_BAIDUPCS_COOKIE")
    os.environ["WIND_L2_BAIDUPCS_COOKIE"] = cookie
    bduss, cookies = _cookies()
    return BaiduPCSApi(bduss=bduss, cookies=cookies)


def download_path(remote_path: str, target: Path) -> Path:
    try:
        import requests
        from baidupcs_py.baidupcs.pcs import PCS_UA
    except ImportError as error:
        raise RuntimeError(
            "分钟采集器缺少 BaiduPCS-Py 或 requests，请安装项目的 wind-l2 可选依赖"
        ) from error

    api = _api()
    metadata = api.meta(remote_path)
    if not metadata or not metadata[0].is_file:
        raise FileNotFoundError(f"百度网盘文件不存在：{remote_path}")
    remote_size = metadata[0].size
    if target.is_file() and target.stat().st_size == remote_size:
        return target
    dlink = api.download_link(remote_path)
    if not dlink:
        raise RuntimeError(f"无法获取百度网盘下载地址：{remote_path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    partial.unlink(missing_ok=True)
    headers = {"User-Agent": PCS_UA, "Connection": "Keep-Alive"}
    with requests.get(
        dlink,
        headers=headers,
        cookies=api.cookies,
        stream=True,
        timeout=(30, 120),
    ) as response:
        response.raise_for_status()
        written = 0
        with partial.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                written += len(chunk)
    if written != remote_size:
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"百度网盘文件下载不完整：{remote_path}，期望 {remote_size}，实际 {written}"
        )
    os.replace(partial, target)
    return target
