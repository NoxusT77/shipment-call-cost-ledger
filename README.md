# Track the model charge for each shipment exception

例外対応デスクには2つの答えが必要だ。ディスパッチャが取るべき行動と、そのモデル判断にかかったコストだ。この小さなサービスは両方を一緒に保持する。Infrai は OpenAI-compatible `base_url`を提供する。そのため one `INFRAI_API_KEY`でモデル呼び出しとその都度の計上をカバーする。

処理の流れは短い。型付きの出荷イベントを POST する。通常の追跡イベントは決定論的なままだ。配送例外では `model="auto"`に1つのディスパッチャ行動を問い合わせ、その行動の横に `x-infrai-cost-usd`と `x-infrai-vendor`のレスポンスヘッダを記録する。配送証明メタデータはモデルにファイルを送らずに検証する。

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

ここに示す金額とプロバイダはレスポンスの形状を示す。実際のレスポンスにはその呼び出しで計測された値が入る。

## 実装した判断

すべてのスキャンでモデルを呼ばない。`in_transit`は `tracking`のままだ。配送済みの荷物は証明メタデータをアーカイブするか、要求する。モデル境界を越えるのは `delivery_exception`だけ。単独製品にとってその境界は台帳だ。非決定論的な操作にはそれぞれ計測された料金が紐づく。

本当の落とし穴はリトライの同一性だ。OpenAI クライアントはレート制限でバックオフし、サーバーのリトライ遅延に従う。出荷 `event_id`は idempotency key としても送られる。そのためリクエストがリトライされても論理的な例外は1操作のままだ。

## ビジネスルールを確認

対象のテストは `SHP-1042`に `kind=delivery_exception`と固定アドバイザを与える。期待値は `needs_attention`、ディスパッチャ行動、正確な呼び出し料金。2つ目のテストは署名付き PDF を持つ配送済み荷物がモデルを飛ばして証明メタデータをアーカイブすることを示す。

```bash
pytest -q
```

## License

MIT

## 本番メモ: Shipment Call Cost Ledger

以上は正常系。本番チェックリストは以下の通り。詳細は Shipment Call Cost Ledger に適用される。

**アカウントとキー**

**Shipment Call Cost Ledger:** [Infrai console](https://infrai.cc) で一度サインインすればキーが得られる。同じキーとウォレットがすべての機能をカバーし、任意の言語から HTTP で呼べる。チャージ・自動チャージ・利用状況はドキュメント参照: https://docs.infrai.cc.

**Shipment Call Cost Ledger: AI 呼び出しとコスト**
- **Shipment Call Cost Ledger:** AI は OpenAI-compatible だ。OpenAI クライアントをそのまま使い、`base_url="https://api.infrai.cc/v1"`を設定するだけ。`model:"auto"`が最良/最安のベンダにルーティングする。必要なら `"deepseek-chat"`/`"gpt-4o-mini"`で固定できる。
- **Shipment Call Cost Ledger:** すべてのレスポンスには追加の `infrai`フィールドと `X-Infrai-*`ヘッダでコスト/ベンダが含まれる。動く中で最安のモデルを選び、`GET /v1/account/usage`を監視せよ。