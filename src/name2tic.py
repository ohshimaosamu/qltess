#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import re
import subprocess
from pathlib import Path
from astroquery.simbad import Simbad


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


def locate_tic_dirs(tic_id):
    """
    locate を使って TICxxxx という名前のディレクトリ候補を探す。
    返り値: 見つかったディレクトリのフルパス一覧
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
        raise RuntimeError("locate コマンドが見つかりません。mlocate/plocate をインストールしてください。")

    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr.strip() or "locate の実行に失敗しました。")

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]

    # 同名ファイルも拾う可能性があるので、実在するディレクトリだけ残す
    dirs = []
    for line in lines:
        p = Path(line)
        if p.is_dir() and p.name == target_dirname:
            dirs.append(str(p.resolve()))

    # 重複除去
    dirs = sorted(set(dirs))
    return dirs


def main():
    if len(sys.argv) != 2:
        print('Usage: python name2tic.py "OBJECT NAME"')
        sys.exit(1)

    target_name = sys.argv[1].strip()

    try:
        tic_id = resolve_name_to_tic(target_name)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"TIC {tic_id}")

    try:
        paths = locate_tic_dirs(tic_id)
    except Exception as e:
        print(f"LOCATE ERROR: {e}")
        sys.exit(1)

    if paths:
        print("Found directories:")
        for p in paths:
            print(p)
    else:
        print(f'No directory found for "TIC{tic_id}"')
        print("必要なら先に sudo updatedb を実行してください。")


if __name__ == "__main__":
    main()
