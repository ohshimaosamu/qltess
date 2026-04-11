#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
次の仕様のようなTESSデータの光度曲線を表示するpythonコード"plot_lcfits.py"を書いてください。
（１）まず、表示するlcfitsファイルを選択できるように、コマンドライン引数で指定するTIC番号のlcfitsファイルの一覧を、選択指定するための通し番号付きで表示する。ここでは、先程書いてもらった*lc.fitsをダウンロードするコードが作成したディレクトリ./(TIC_ID)/mastDownload/TESS/にあるlcfitsサブディレクトリ名を示せばよい
（２）選択番号で選ばれたlcfitsを光度曲線表示する。横軸をBJD,縦軸をPDCSAP_FLUX(もしデータがなければSAP_FLUX)で。縦軸の表題は"PDCSAP_FLUX"または"SAP_FLUX"で。
（３）ユーザーがplotを消したら、残りのlcfitsの一覧または終了を表示し、選択を促す。
"""
import sys
import os
import re
import glob

from astropy.io import fits
import numpy as np
import matplotlib.pyplot as plt


def normalize_tic(tic_text):
    """
    TIC番号文字列を正規化して整数値にする。
    例:
      120016
      000120016
      TIC120016
      TIC 120016
    のどれでも受け付ける。
    """
    s = str(tic_text).strip().upper()
    s = s.replace("TIC", "").strip()
    if not re.fullmatch(r"\d+", s):
        raise ValueError("TIC番号は数字で指定してください。例: 120016 / TIC120016")
    return int(s)


def find_lc_dirs(tic_id):
    """
    ./TICxxxx/mastDownload/TESS/ 以下の lc.fits を含むサブディレクトリ一覧を返す。
    返値: (base_dir, [(subdir_name, fits_path), ...])
    """
#    base_dir = os.path.join(".", f"TIC{tic_id}", "mastDownload", "TESS")
    base_dir = os.path.join(".", f"TIC{tic_id}", "mastDownload", "HLSP")
    if not os.path.isdir(base_dir):
        return base_dir, []

    entries = []
    subdirs = sorted(glob.glob(os.path.join(base_dir, "*")))

    for d in subdirs:
        if not os.path.isdir(d):
            continue
        fits_list = sorted(glob.glob(os.path.join(d, "*lc.fits")))
        for fp in fits_list:
            subdir_name = os.path.basename(d)
            entries.append((subdir_name, fp))

    return base_dir, entries


def read_lightcurve(fits_path):
    """
    lcfits を読み、BJD相当の時刻配列と flux を返す。
    flux は PDCSAP_FLUX を優先し、無ければ SAP_FLUX。
    戻り値:
      x, y, ylabel
    """
    with fits.open(fits_path) as hdul:
        data = hdul[1].data
        hdr0 = hdul[0].header
        hdr1 = hdul[1].header

        colnames = [c.upper() for c in data.columns.names]

        if "TIME" not in colnames:
            raise RuntimeError("TIME 列が見つかりません。")

        time_data = np.array(data["TIME"], dtype=float)

        bjdrefi = hdr1.get("BJDREFI", hdr0.get("BJDREFI", 0.0))
        bjdreff = hdr1.get("BJDREFF", hdr0.get("BJDREFF", 0.0))
        bjdref = float(bjdrefi) + float(bjdreff)

        x = time_data + bjdref

        ylabel = None
        if "PDCSAP_FLUX" in colnames:
            y = np.array(data["PDCSAP_FLUX"], dtype=float)
            ylabel = "PDCSAP_FLUX"
        elif "SAP_FLUX" in colnames:
            y = np.array(data["SAP_FLUX"], dtype=float)
            ylabel = "SAP_FLUX"
        else:
            raise RuntimeError("PDCSAP_FLUX も SAP_FLUX も見つかりません。")

        mask = np.isfinite(x) & np.isfinite(y)
        x = x[mask]
        y = y[mask]

        if len(x) == 0:
            raise RuntimeError("有効なデータ点がありません。")

        return x, y, ylabel


def plot_lightcurve(fits_path, subdir_name):
    x, y, ylabel = read_lightcurve(fits_path)

    plt.figure(figsize=(10, 5))
    plt.plot(x, y, ".", markersize=2)
    plt.xlabel("BJD")
    plt.ylabel(ylabel)
    plt.title(subdir_name)
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def print_menu(entries, shown_flags):
    print("")
    print("表示する lcfits を選んでください")
    print("--------------------------------------------------")
    any_left = False
    for i, (subdir_name, fits_path) in enumerate(entries, start=1):
        if not shown_flags[i - 1]:
            print("{:3d} : {}".format(i, subdir_name))
            any_left = True
    print("  q : 終了")
    print("--------------------------------------------------")
    return any_left


def main():
    if len(sys.argv) != 2:
        print("使い方:")
        print("  python plot_lcfits.py TIC番号")
        print("")
        print("例:")
        print("  python plot_lcfits.py 120016")
        print("  python plot_lcfits.py TIC120016")
        print("  python plot_lcfits.py 000120016")
        sys.exit(1)

    try:
        tic_id = normalize_tic(sys.argv[1])
    except Exception as e:
        print("TIC番号の解釈に失敗しました: {}".format(e))
        sys.exit(1)

    base_dir, entries = find_lc_dirs(tic_id)

    if not entries:
        print("lc.fits が見つかりません。")
        print("探した場所: {}".format(base_dir))
        sys.exit(1)

    shown_flags = [False] * len(entries)

    while True:
        any_left = print_menu(entries, shown_flags)
        if not any_left:
            print("未表示の lcfits はありません。終了します。")
            break

        sel = input("選択番号または q を入力してください: ").strip()

        if sel.lower() == "q":
            print("終了します。")
            break

        if not sel.isdigit():
            print("番号または q を入力してください。")
            continue

        idx = int(sel)
        if idx < 1 or idx > len(entries):
            print("範囲外の番号です。")
            continue

        if shown_flags[idx - 1]:
            print("その番号の lcfits は既に表示済みです。未表示のものを選んでください。")
            continue

        subdir_name, fits_path = entries[idx - 1]

        try:
            plot_lightcurve(fits_path, subdir_name)
            shown_flags[idx - 1] = True
        except Exception as e:
            print("表示に失敗しました: {}".format(e))


if __name__ == "__main__":
    main()
