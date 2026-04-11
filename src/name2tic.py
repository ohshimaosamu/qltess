#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import re
import os
import platform
import argparse
import subprocess
from pathlib import Path

from astroquery.simbad import Simbad
"""
Linux / macOS / WindowsどれでもOK
Usage: python name2tic.py "AM Leo"
"""

def resolve_name_to_tic(target_name):
    """
    SIMBAD名からTIC番号を得る。
    Identifiers から TIC cross-id を直接探す。
    """
    try:
        ids_tab = Simbad.query_objectids(target_name)
    except Exception as e:
        raise RuntimeError(f"SIMBAD query_objectids() failed: {e}")

    if ids_tab is None or len(ids_tab) == 0:
        raise RuntimeError(f"SIMBADで天体名を解決できませんでした: {target_name}")

    id_col = None
    for c in ids_tab.colnames:
        if c.lower() == "id":
            id_col = c
            break

    if id_col is None:
        raise RuntimeError(f"SIMBADの戻り表に ID 列がありません。列名: {ids_tab.colnames}")

    for row in ids_tab:
        s = str(row[id_col]).strip()

        m = re.match(r"^TIC\s+(\d+)$", s, re.IGNORECASE)
        if m:
            return int(m.group(1))

        m = re.search(r"\bTIC\s+(\d+)\b", s, re.IGNORECASE)
        if m:
            return int(m.group(1))

    raise RuntimeError(f"SIMBAD identifiers にTIC番号が見つかりませんでした: {target_name}")


def locate_tic_dirs_unix(tic_id):
    """
    Unix系で locate を使って TICxxxx ディレクトリを探す。
    """
    target_dirname = f"TIC{tic_id}"

    try:
        result = subprocess.run(
            ["locate", "-b", f"\\{target_dirname}"],
            capture_output=True,
            text=True,
            check=False
        )
    except FileNotFoundError:
        return []

    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or "locate の実行に失敗しました。")

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    dirs = []
    for line in lines:
        p = Path(line)
        if p.is_dir() and p.name == target_dirname:
            dirs.append(str(p.resolve()))

    return sorted(set(dirs))


def recursive_find_tic_dirs(tic_id, search_roots):
    """
    OS非依存の再帰探索。
    search_roots 以下を walk して TICxxxx ディレクトリを探す。
    """
    target_dirname = f"TIC{tic_id}"
    found = []

    for root in search_roots:
        root_path = Path(root).expanduser()
        if not root_path.exists() or not root_path.is_dir():
            continue

        for dirpath, dirnames, filenames in os.walk(root_path):
            # 一致したらそのディレクトリを記録
            current = Path(dirpath)
            if current.name == target_dirname:
                found.append(str(current.resolve()))
                # その下は探索不要ならここで continue/break も可
                # 今回は複数候補を拾うため継続

    return sorted(set(found))


def locate_tic_dirs_cross_platform(tic_id, search_roots=None):
    """
    クロスプラットフォーム版。
    - Unix系: locate が使えれば使う
    - Windows: 再帰探索
    - locateが無いUnix系: 再帰探索
    """
    if search_roots is None or len(search_roots) == 0:
        # デフォルト探索場所
        home = Path.home()
        search_roots = [home]

    system_name = platform.system().lower()

    # Windows は locate を使わず再帰探索
    if "windows" in system_name:
        return recursive_find_tic_dirs(tic_id, search_roots)

    # Unix系はまず locate を試す
    try:
        paths = locate_tic_dirs_unix(tic_id)
        if paths:
            return paths
    except Exception:
        pass

    # locate が無い/見つからない場合は再帰探索
    return recursive_find_tic_dirs(tic_id, search_roots)


def main():
    parser = argparse.ArgumentParser(
        description="星名からTIC番号と、そのTICフォルダの場所を調べる"
    )
    parser.add_argument("target_name", help='例: "AM Leo"')
    parser.add_argument(
        "--search-root",
        action="append",
        default=[],
        help="TICフォルダ探索の開始ディレクトリ。複数指定可。"
    )

    args = parser.parse_args()

    target_name = args.target_name.strip()

    try:
        tic_id = resolve_name_to_tic(target_name)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"TIC {tic_id}")

    # 探索開始ディレクトリ
    if args.search_root:
        search_roots = [Path(p).expanduser() for p in args.search_root]
    else:
        # デフォルトはホーム以下
        search_roots = [Path.home()]

    try:
        paths = locate_tic_dirs_cross_platform(tic_id, search_roots=search_roots)
    except Exception as e:
        print(f"SEARCH ERROR: {e}")
        sys.exit(1)

    if paths:
        print("Found directories:")
        for p in paths:
            print(p)
    else:
        print(f'No directory found for "TIC{tic_id}"')
        if "windows" not in platform.system().lower():
            print("必要なら先に sudo updatedb を実行してください。")
        print("必要なら --search-root で探索開始ディレクトリを指定してください。")


if __name__ == "__main__":
    main()
