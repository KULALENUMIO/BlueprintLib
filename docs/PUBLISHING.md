# 公開手順チェックリスト

## 0. 事前に決めること

- [x] GitHub のリポジトリ：`KULALENUMIO/BlueprintLib`（Public）
- [x] ライセンス：**MIT**（改造・再配布・商用利用は自由。著作権表示とライセンス文を残すことだけが条件）
- [ ] Workshop の最初の公開範囲（いきなり公開するか、まず「非公開」や「フレンドのみ」で確認するか）

## 1. GitHub

1. GitHub で空のリポジトリを作ります（README・.gitignore・ライセンスは追加しない）
2. このフォルダでコミットしてプッシュします
   ```bat
   git init
   git add .
   git commit -m "Blueprint Lib 1.0.0"
   git branch -M main
   git remote add origin https://github.com/<ユーザー名>/<リポジトリ名>.git
   git push -u origin main
   ```
   `.gitignore` で、個人データ（`Mod/Data/*.json`）・キャッシュ・ログ・`dist/` は除外されます。
3. `python tools\release.py zip` で `dist\BlueprintLib-1.0.0.zip` を作り、GitHub の **Releases → Draft a new release**（タグ `v1.0.0`）に添付して公開します
4. `docs\workshop_description.txt` の GitHub の URL が、リポジトリを指していることを確認します

## 2. Steam Workshop

1. **ゲームを閉じて**から、個人データとキャッシュを退避します
   ```bat
   python tools\release.py prepare-upload
   ```
   最後に「OK - ready to upload」と出れば準備完了です（`preview.jpg` の確認も含まれます）。マネージャー（`Blueprint Lib Manager.bat` と `Manager/`）も MOD の一部としてアップロードされます
2. **Scrap Mechanic Mod Tool** を起動し、「Blueprint Lib」を選んで **Upload To Steam** を押します
   - 最初は公開範囲を「非公開」か「フレンドのみ」にして確認すると安全です
3. アップロード後、Mod Tool が `Mod/description.json` に `fileId` を書き込みます。この変更もコミットしておきます
4. Workshop のページで次を設定します
   - 説明文：`docs\workshop_description.txt` の内容を貼り付けます（Steam の BBCode 形式）
   - 画像：`docs\images\keyart.jpg` を追加画像としてアップロードします。ゲーム内メニューのスクリーンショットもあると伝わりやすくなります
   - タグ：Blocks and Parts / Creative など
5. 退避したデータを戻します
   ```bat
   python tools\release.py restore
   ```
   マネージャーを起動しても自動で戻ります

## 3. 公開後の確認

- 開発用のリンク（`Mods\Blueprint Lib` → このフォルダ）と、Workshop で購読したものを**同時に有効にしない**でください。どちらも同じ `localId` なので、ゲームが二重に読み込みます
- 購読者の環境の確認：開発用のリンクを外した状態で購読し、`steamapps\workshop\content\387990\<ID>` に `Blueprint Lib Manager.bat` と `Manager` フォルダが届いていること、その `.bat` から起動したマネージャーで「再スキャン」できることを確認します

## 4. 更新するとき

1. `VERSION` を上げ、変更点を Release ノートに書きます
2. `prepare-upload` → Mod Tool で同じアイテムを更新 → `restore`
3. `release.py zip` → GitHub の Release に添付します

利用者の `library.json` は、Workshop の更新で消えても、マネージャーの起動時に `%APPDATA%\BlueprintLib` から復元されます。

## 画像

| ファイル | 用途 |
|---|---|
| `Mod/preview.jpg` | **Workshop のサムネイル**（16:9、1920×1080）。一覧で小さく表示されるので、背景と「BLUEPRINT LIB」の文字だけにしています。ゲーム内の MOD 一覧にも使われます |
| `docs/images/keyart.jpg` | **紹介画像**。Workshop のページに追加画像としてアップロードし、GitHub の README にも使います |
| `docs/images/manager.jpg` | マネージャーの画面（架空のデータ） |

紹介画像に写っている作品は、`tools/demo/` で作った架空のものです（あなたのブループリントは写りません）。

作り直す手順：
```bat
rem サムネイル（文字だけ）
python tools\make_preview.py Mod\preview.jpg

rem 紹介画像（架空の作品を表示するデモ用サーバーで撮影）
python tools\demo\voxel_icons.py %TEMP%\bl_icons
start python tools\demo\demo_server.py %TEMP%\bl_icons
msedge --headless=new --window-size=1920,1080 --virtual-time-budget=9000 --screenshot=%TEMP%\shot.png "http://127.0.0.1:47990/#view=L&scope=%%2Aall&select=demo-buggy,demo-truck,demo-tank"
python tools\make_preview.py docs\images\keyart.jpg --style keyart --screenshot %TEMP%\shot.png
```
マネージャーの URL の `#view=…&scope=…&select=…` で、表示形式・フォルダ・選択した状態を指定できます。
