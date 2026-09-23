# real-estate-ai-assistant

不動産の問い合わせを自動で対応するMVPアプリです。

機能
- 物件一覧の表示
- 問い合わせフォーム
- AI風の自動返信（ルールベース）
- 物件登録画面
- 管理画面で問い合わせ履歴確認
- SQLiteによるデータ保存

起動手順
1. `python3 -m venv .venv`
2. `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `python app.py`
5. ブラウザで `http://localhost:5000` を開く

主な画面
- トップページ: 物件一覧と問い合わせフォーム
- 管理画面: `/admin`
- 物件追加: `/properties/new`

開発方針
- まずはローカルで動くMVPを作成
- 後でLINEやメール連携、OpenAI API連携、予約管理を拡張可能

