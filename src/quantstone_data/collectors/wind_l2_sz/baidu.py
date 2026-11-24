from __future__ import annotations

import os
import sys
from collections import deque
from datetime import date
from pathlib import Path, PurePosixPath

DEFAULT_SHARE_URL = "https://pan.baidu.com/s/1qii0cUtTuNc6HBIH0-PwJA"
DEFAULT_REMOTE_ROOT = "/quant-data/wind-l2"


def _load_library():
    default_root = Path(os.environ.get("QUANTSTONE_DATA_ROOT", Path.cwd() / "var"))
    log_path = default_root / "logs" / "baidupcs.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("LOG_PATH", str(log_path))
    scripts_dir = str(Path(sys.executable).parent)
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if scripts_dir not in path_parts:
        os.environ["PATH"] = os.pathsep.join([scripts_dir, *path_parts])
    try:
        from baidupcs_py.baidupcs import BaiduPCSApi
        from baidupcs_py.commands.download import Downloader, DownloadParams, download
        from baidupcs_py.commands.share import list_all_sub_paths
    except ImportError as error:
        raise RuntimeError(
            "Wind L2 采集器缺少 BaiduPCS-Py，请安装项目的 wind-l2 可选依赖"
        ) from error
    return BaiduPCSApi, DownloadParams, Downloader, download, list_all_sub_paths


def _cookies() -> tuple[str, dict[str, str]]:
    raw = os.environ.get("WIND_L2_BAIDUPCS_COOKIE", "").strip()
    if not raw:
        raise RuntimeError("未配置 WIND_L2_BAIDUPCS_COOKIE")
    cookies = {}
    for item in raw.split(";"):
        if "=" in item:
            name, value = item.strip().split("=", 1)
            cookies[name] = value
    if not cookies.get("BDUSS"):
        raise RuntimeError("WIND_L2_BAIDUPCS_COOKIE 缺少 BDUSS")
    return cookies["BDUSS"], cookies


def create_api():
    api_type, *_ = _load_library()
    bduss, cookies = _cookies()
    return api_type(bduss=bduss, cookies=cookies)


def _archive_name(run_date: date) -> str:
    return f"{run_date:%Y%m%d}.7z"


def _find_shared_archive(api, shared_url: str, run_date: date, password: str | None):
    *_, list_all_sub_paths = _load_library()
    if password:
        api.access_shared(shared_url, password, show_vcode=False)
    wanted_month = f"{run_date:%Y%m}"
    wanted_name = _archive_name(run_date)
    queue = deque(api.shared_paths(shared_url))
    visited: set[str] = set()
    while queue:
        item = queue.popleft()
        path = PurePosixPath(item.path)
        if item.is_file and path.name == wanted_name and path.parent.name == wanted_month:
            return item
        if not item.is_dir or item.path in visited:
            continue
        visited.add(item.path)
        if item.uk is None or item.share_id is None or item.bdstoken is None:
            raise RuntimeError(f"百度分享目录元数据不完整：{item.path}")
        queue.extend(
            list_all_sub_paths(api, item.path, item.uk, item.share_id, item.bdstoken)
        )
    return None


def ensure_archive(run_date: date, target: Path) -> Path:
    """转存并下载日压缩包；完整文件按远端大小复用。"""
    _, DownloadParams, Downloader, download, _ = _load_library()
    api = create_api()
    shared_url = os.environ.get("WIND_L2_BAIDUPCS_SHARE_URL", DEFAULT_SHARE_URL)
    password = os.environ.get("WIND_L2_BAIDUPCS_SHARE_PASSWORD") or None
    remote_root = os.environ.get("WIND_L2_BAIDUPCS_REMOTE_ROOT", DEFAULT_REMOTE_ROOT)
    remote_dir = (PurePosixPath(remote_root) / f"{run_date:%Y%m}").as_posix()
    remote_path = (PurePosixPath(remote_dir) / _archive_name(run_date)).as_posix()

    if not api.exists(remote_path):
        source = _find_shared_archive(api, shared_url, run_date, password)
        if source is None:
            raise FileNotFoundError(f"百度分享中没有 {run_date:%Y%m}/{_archive_name(run_date)}")
        current = PurePosixPath("/")
        for part in PurePosixPath(remote_dir).parts[1:]:
            current /= part
            if not api.exists(current.as_posix()):
                api.makedir(current.as_posix())
        if source.uk is None or source.share_id is None or source.bdstoken is None:
            raise RuntimeError("百度分享文件元数据不完整")
        api.transfer_shared_paths(
            remote_dir,
            [source.fs_id],
            source.uk,
            source.share_id,
            source.bdstoken,
            shared_url,
        )

    metadata = api.meta(remote_path)
    if not metadata or not metadata[0].is_file:
        raise FileNotFoundError(f"百度网盘转存文件不存在：{remote_path}")
    remote_size = metadata[0].size
    if target.is_file() and target.stat().st_size == remote_size:
        return target
    if target.exists():
        target.unlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    download(
        api,
        [remote_path],
        str(target.parent),
        downloader=Downloader.aget_py,
        downloadparams=DownloadParams(
            concurrency=int(os.environ.get("WIND_L2_DOWNLOAD_CONCURRENCY", "5")),
            chunk_size=os.environ.get("WIND_L2_DOWNLOAD_CHUNK_SIZE", "5M"),
            quiet=True,
        ),
    )
    downloaded = target.parent / PurePosixPath(remote_path).name
    if downloaded != target and downloaded.is_file():
        os.replace(downloaded, target)
    if not target.is_file() or target.stat().st_size != remote_size:
        raise RuntimeError("Wind L2 压缩包下载不完整")
    return target
