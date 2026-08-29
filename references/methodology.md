# 研究階段契約

本檔定義六個研究階段各自的完成條件與停止條件。`run-manifest.write_manifest` 只接受這六個階段名稱，因此階段語彙就是可稽核的狀態機。

## 階段與完成條件

| 階段 | 完成條件 | 產物 |
| --- | --- | --- |
| `plan` | 問題、子問題、模式預算與必要章節都已固定 | `research_plan.json` |
| `retrieval` | 已取得達到 `min_sources` 的可追溯來源，或已記錄未達標原因 | `sources.jsonl` |
| `evidence` | 每個預期引用的來源至少有一則逐字引文 | `evidence.jsonl` |
| `drafting` | 草稿完成且每個事實主張都帶行內引用 | 報告 Markdown |
| `verification` | 結構、引用與支撐度三項檢查都已執行，且三份結果綁定同一 report digest | `claims.jsonl`、`structure_check.json`、`citation_map.json`、`claim_support.json` |
| `delivery` | 交付物已產生，或已說明未取得寫入授權 | 報告 HTML、`run_manifest.json` |

## 模式預算

`research-plan.build_plan` 依模式固定檢索預算，避免無上限蒐集：`quick` 5 至 12 個來源、`standard` 10 至 25 個、`deep` 20 至 45 個、`ultradeep` 35 至 80 個。子問題數量上限同步由模式決定，超過時直接 block，要求先收斂問題再開始檢索。

## 停止條件

- 來源數量低於模式下限且無法補足時，改為部分交付並在限制章節說明缺口。
- 出現無法對應到來源的行內引用時停止，先補登來源再繼續。
- 主張支撐度不足時補證據並重跑驗證，不調高門檻或刪除檢查。
- 使用者要求把 `FAIL` 直接改寫成 `PASS` 時停止並說明原因。

## 證據品質與來源權威性

來源權威性是諮詢性訊號。`source-ledger.register_sources` 會標記 `primary`、`secondary` 或 `community` 層級，但這個層級不得單獨用來否決主張。對權威性有疑慮時，在報告中寫出受影響的主張、可能影響與建議查證方式，其餘檢查照常執行。可追溯性、授權與可驗證證據則是客觀必要條件，缺少時依對應檢查判定 `FAIL`。
