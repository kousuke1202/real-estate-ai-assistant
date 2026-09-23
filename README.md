# real-estate-ai-assistant

不動産の問い合わせを自動で対応するMVPアプリです。

機能
- 物件一覧の表示
- お問い合わせフォーム
- AI風の自動返信（OpenAIが設定されている場合はAI利用、未設定時はルールベース）
- 物件登録画面
- 管理画面で問い合わせ履歴確認
- SQLiteによるデータ保存
- 公式LINE Bot連携
- 内見予約管理
- 問い合わせ/予約時の管理者通知（Slack / メール）

起動手順
1. `python3 -m venv .venv`
2. `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `.env.example` を `.env` にコピーし、必要な値を設定
5. `python app.py`
6. ブラウザで `http://localhost:5000` を開く

環境変数
```
LINE_CHANNEL_SECRET=
LINE_CHANNEL_ACCESS_TOKEN=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
ADMIN_EMAIL=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SLACK_WEBHOOK_URL=
```

LINE連携の設定
- LINE Developers Console で Messaging API チャネルを作成
- Channel Secret と Channel access token を取得
- `.env` に設定
- ngrok などで公開URLを作成し、Webhook URL を設定

例:
- `https://<your-ngrok-url>/line/webhook`

主な画面
- トップページ: `/`
- 管理画面: `/admin`
- 物件追加: `/properties/new`
- 内見予約: `/reservations/new`

開発方針
- まずはローカルで動くMVPを作成
- LINE連携でリアルタイムに問い合わせ対応できるように拡張
- OpenAI連携で自然な回答に対応
- 管理者への通知と予約管理を追加して会社運用へ接続

