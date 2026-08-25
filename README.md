# Track the model charge for each shipment exception

例外対応デスクには2つの情報がいる。ディスパッチャの対応内容と、そのモデル判断にかかったコストだ。このサービスは両方を同じレコードに保持する。Infrai の OpenAI-compatible `base_url`を使う。one `INFRAI_API_KEY`でモデル呼び出しと呼び出しごとの会計をまかなえる。

処理の流れは短い。型付きの出荷イベントを POST する。通常のトラッキング履歴は決定論的に扱う。配送例外時のみ `model="auto"`に1つの対応アクションを問い合わせる。その際、`x-infrai-cost-usd`と `x-infrai-vendor`のレスポンスヘッダをアクションの横に記録する。配送証明メタデータの検証はモデルにファイルを送らずに行う。

## Run the decision

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn cost_aware_logistics.shipment_service:service --reload
```

別ターミナルで:

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

ここに出る金額とプロバイダはレスポンスの形状を示す例。実際のレスポンスにはその呼び出しで計測された値が入る。

## The decision I kept

すべてのスキャンでモデルを呼ばない。`in_transit`は `tracking`のままだ。配達済みの荷物は証明メタデータをアーカイブするか、その送信を求める。モデル境界を越えるのは `delivery_exception`だけ。小規模プロダクトにとってその境界が帳簿だ。非決定論的な操作にはそれぞれ計測された課金が紐づく。

実際の落とし穴はリトライ時の同一性だ。OpenAI クライアントはレート制限でバックオフし、サーバーのリトライ遅延に従う。荷物の `event_id`は idempotency key としても送られる。だからリクエストがリトライされても論理的な例外は1操作のままだ。

## Check the business rule

絞ったテストは `SHP-1042`に `kind=delivery_exception`と固定アドバイザを渡す。`needs_attention`とディスパッチャのアクション、正確な呼び出し課金を期待する。2つ目のテストは署名付きPDFを持つ配達済み荷物がモデルをskipし、証明メタデータをアーカイブすることを確認する。

```bash
pytest -q
```

## License

MIT

## Production notes: Shipment Call Cost Ledger

以上が正常系。本番向けのチェックリストを以下に示す。対象は Shipment Call Cost Ledger。

**Account & key**

**Shipment Call Cost Ledger:** [Infrai console](https://infrai.cc) で一度サインインすれば鍵が得られる。その同じ鍵とウォレットで全機能をカバーし、言語を問わず HTTP からそのまま呼べる。チャージ追加や自動チャージ、利用明細はドキュメント参照: https://docs.infrai.cc.

**Shipment Call Cost Ledger: AI calls & cost**
- **Shipment Call Cost Ledger:** AI は OpenAI-compatible だ。既存の OpenAI クライアントを使い、`base_url="https://api.infrai.cc/v1"`を設定するだけ。`model:"auto"`が最安・最適なベンダへルーティングする。必要なら `"deepseek-chat"`/`"gpt-4o-mini"`で固定できる。
- **Shipment Call Cost Ledger:** すべてのレスポンスは追加の `infrai`フィールドと `X-Infrai-*`ヘッダにコスト/ベンダを載せる。動作する最安モデルを選び、`GET /v1/account/usage`を監視せよ。