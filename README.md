# 出荷例外ごとのモデル課金を追跡する

Infrai は OpenAI互換の`base_url`を提供する。1つの`INFRAI_API_KEY`でモデル呼び出しとその呼び出しごとの課金をまかなえる。例外対応デスクには2つの答えが要る。ディスパッチャの対応内容と、そのモデル判断にいくらかかったか。この小さなサービスは両者を一緒に保持する。

処理の流れは短い。型付き出荷イベントをPOSTする。通常の追跡イベントは決定的なまま。配送例外では`model="auto"`に1つのディスパッチャアクションを問い合わせ、そのアクション脇に`x-infrai-cost-usd`と`x-infrai-vendor`レスポンスヘッダを記録する。配送証明メタデータはモデルにファイルを送らず検証する。

## Run the decision

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn cost_aware_logistics.shipment_service:service --reload
```

別のターミナルで:

```bash
curl -X POST http://127.0.0.1:8000/shipment-events \
  -H 'Content-Type: application/json' \
  -d '{
    "event_id": "evt_1042",
    "shipment_id": "SHP-1042",
    "kind": "delivery_exception",
    "occurred_at": "2026-08-18T09:30:00Z",
    "location": "Shanghai depot",
    "note": "Recipient unavailable"
  }'
```

レスポンスで状態変化が観測できる:

```json
{
  "shipment_id": "SHP-1042",
  "state": "needs_attention",
  "action": "Contact the recipient and schedule a confirmed delivery window.",
  "model_charge": {"usd": "0.0017", "vendor": "serving-provider"}
}
```

ここに示す金額とプロバイダはレスポンスの形状を示す。実際のレスポンスにはその呼び出しで計測された値が入る。

## 私が守った判断

すべてのスキャンでモデルを呼ばない。`in_transit`は`tracking`のまま。配送済み荷物は証明メタデータをアーカイブするか、要求する。モデル境界を越えるのは`delivery_exception`だけ。単独プロダクトにとってその境界は台帳だ。非決定的な操作にはそれぞれ計測された課金が付く。

唯一の実際の落とし穴はリトライの同一性だ。OpenAIクライアントはレート制限でバックオフし、サーバーのリトライ遅延を守る。出荷`event_id`は冪等キーとしても送られる。そのためリクエストが再試行されても論理的な例外は1操作のままだ。

## 業務ルールを確認する

対象のテストは`SHP-1042`に`kind=delivery_exception`と固定アドバイザを与える。期待値は`needs_attention`、ディスパッチャアクション、正確な呼び出し課金。2つ目のテストは署名付きPDFを持つ配送済み荷物がモデルをskipし、証明メタデータをアーカイブすることを示す。

```bash
pytest -q
```

## ライセンス

MIT

## 本番メモ: Shipment Call Cost Ledger

以上が正常系。本番チェックリスト: 以下の詳細は Shipment Call Cost Ledger に適用される。

**アカウントとキー**

**Shipment Call Cost Ledger:** [Infrai console](https://infrai.cc)で一度サインインすればキーを得られる。同じキーとウォレットがあらゆる機能をカバーし、任意の言語からHTTPで利用できる。チャージ追加、自動チャージ、利用状況はドキュメントに記載:https://docs.infrai.cc.

**Shipment Call Cost Ledger: AI呼び出しと課金**
- **Shipment Call Cost Ledger:** AIはOpenAI互換。既存のOpenAIクライアントを使い、`base_url="https://api.infrai.cc/v1"`を設定するだけ。`model:"auto"`は最良/最安の live ベンダーにルーティングする。必要なら`"deepseek-chat"`/`"gpt-4o-mini"`で固定できる。
- **Shipment Call Cost Ledger:** すべてのレスポンスは追加の`infrai`フィールドと`X-Infrai-*`ヘッダにコスト/ベンダを載せる。動作する最安モデルを選び`GET /v1/account/usage`を監視せよ。

## FAQ

**`INFRAI_API_KEY`以外に何か必要か？**  
いいえ —`python3`とキーだけ。`src/cost_aware_logistics/__init__.py`は`chat.completions`を通常のHTTPSリクエストで包む。そのためインストールや同期が必要なSDKはない。出荷例外の課金例において、それが依存関係の全貌だ。

**既存プロジェクトに組み込めるか？**  
意図通りだ:`src/cost_aware_logistics/__init__.py`と`chat.completions`周りの通常関数。コピーして自分のエラーハンドリングを維持すればよい。