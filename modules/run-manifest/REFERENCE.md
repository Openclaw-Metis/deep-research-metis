# run-manifest 模組

記錄一次研究走到哪裡，讓中斷後可以續跑，也讓「檢查過了」這句話可以被核對。

## 函數

### `run-manifest.write_manifest`

- 能力：合併階段狀態、gate 結果與產物 digest，並保存三項驗證的狀態快照，維持可續跑的 run manifest。
- Use when：每完成一個階段。
- Avoid when：想用它覆蓋真實的 FAIL 結果。
- 規則：`check_structure`、`check_citations`、`check_claim_support` 記錄的 PASS／FAIL 必須與驗證產物一致，否則以 `manifest.gate-status-mismatch` 拒絕。函數被 guard 阻擋而沒有產物時記為 `BLOCKED`。已完成階段不得在未明示 `allow_downgrade` 時被降級。

## Playbook：`run-resume`

- 專家任務：依 `run_manifest.json` 判斷中斷後該從哪個階段續跑，並如實記錄續跑結果。
- 允許工具：`run-manifest.write_manifest`
- 選擇規則：使用者說研究中斷、要接著做時採用；工作區沒有 manifest 時改用 `full-research-report` 或 `evidence-intake` 重新開始。
- 前置條件：`run_dir` 內有 `run_manifest.json`。
- 執行步驟：先讀 `run_manifest.json`，比對 `artifacts` digest 與 `verification` 快照；只把未完成或產物已變動的階段排入續跑，交回對應 playbook 的函數；完成後以 `run-manifest.write_manifest` 記錄實際結果。
- 成功條件：已完成且產物未變動的階段不重跑；manifest 的 gate 結果與驗證產物一致。
- 替代方案：報告 digest 已變動時把 `verification` 階段標為待重跑。
- 替代政策：runtime 不可用時交棒；函數失敗時停止；成功條件未達成時停止。
- 停止條件：manifest 無法解析，或使用者要求把 FAIL 記成 PASS。

## 執行依據

- 六個階段的完成條件是判斷續跑起點的依據：[methodology](../../references/methodology.md)。
- 呼叫前先確認函數狀態與 digest 綁定：[tool registry](../../tools/registry.json)。
- 參數、語意規則與 result policy 以函數 contract 為準：[write_manifest contract](../../tools/contracts/run-manifest.write_manifest.json)。
- Python 入口與環境 allowlist 以 runtime metadata 為準：[write_manifest runtime](../../tools/runtime/run-manifest.write_manifest.json)。
- 修改狀態或 gate 核對規則時要同步檢查功能分組 module：[run manifest](../../scripts/run_manifest.py)。
- 所有函數都經共用 runner 以 JSON stdin／stdout 呼叫：[run function](../../scripts/run_function.py)。
- 修改後以決定性軌跡確認矛盾的 gate 仍會被拒絕：[tool execution traces](../../assets/evals/tool-execution-traces.json)。
