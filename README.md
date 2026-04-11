# qltess
天体名からTESSの測光データを探してダウンロードし、光度曲線を表示し、自動でスクロールする。古いql_tesslcの更新版

読み方は「キューエルテス」くらいでしょうか。

## 何が新しくなったか
　一番の違いは、データを保存するディレクトリが、カレントディレクトリ（実行したディレクトリなので不定）から~/tess_data/（固定）になりました。これにより、どのディレクトリで実行してもデータが保存される場所は１箇所になり集中管理できるようになりました。
 
 次に、OS非依存にしたことで、Linux / macOS / Windows（PowerShell）すべてで同じ動作になるはずです。(私はMacを持っていないためにMacでは未確認ですが、不具合があればご連絡ください)

 最後の違いは、名前が短くなった。
 
 
## 最も簡単な使い方（変光星名 UV Cet の例）
```
 python3 qltess.py "UV Cet"
```
または、_(アンダースコア)を利用して星名中にスペース文字が入らないようにすれば、全体を""でくくる必要がなくなります。また大文字小文字も無視されます。おすすめは全小文字＋アンダースコアで、次のよう入力が楽になります。
```
 python3 qltess.py uv_cet
```
 Windowsの場合は、コマンドプロンプトよりもWindows Power Shellで実行することをおすすめします。

ある場面。複数のフレアが出現しているのがわかる。

![UV Cet](images/ex_uv_cet1.png)

[実行例：自動スクロールする様子の動画](https://www.youtube.com/watch?v=tNV-A5AJE_U)

次のように何も引数を付けなければ、オプションなどの使い方が表示される。
```
python3 qltess.py

usage: qltess.py [-h] [-s SPEED] [-w WINDOW] [--intermittent]
                    [--save-dir SAVE_DIR] [--redownload]
                    target
```
-hをつけると日本語で少し丁寧な説明になります
```
$ python ~/python_prog/tess/qltess.py -h
/home/o2/miniconda3/lib/python3.13/site-packages/lightkurve/prf/__init__.py:7: UserWarning: Warning: the tpfmodel submodule is not available without oktopus installed, which requires a current version of autograd. See #1452 for details.
  warnings.warn(
usage: qltess.py [-h] [-s SPEED] [-w WINDOW] [--intermittent]
                 [--save-dir SAVE_DIR] [--redownload]
                 target

TESS lc.fits quick-look downloader + scanner

positional arguments:
  target               TIC番号またはSIMBAD名。例: 11480757 または "AM Leo"

options:
  -h, --help           show this help message and exit
  -s, --speed SPEED    スキャン速度 [day/sec] (default: 0.5)
  -w, --window WINDOW  表示窓幅 [day] (default: 1.0)
  --intermittent       間欠表示モード (0.5秒ごとに進める)
  --save-dir SAVE_DIR  sキーで保存するPNGの保存先ディレクトリ (default: snapshots)
  --redownload         既存ローカルファイルがあっても再ダウンロードする

```

# 必要なpythonライブラリ

numpy, matplotlib, astropy, astroquery, lightkurve 

# 実行するディレクトリ（フォルダー）
実行すると自動でダウンロードしたTESSの*_lc.fitsファイルは~/tess_data/ディレクトリに保存される。
Windows PowerShellの場合は、C:\Users\YourName\tess_data\ になる

# 実行例（Linux）
```
$ python ~/python_prog/ql_tesslc.py "UV Cet"

/home/xxx/xxx/lib/python3.13/site-packages/lightkurve/prf/__init__.py:7: UserWarning: Warning: the tpfmodel submodule is not available without oktopus installed, which requires a current version of autograd. See #1452 for details.

  warnings.warn(
[INFO] input interpreted as SIMBAD object name: UV Cet

[INFO] resolved TIC: 632499595

[INFO] TIC was resolved directly from SIMBAD identifiers.

[INFO] target: TIC 632499595

[INFO] download dir: ./TIC632499595

[INFO] author=SPOC: 4 entries found

[INFO] author=SPOC: downloaded 4 files

[INFO] author=TESS-SPOC: 1 entries found

[INFO] author=TESS-SPOC: downloaded 1 files

[INFO] author=QLP: 2 entries found

[INFO] author=QLP: downloaded 2 files

[INFO] total downloaded entries: 7


表示する lcfits を選んでください

--------------------------------------------------

  1 : mastDownload/HLSP/hlsp_qlp_tess_ffi_s0030-0000000632499595_tess_v01_llc
  
  2 : mastDownload/HLSP/hlsp_qlp_tess_ffi_s0097-0000000632499595_tess_v01_llc
  
  3 : mastDownload/HLSP/hlsp_tess-spoc_tess_phot_0000000632499595-s0030_tess_v1_tp
  
  4 : mastDownload/TESS/tess2020266004630-s0030-0000000632499595-0195-a_fast
  
  5 : mastDownload/TESS/tess2020266004630-s0030-0000000632499595-0195-s
  
  6 : mastDownload/TESS/tess2025258001959-s0097-0000000632499595-0294-a_fast
  
  7 : mastDownload/TESS/tess2025258001959-s0097-0000000632499595-0294-s
  
  q : 終了
  
--------------------------------------------------

選択番号または q を入力してください: 6
```
以上を実行した時の様子
![scan lightcurve](images/scan_UV_Cet6.mp4)


# name2tic.py
先に一度ql_tesslcを使ったら、その星のlcfitsファイルはすでに手元にダウンロードされています。
次にじっくりとその光度曲線を調べてみたいと思ったら収められているディレクトリをTIC番号で探さなければならない。
これは不便なので、このソフトを作りました。
名前を引数として与えれば、TIC番号が表示され、さらにLinuxの場合は、そのディレクトリが合う場所を探し出してフルパス表示してくれる（前提：locateコマンドをインストールして、sudo updatedaを実行してある）。


# plot_lcfits.py

先に一度ql_tesslcを使ったら、その星のlcfitsファイルはすでに手元にダウンロードされています。
じっくりとその光度曲線を調べてみたいと思ったら、もうql_tesslcを使わず、この"plot_lcfits.py"を使えば、
光度曲線を表示してくれます。

このグラフは、虫めがねアイコンをクリックしてマウスで範囲指定すれば、自由に拡大できます。
元のスケールに戻したい時は、家マークのアイコンをクリック。
