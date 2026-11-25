from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CatalogFile, CatalogPartition, CollectionRun

L2_DATASET_IDS = (
    "tb_xxlpd.cn.stock.l2_order.sz",
    "tb_xxlpd.cn.stock.l2_trade.sz",
    "zhongtai.cn.stock.l2_order.sz",
    "zhongtai.cn.stock.l2_trade.sz",
)
COMPACT_DATE = re.compile(r"^\d{8}$")


def _iso_date(value: str) -> str:
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def migrate_l2_directory_paths(session: Session, data_root: Path) -> int:
    """将 L2 正式目录从 YYYYMMDD 原子迁移为 YYYY-MM-DD。"""
    file_rows = list(
        session.scalars(select(CatalogFile).where(CatalogFile.dataset_id.in_(L2_DATASET_IDS)))
    )
    changes: list[tuple[CatalogFile, str, str, Path, Path]] = []
    directory_moves: dict[Path, Path] = {}
    for file_row in file_rows:
        parts = list(PurePosixPath(file_row.path).parts)
        if len(parts) < 4 or parts[0] != "datasets" or not COMPACT_DATE.fullmatch(parts[2]):
            continue
        old_path = file_row.path
        parts[2] = _iso_date(parts[2])
        new_path = PurePosixPath(*parts).as_posix()
        old_directory = data_root / PurePosixPath(*PurePosixPath(old_path).parts[:3])
        new_directory = data_root / PurePosixPath(*PurePosixPath(new_path).parts[:3])
        directory_moves[old_directory] = new_directory
        changes.append((file_row, old_path, new_path, old_directory, new_directory))

    if not changes:
        return 0
    for old_directory, new_directory in directory_moves.items():
        if not old_directory.is_dir():
            raise FileNotFoundError(f"L2 旧日期目录不存在：{old_directory}")
        if new_directory.exists():
            raise FileExistsError(f"L2 新日期目录已存在：{new_directory}")

    moved: list[tuple[Path, Path]] = []
    try:
        for old_directory, new_directory in directory_moves.items():
            os.replace(old_directory, new_directory)
            moved.append((old_directory, new_directory))
        for file_row, old_path, new_path, _, _ in changes:
            file_row.path = new_path
            for partition in session.scalars(
                select(CatalogPartition).where(CatalogPartition.file_path == old_path)
            ):
                partition.file_path = new_path
            for run in session.scalars(
                select(CollectionRun).where(CollectionRun.published_path == old_path)
            ):
                run.published_path = new_path
        session.commit()
    except Exception:
        session.rollback()
        for old_directory, new_directory in reversed(moved):
            if new_directory.exists() and not old_directory.exists():
                os.replace(new_directory, old_directory)
        raise
    return len(directory_moves)
