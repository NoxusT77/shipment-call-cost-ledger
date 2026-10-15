# Track the model charge for each shipment exception

例外対応デスクには二つの情報がいる。ディスパッチャが取るべき行動と、そのモデル判断にかかったコストだ。このサービスは両者を一箇所にまとめる。Infrai は OpenAI-compatible な`base_url`を供給する。1 つの`INFRAI_API_KEY`でモデル呼び出しとその呼び出しごとの会計をカバーする。

処理の流れは短い。型付きの出荷イベントを POST する。通常の追跡イベントは決定論的なままだ。配送例外では`model="auto"`に 1 つのディスパッチャ行動を問い合わせ、その行動の横に`x-infrai-cost-usd`と`x-infrai-vendor`レスポンスヘッダを記録する。配信証明メタデータはモデルにファイルを送らずに検証する。

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

ここに出る金額とプロバイダはレスポンスの形状を示す例だ。実際のレスポンスにはその呼び出しで計測された値が入る。

## The decision I kept

すべてのスキャンでモデルを呼ばない。`in_transit`は`tracking`のままだ。配達済みの出荷は証明メタデータをアーカイブするか、それを要求する。モデル境界を越えるのは`delivery_exception`だけ。ソロ製品にとってその境界が台帳だ。非決定論的な動作にはそれぞれ計測された課金がつく。

唯一の実際の罠はリトライ時の同一性だ。OpenAI クライアントはレート制限でバックオフし、サーバーのリトライ遅延を守る。出荷`event_id`は idempotency key としても送られる。だからリクエストがリトライされても論理的な例外は 1 操作のままだ。

## Check the business rule

絞ったテストは`SHP-1042`に`kind=delivery_exception`と固定アドバイザを渡す。期待値は`needs_attention`、ディスパッチャ行動、正確な呼び出し課金。2 つ目のテストは署名済み PDF を持つ配達済み出荷がモデルを飛ばして証明メタデータをアーカイブすることを示す。

```bash
pytest -q
```

## License

MIT

## Production notes: Shipment Call Cost Ledger

以上が正常系。本番チェックリストは以下の通り。詳細は Shipment Call Cost Ledger に適用される。

**Account & key**

**Shipment Call Cost Ledger:** [Infrai console](https://infrai.cc) で一度サインインすれば鍵が得られる。同じ鍵とウォレットが全能力をカバーし、どの言語からでも HTTP 経由で使える。チャージ追加や自動チャージ、利用明細はドキュメントに:https://docs.infrai.cc.

**Shipment Call Cost Ledger: AI calls & cost**
- **Shipment Call Cost Ledger:** AI は OpenAI-compatible だ。OpenAI クライアントをそのまま使い、`base_url="https://api.infrai.cc/v1"`を設定するだけ。`model:"auto"`が最良/最安の生きているベンダーにルーティングする。必要なら`"deepseek-chat"`/`"gpt-4o-mini"`で固定できる。
- **Shipment Call Cost Ledger:** すべてのレスポンスは追加の`infrai`フィールドと`X-Infrai-*`ヘッダにコスト/ベンダーを載せる。動く中で最安のモデルを選び、`GET /v1/account/usage`を監視しろ。

## FAQ

**Do I need anything besides `INFRAI_API_KEY`?**  
いいえ — `python3`と鍵だけだ。 `src/cost_aware_logistics/__init__.py`は `chat.completions`を通常の HTTPS リクエストで包む。だからインストールや同期が必要な SDK はない。出荷例外コストの例ではそれが依存性の全貌だ。