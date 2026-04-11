#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
追加機能：./TICxxxx/ 以下に *_lc.fits が既にあるか確認し、あればダウンロードを飛ばす
　　　　　--redownload オプションを追加
　　　　　ファイルダウンロード保存先がOS非依存で~/tess_data/になるようにした
"""
import sys
import os
import re
import glob
import argparse
import warnings
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.ticker import ScalarFormatter

from astropy.io import fits
from astropy.coordinates import SkyCoord
import astropy.units as u

from astroquery.simbad import Simbad
import lightkurve as lk

# ============================================================
# utility
# ============================================================
def get_default_data_dir():
    """
    既定の保存先: ~/tess_data
    Windowsでも Path.home() が適切に解決される
    """
    return Path.home() / "tess_data"
    
def is_tic_like(text):
    s = str(text).strip().upper()
    s = s.replace("TIC", "").strip()
    return bool(re.fullmatch(r"\d+", s))


def normalize_tic(tic_text):
    s = str(tic_text).strip().upper()
    s = s.replace("TIC", "").strip()
    if not re.fullmatch(r"\d+", s):
        raise ValueError("TIC番号は数字で指定してください。例: 120016 / TIC120016")
    return int(s)


def sanitize_filename(text):
    s = str(text)
    s = re.sub(r'[\\/:*?"<>|]+', "_", s)
    s = re.sub(r"\s+", "_", s.strip())
    return s


# ============================================================
# SIMBAD name -> TIC
# ============================================================

def resolve_name_to_tic(target_name):
    """
    SIMBAD名からTIC番号を得る。
    まず Identifiers から TIC cross-id を直接探す。
    """
    try:
        ids_tab = Simbad.query_objectids(target_name)
    except Exception:
        ids_tab = None

    if ids_tab is not None and len(ids_tab) > 0:
        id_col = None
        for c in ids_tab.colnames:
            if c.lower() == "id":
                id_col = c
                break

        if id_col is not None:
            for row in ids_tab:
                s = str(row[id_col]).strip()

                m = re.match(r"^TIC\s+(\d+)$", s, re.IGNORECASE)
                if m:
                    tic_id = int(m.group(1))
                    return tic_id, None, None

                m = re.search(r"\bTIC\s+(\d+)\b", s, re.IGNORECASE)
                if m:
                    tic_id = int(m.group(1))
                    return tic_id, None, None

    sim = Simbad()
    sim.add_votable_fields("ra(d)", "dec(d)")
    result = sim.query_object(target_name)

    if result is None or len(result) == 0:
        raise RuntimeError(f"SIMBADで天体名を解決できませんでした: {target_name}")

    ra_col = None
    dec_col = None
    for c in result.colnames:
        cl = c.lower()
        if cl == "ra_d":
            ra_col = c
        elif cl == "dec_d":
            dec_col = c

    if ra_col is None or dec_col is None:
        raise RuntimeError(f"SIMBADから座標列を取得できませんでした。得られた列: {result.colnames}")

    ra_deg = float(result[ra_col][0])
    dec_deg = float(result[dec_col][0])
    coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")

    raise RuntimeError(
        f"SIMBAD identifiers にTICが見つかりませんでした: {target_name} "
        f"(RA={ra_deg:.8f}, DEC={dec_deg:.8f})"
    )


# ============================================================
# download
# ============================================================

def download_tess_lc_for_tic(tic_id, download_root=".", prefer_authors=None):
    """
    TIC番号に対応する TESS light curve FITS を lightkurve 経由で取得する。
    SPOC / TESS-SPOC / QLP を順に試す。
     保存先: ~/tess_data/TICxxxx/
    """
    if prefer_authors is None:
        prefer_authors = ["SPOC", "TESS-SPOC", "QLP"]

    # 既定: ~/tess_data
    if download_root is None:
        download_root = get_default_data_dir()

    base = Path(download_root)
    base.mkdir(parents=True, exist_ok=True)  # ~/tess_data を作る

    outdir = base / f"TIC{tic_id}"
    outdir.mkdir(parents=True, exist_ok=True)

    target = f"TIC {tic_id}"
    print(f"[INFO] target: {target}")
    print(f"[INFO] download dir: {outdir}")

    total_downloaded = 0
    any_found = False

    warnings.filterwarnings(
        "ignore",
        message="Because of their large size, Astroquery should not be used to download TESS FFI products."
    )
    warnings.filterwarnings(
        "ignore",
        message="Warning: the tpfmodel submodule is not available without oktopus installed.*"
    )

    for author in prefer_authors:
        try:
            sr = lk.search_lightcurve(target, mission="TESS", author=author)
        except Exception as e:
            print(f"[WARN] search failed for author={author}: {e}")
            continue

        n = len(sr)
        print(f"[INFO] author={author}: {n} entries found")

        if n == 0:
            continue

        any_found = True

        try:
            collection = sr.download_all(download_dir=str(outdir))
            if collection is None:
                print(f"[WARN] author={author}: download_all() returned None")
                continue

            try:
                downloaded_now = len(collection)
            except Exception:
                downloaded_now = 0

            total_downloaded += downloaded_now
            print(f"[INFO] author={author}: downloaded {downloaded_now} files")

        except Exception as e:
            print(f"[WARN] download failed for author={author}: {e}")
            continue

    if not any_found:
        print("[INFO] search_lightcurve では light curve が見つかりませんでした。")
    else:
        print(f"[INFO] total downloaded entries: {total_downloaded}")

    return outdir


# ============================================================
# file discovery
# ============================================================

def find_lc_dirs(tic_id, root=None):
    """
    ./TICxxxx/ 以下を再帰探索して *_lc.fits を拾う。
    HLSP, QLP, SPOC などをまとめて拾う。
    """
    if root is None:
        root = get_default_data_dir()

    base_dir = Path(root) / f"TIC{tic_id}"
    if not base_dir.is_dir():
        return str(base_dir), []
        
    if not os.path.isdir(base_dir):
        return base_dir, []

    patterns = [
        os.path.join(base_dir, "**", "*_lc.fits"),
        os.path.join(base_dir, "**", "*lc.fits"),
    ]

    found = []
    for pat in patterns:
        found.extend(glob.glob(pat, recursive=True))

    fits_list = sorted(set(found))

    entries = []
    for fp in fits_list:
        rel = os.path.relpath(fp, base_dir)
        parent = os.path.dirname(rel)
        display_name = parent if parent != "." else os.path.basename(fp)
        entries.append((display_name, fp))

    return base_dir, entries


def count_local_lc_files(tic_id, root=None):
    _, entries = find_lc_dirs(tic_id, root=root)
    return len(entries)


# ============================================================
# FITS read
# ============================================================

def read_lightcurve(fits_path):
    with fits.open(fits_path) as hdul:
        if len(hdul) < 2 or hdul[1].data is None:
            raise RuntimeError("FITS extension 1 にテーブルデータがありません。")

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

        order = np.argsort(x)
        x = x[order]
        y = y[order]

        return x, y, ylabel


def robust_ylim(y, low=1.0, high=99.0, pad_frac=0.08):
    if len(y) == 0:
        return None

    y1 = np.nanpercentile(y, low)
    y2 = np.nanpercentile(y, high)

    if not np.isfinite(y1) or not np.isfinite(y2):
        y1 = np.nanmin(y)
        y2 = np.nanmax(y)

    if y1 == y2:
        delta = abs(y1) * 0.01 if y1 != 0 else 1.0
        return y1 - delta, y2 + delta

    pad = (y2 - y1) * pad_frac
    return y1 - pad, y2 + pad


# ============================================================
# menu
# ============================================================

def print_menu(entries, shown_flags):
    print("")
    print("表示する lcfits を選んでください")
    print("--------------------------------------------------")
    any_left = False
    for i, (subdir_name, fits_path) in enumerate(entries, start=1):
        if not shown_flags[i - 1]:
            print(f"{i:3d} : {subdir_name}")
            any_left = True
    print("  q : 終了")
    print("--------------------------------------------------")
    return any_left


# ============================================================
# formatter
# ============================================================

class IntOffsetFormatter(ScalarFormatter):
    def get_offset(self):
        s = super().get_offset()
        if not s:
            return s

        txt = s.replace(" ", "")
        try:
            m = re.match(r'([+-]?\d+(?:\.\d+)?)(?:e([+-]?\d+))?', txt)
            if m:
                base = float(m.group(1))
                exp = int(m.group(2)) if m.group(2) is not None else 0
                val = int(round(base * (10 ** exp)))
                if val >= 0:
                    return f"+{val}"
                return str(val)
        except Exception:
            pass

        return s


# ============================================================
# scanner
# ============================================================

class LCScanner:
    def __init__(
        self,
        x,
        y,
        ylabel,
        title,
        window_days=1.0,
        speed_days_per_sec=0.5,
        interval_ms=100,
        intermittent=False,
        save_dir="snapshots",
        target_label="",
        tic_id=None
    ):
        self.x = x
        self.y = y
        self.ylabel = ylabel
        self.title = title
        self.window_days = float(window_days)
        self.speed_days_per_sec = float(speed_days_per_sec)
        self.interval_ms = int(interval_ms)
        self.paused = False
        self.finished = False
        self.intermittent = intermittent
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.target_label = target_label
        self.tic_id = tic_id

        self.tmin = float(np.min(self.x))
        self.tmax = float(np.max(self.x))

        self.current_left = self.tmin - self.window_days

        if self.intermittent:
            self.interval_ms = 500
            self.step_days = self.speed_days_per_sec * 0.5
        else:
            self.step_days = self.speed_days_per_sec * (self.interval_ms / 1000.0)

        self.fig, self.ax = plt.subplots(figsize=(11, 5.5))
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)

        self.ax.plot(self.x, self.y, ".", markersize=2)
        self.ax.set_xlabel("BJD")
        self.ax.set_ylabel(self.ylabel)
        self.ax.set_title(self.make_title())
        self.ax.grid(True)

        ylim = robust_ylim(self.y)
        if ylim is not None:
            self.ax.set_ylim(*ylim)

        self.ax.set_xlim(self.current_left, self.current_left + self.window_days)

        fmt = IntOffsetFormatter(useOffset=True)
        fmt.set_scientific(False)
        self.ax.xaxis.set_major_formatter(fmt)

        self.status_text = self.ax.text(
            0.01, 0.98, "",
            transform=self.ax.transAxes,
            ha="left", va="top",
            fontsize=11,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.7)
        )

        self.help_text = self.ax.text(
            0.99, 0.98,
            "space: pause/resume  s: save(when paused)  ←/→: move  q: close",
            transform=self.ax.transAxes,
            ha="right", va="top",
            fontsize=9,
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.5)
        )

        self.anim = FuncAnimation(
            self.fig,
            self.update,
            interval=self.interval_ms,
            blit=False,
            cache_frame_data=False
        )

        self.fig.canvas.draw()
        try:
            off = self.ax.xaxis.get_offset_text()
            off.set_horizontalalignment("center")
            off.set_x(0.72)
            off.set_y(-0.08)
        except Exception:
            pass

    def make_title(self):
        mode = "PAUSE" if self.paused else "SCAN"
        return (
            f"{self.title}   "
            f"[window={self.window_days:.3f} day, speed={self.speed_days_per_sec:.3f} day/s, {mode}]"
        )

    def save_current_window(self):
        left = self.current_left
        right = self.current_left + self.window_days

        target_part = sanitize_filename(self.target_label) if self.target_label else "target"
        tic_part = f"TIC{self.tic_id}" if self.tic_id is not None else "TICunknown"
        title_part = sanitize_filename(self.title)

        fname = (
            f"{target_part}__{tic_part}__{title_part}"
            f"__BJD_{int(round(left))}_{int(round(right))}.png"
        )
        out = self.save_dir / fname

        self.fig.savefig(out, dpi=150, bbox_inches="tight")
        self.status_text.set_text(f"SAVED: {out}")
        self.fig.canvas.draw_idle()
        print(f"[INFO] saved: {out}")

    def on_key(self, event):
        if event.key == " ":
            self.paused = not self.paused
            self.ax.set_title(self.make_title())
            if self.paused:
                self.status_text.set_text("PAUSED  (space: resume, s: save)")
            else:
                self.status_text.set_text("")
            self.fig.canvas.draw_idle()

        elif event.key == "s":
            if self.paused:
                self.save_current_window()

        elif event.key in ("q", "escape"):
            self.finished = True
            plt.close(self.fig)

        elif event.key == "right":
            self.current_left += self.window_days * 0.2
            max_left = self.tmax - self.window_days
            if self.current_left > max_left:
                self.current_left = max_left
            self.ax.set_xlim(self.current_left, self.current_left + self.window_days)
            self.fig.canvas.draw_idle()

        elif event.key == "left":
            self.current_left -= self.window_days * 0.2
            min_left = self.tmin - self.window_days
            if self.current_left < min_left:
                self.current_left = min_left
            self.ax.set_xlim(self.current_left, self.current_left + self.window_days)
            self.fig.canvas.draw_idle()

    def update(self, frame):
        if self.finished:
            return

        if not self.paused:
            self.current_left += self.step_days

            max_left = self.tmax - self.window_days
            if self.current_left > max_left:
                self.current_left = max_left
                self.paused = True
                self.status_text.set_text("END  (left/right key to inspect, s: save, q/ESC to close)")
                self.ax.set_title(self.make_title())
            else:
                self.status_text.set_text("")

            self.ax.set_xlim(self.current_left, self.current_left + self.window_days)

        return

    def show(self):
        print("")
        print("操作:")
        print("  space : 一時停止 / 再開")
        print("  s     : 一時停止中の現在窓をPNG保存")
        print("  ← →   : 表示窓を少し戻す / 進める")
        print("  q,ESC : このプロットを閉じる")
        plt.tight_layout()
        plt.show()


def scan_lightcurve(
    fits_path,
    subdir_name,
    window_days,
    speed_days_per_sec,
    intermittent,
    save_dir,
    target_label,
    tic_id
):
    x, y, ylabel = read_lightcurve(fits_path)
    scanner = LCScanner(
        x=x,
        y=y,
        ylabel=ylabel,
        title=subdir_name,
        window_days=window_days,
        speed_days_per_sec=speed_days_per_sec,
        intermittent=intermittent,
        save_dir=save_dir,
        target_label=target_label,
        tic_id=tic_id
    )
    scanner.show()


# ============================================================
# main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="TESS lc.fits quick-look downloader + scanner"
    )
    parser.add_argument(
        "target",
        help='TIC番号またはSIMBAD名。例: 11480757  または  "AM Leo"'
    )
    parser.add_argument(
        "-s", "--speed",
        type=float,
        default=0.5,
        help="スキャン速度 [day/sec] (default: 0.5)"
    )
    parser.add_argument(
        "-w", "--window",
        type=float,
        default=1.0,
        help="表示窓幅 [day] (default: 1.0)"
    )
    parser.add_argument(
        "--intermittent",
        action="store_true",
        help="間欠表示モード (0.5秒ごとに進める)"
    )
    parser.add_argument(
        "--save-dir",
        default="snapshots",
        help="sキーで保存するPNGの保存先ディレクトリ (default: snapshots)"
    )
    parser.add_argument(
        "--redownload",
        action="store_true",
        help="既存ローカルファイルがあっても再ダウンロードする"
    )

    args = parser.parse_args()

    if args.speed <= 0:
        print("スキャン速度 -s は正の値にしてください。")
        sys.exit(1)

    if args.window <= 0:
        print("窓幅 -w は正の値にしてください。")
        sys.exit(1)

    target_input = args.target.strip()

    try:
        if is_tic_like(target_input):
            tic_id = normalize_tic(target_input)
            coord = None
            row = None
            print(f"[INFO] input interpreted as TIC: {tic_id}")
        else:
            print(f"[INFO] input interpreted as SIMBAD object name: {target_input}")
            tic_id, coord, row = resolve_name_to_tic(target_input)
            print(f"[INFO] resolved TIC: {tic_id}")
            if coord is not None:
                print(f"[INFO] SIMBAD coord: RA={coord.ra.deg:.8f} deg  DEC={coord.dec.deg:.8f} deg")
            else:
                print("[INFO] TIC was resolved directly from SIMBAD identifiers.")
    except Exception as e:
        print(f"[ERROR] TIC解決に失敗しました: {e}")
        sys.exit(1)
    data_root = get_default_data_dir()

    local_count_before = count_local_lc_files(tic_id, root=data_root)
    if local_count_before > 0:
        print(f"[INFO] local lc.fits files found: {local_count_before}")

    if args.redownload:
        download_tess_lc_for_tic(tic_id, download_root=data_root)
    else:
        if local_count_before > 0:
            print(f"[INFO] 既存のローカルデータを使用します: {data_root / f'TIC{tic_id}'}")
        else:
            download_tess_lc_for_tic(tic_id, download_root=data_root)

    base_dir, entries = find_lc_dirs(tic_id, root=data_root)
    final_count = len(entries)
    print(f"[INFO] usable lc.fits files: {final_count}")

    if not entries:
        print("lc.fits が見つかりません。")
        print(f"探した場所: {base_dir}")
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
            scan_lightcurve(
                fits_path=fits_path,
                subdir_name=subdir_name,
                window_days=args.window,
                speed_days_per_sec=args.speed,
                intermittent=args.intermittent,
                save_dir=args.save_dir,
                target_label=target_input,
                tic_id=tic_id
            )
            shown_flags[idx - 1] = True
        except Exception as e:
            print(f"表示に失敗しました: {e}")


if __name__ == "__main__":
    main()
