# real-estate-ai-assistant

不動産の問い合わせを自動で対応するMVPアプリです。

機能
- 物件一覧の表示
- お問い合わせフォーム
- AI風の自動返信（ルールベース）
- 物件登録画面
- 管理画面で問い合わせ履歴確認
- SQLiteによるデータ保存
- 公式LINE Bot連携

起動手順
1. `python3 -m venv .venv`
2. `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `cp .env.example .env` し、LINEのチャンネル情報を設定
5. `python app.py`
6. ブラウザで `http://localhost:5000` を開く

LINE連携の設定
- LINE Developers Console で Messaging API チャネルを作成
- Channel Secret と Channel access token を取得
- `.env.example` の内容を `.env` にコピーして値をセット
- ローカル開発時は ngrok などで公開URLを作成し、Webhook URL を設定

例:
- `LINE_CHANNEL_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- `LINE_CHANNEL_ACCESS_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

Webhook URL
- `https://<your-ngrok-url>/line/webhook`

主な画面
- トップページ: `/`
- 管理画面: `/admin`
- 物件追加: `/properties/new`

開発方針
- まずはローカルで動くMVPを作成
- LINE連携でリアルタイムに問い合わせ対応できるように拡張
- 後でOpenAI API連携、予約管理、顧客管理を追加可能

