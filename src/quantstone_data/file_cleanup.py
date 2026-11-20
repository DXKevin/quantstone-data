from pathlib import Path


def remove_empty_parent_directories(path: Path, *, stop: Path) -> int:
    """删除文件原位置留下的空父目录，但绝不删除 stop 本身或越过该边界。"""
    current = path.parent
    removed = 0
    if not current.is_relative_to(stop):
        return removed
    while current != stop:
        try:
            current.rmdir()
        except FileNotFoundError:
            pass
        except OSError:
            break
        else:
            removed += 1
        current = current.parent
    return removed
