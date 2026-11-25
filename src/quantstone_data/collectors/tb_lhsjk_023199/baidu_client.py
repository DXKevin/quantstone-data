from __future__ import annotations

import json
import os
import re
from pathlib import Path

from ..wind_l2_sz.baidu import _cookies


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


def _share():
    share_url = _load_setting("MINUTE_SHARE_URL")
    password = _load_setting("MINUTE_SHARE_PASSWORD")
    if not share_url or not password:
        raise RuntimeError("未配置 MINUTE_SHARE_URL / MINUTE_SHARE_PASSWORD")
    try:
        from baidupcs_py.baidupcs.pcs import Method
    except ImportError as error:
        raise RuntimeError("缺少 BaiduPCS-Py") from error
    api = _api()
    api.access_shared(share_url, password, show_vcode=False)
    html = api._baidupcs._request(Method.Get, share_url, params=None).text
    match = re.search(
        r'<script id="locals-data" type="application/json">\s*(.*?)\s*</script>',
        html,
        re.S,
    )
    if not match:
        raise RuntimeError("无法解析百度分享页面")
    data = json.loads(match.group(1))
    if not data.get("file_list"):
        raise RuntimeError("百度分享没有文件")
    return api, share_url, data


def _list_shared(api, path: str, uk: int, share_id: int, token: str) -> list:
    items = []
    page = 1
    while True:
        chunk = api.list_shared_paths(
            path, uk, share_id, token, page=page, size=100
        )
        items.extend(chunk)
        if len(chunk) < 100:
            return items
        page += 1



def _download_own(remote_path: str, target: Path) -> Path:
    try:
        import requests
        from baidupcs_py.baidupcs.pcs import PCS_UA
    except ImportError as error:
        raise RuntimeError("分钟采集器缺少 BaiduPCS-Py 或 requests") from error
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
    written = 0
    with requests.get(
        dlink,
        headers={"User-Agent": PCS_UA, "Connection": "Keep-Alive"},
        cookies=api.cookies,
        stream=True,
        timeout=(30, 120),
    ) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
                    written += len(chunk)
    if written != remote_size:
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"百度网盘文件下载不完整：{remote_path}，期望 {remote_size}，实际 {written}"
        )
    os.replace(partial, target)
    return target


def fetch_shared_file(relative_path: str, target: Path, folder: str) -> Path:
    """把分享中的单个文件转存到年数据/日数据目录，下载后保留转存文件。"""
    if folder not in {"年数据", "日数据"}:
        raise ValueError(f"不支持的转存目录：{folder}")
    api, share_url, data = _share()
    uk = int(data["share_uk"])
    share_id = int(data["shareid"])
    token = data["bdstoken"]
    root_path = data["file_list"][0]["path"]
    full_relative = relative_path.strip("/")
    parent_relative, _, name = full_relative.rpartition("/")
    if not parent_relative:
        raise ValueError(f"分享路径必须包含目录：{relative_path}")
    parent = root_path + "/" + parent_relative
    source = next(
        (item for item in _list_shared(api, parent, uk, share_id, token)
         if item.path.rsplit("/", 1)[-1] == name),
        None,
    )
    if source is None:
        raise FileNotFoundError(f"分享中不存在文件：{relative_path}")

    transfer_root = _load_setting("MINUTE_TRANSFER_ROOT") or "/quant-data/A股分钟数据"
    remote_dir = transfer_root.rstrip("/") + "/" + folder
    if not api.exists(remote_dir):
        api.makedir(remote_dir)
    remote_path = remote_dir + "/" + name
    existing = api.meta(remote_path)
    if existing and existing[0].is_file and existing[0].size == source.size:
        pass
    else:
        if api.exists(remote_path):
            api.remove(remote_path)
        api.transfer_shared_paths(
            remote_dir, [source.fs_id], uk, share_id, token, share_url
        )
    _download_own(remote_path, target)
    return target
