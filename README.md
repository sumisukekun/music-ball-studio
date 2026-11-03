# music-ball-studio

音に合わせて球が跳ねる縦型ショート動画（TikTok / YouTube ショート向け）を、**設定ファイル1つ → MP4** で作るための制作環境です。
Blender（bpy）で映像を、自前のピアノ音源で音楽を作るので、使う曲は**パブリックドメイン（作曲者の死後70年以上）かオリジナル曲だけ**です。

## 中身

| フォルダ | 役割 |
|---|---|
| `songs/` | 曲を作るスクリプト。音符（時刻・音高・長さ・声部）を `arr.json` に書き出す |
| `configs/` | 動画1本 = JSON 1つ。曲・色・カメラ・音色・字幕を指定 |
| `studio/spiral_scene.py` | らせんバウンドの映像エンジン（1回のバウンド = 1音、音が高いほど高く跳ねる） |
| `studio/audio.py` | ピアノ（Salamander）・ウッドベース・ブラシドラム・リバーブで音楽を書き出す |
| `studio/make.py` | 全工程をまとめて実行：song → audio → scene → render → post |
| `archive/` | これまでに作った13本のスクリプト（ドミノ、ピタゴラ、月の光、ラスベガス、北欧、氷の城、ハンガリー舞曲、ジャズなど） |

## 使い方

### GitHub 上で作る（パソコン不要）
1. **Actions** タブ → **render** → **Run workflow**
2. `config` に `configs/midnight_spiral.json` などを入れて実行
3. 終わったら、実行結果ページの **Artifacts → video** から MP4 をダウンロード

試し撮りだけしたいときは `steps` を `song,audio,scene,preview` にすると、静止画5枚だけを書き出します（数分で終わります）。

### 手元で作る
```bash
bash scripts/setup.sh
bash scripts/fetch_samples.sh
MBS_BPY_PYTHON=.venv/bin/python .venv/bin/python studio/make.py configs/midnight_spiral.json
# → out/midnight_spiral.mp4
```
途中で止まった場合は、`--steps render,post` で続きから再開できます（書き出し済みの区間は飛ばされます）。

## 新しい動画を作る手順
1. `songs/` に曲スクリプトを追加します。出力は `{"events":[{"t","midi","dur","voice"}...], "end_music", "END"}` の形にします。
2. `configs/` の既存の JSON をコピーして、`name`・`song`・レーンの色・音色・字幕を書き換えます。
3. まず `preview` で見た目を確認し、問題なければ本番を書き出します。

## ルール
- 曲はパブリックドメインかオリジナルのみ。演奏も自前で作ります（市販の録音は使いません）。
- 収益化のため、動画の長さは **61秒以上** にします。
- ディズニー作品などのキャラクター・曲・デザインは使いません。
- 投稿は手作業で行います（取り消しにくい操作のため）。
