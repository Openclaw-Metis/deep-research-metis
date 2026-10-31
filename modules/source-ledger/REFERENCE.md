# source-ledger 模組

來源身分的唯一持有者。任何要被引用的來源都先在這裡取得穩定的 `source_id`。

## 函數

### `source-ledger.register_sources`

- 能力：只接受 http(s) 來源，拒絕 userinfo credential，正規化網址、指派穩定 `source_id`、合併重複來源並記錄諮詢性權威訊號。
- Use when：任何來源要被引用之前，或 `check_citations` 回報 `source_not_registered`。
- Avoid when：來源沒有可追溯網址，應先取得原始出處。
- 規則：網址 query 中的 credential 參數在持久化前移除；中文路徑與百分比編碼視為同一來源；`primary`、`secondary`、`community` 層級以完整網域比對，只是諮詢訊號，不得單獨用來否決主張。

## Playbook：`source-registration`

- 專家任務：把新找到的來源補進既有 run 的來源帳本，完成去重與身分指派。
- 允許工具：`source-ledger.register_sources`、`run-manifest.write_manifest`
- 選擇規則：使用者只要補登來源，或要修正 `source_not_registered` 時採用；同時要持久化逐字引文時改用 `evidence-intake`；要完整報告時改用 `full-research-report`。
- 前置條件：`run_dir` 可寫入；每個來源都有 http(s) 網址與標題。
- 執行步驟：先以 `source-ledger.register_sources` 批次登錄，再回報 `registered`、`duplicates` 與被移除的 credential 參數，最後以 `run-manifest.write_manifest` 記錄 `retrieval` 階段狀態。
- 成功條件：每個要被引用的來源都取得 `source_id`；manifest 的 `retrieval` 階段狀態與實際結果一致。
- 替代方案：來源沒有可追溯網址時列出缺口，請使用者提供原始出處。
- 替代政策：runtime 不可用時交棒；函數失敗時停止；成功條件未達成時停止。
- 停止條件：來源沒有可追溯網址，或網址含 userinfo credential、不是 http(s)。

## 執行依據

- 呼叫前先確認函數狀態與 digest 綁定：[tool registry](../../tools/registry.json)。
- 參數、語意規則與 result policy 以函數 contract 為準：[register_sources contract](../../tools/contracts/source-ledger.register_sources.json)。
- Python 入口與環境 allowlist 以 runtime metadata 為準：[register_sources runtime](../../tools/runtime/source-ledger.register_sources.json)。
- 修改身分與層級規則時要同步檢查功能分組 module：[source ledger](../../scripts/source_ledger.py)。
- 所有函數都經共用 runner 以 JSON stdin／stdout 呼叫：[run function](../../scripts/run_function.py)。
- 修改後以決定性軌跡確認去重與 redaction 仍成立：[tool execution traces](../../assets/evals/tool-execution-traces.json)。
