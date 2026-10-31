# evidence-store 模組

逐字引文的持有者，並擁有寫作前的底稿流程。驗證階段讀到的就是這裡寫入的內容。

## 函數

### `evidence-store.append_evidence`

- 能力：把逐字引文綁定到已登錄來源並以 append-only 方式持久化。
- Use when：寫作前需要固定引文內容。
- Avoid when：手上只有改寫過的摘要而非原文。
- 規則：引文要含報告會引用的數字，否則 `check_claim_support` 會回報 `claim_number_unmatched`。短於 8 字元或長於 1200 字元的引文列入 `rejected` 不寫入，呼叫後要檢查這個清單，不能只看 exit code。

## Playbook：`evidence-intake`

- 專家任務：在寫作前建立可追溯的來源身分與逐字證據底稿。
- 允許工具：`research-plan.build_plan`、`source-ledger.register_sources`、`evidence-store.append_evidence`、`run-manifest.write_manifest`
- 選擇規則：使用者要先蒐集整理、暫不產出報告時採用；已有完整證據要寫報告時改用 `full-research-report`；只要稽核既有報告時改用 `report-verification`。
- 前置條件：已知研究問題與工作區；每筆引文都能對應到具體來源網址。
- 執行步驟：先以 `research-plan.build_plan` 固定檢索預算，再以 `source-ledger.register_sources` 分批登錄來源，逐字引文經 `evidence-store.append_evidence` 寫入並附上 locator，最後以 `run-manifest.write_manifest` 記錄 `evidence` 階段狀態。
- 成功條件：來源數量達到模式下限或已記錄未達標原因、每筆證據都綁定已登錄的 `source_id`、`rejected` 清單已處理、manifest 狀態與實際結果一致。
- 替代方案：來源不足時記錄為 partial 並列出仍缺的子問題；引文過長時擷取關鍵段落並保留 locator。
- 替代政策：runtime 不可用時交棒；函數失敗時停止；成功條件未達成時停止。
- 停止條件：來源沒有可追溯網址，或引文是改寫而非原文。

## 執行依據

- 呼叫前先確認函數狀態與 digest 綁定：[tool registry](../../tools/registry.json)。
- 參數、語意規則與 result policy 以函數 contract 為準：[append_evidence contract](../../tools/contracts/evidence-store.append_evidence.json)。
- Python 入口與環境 allowlist 以 runtime metadata 為準：[append_evidence runtime](../../tools/runtime/evidence-store.append_evidence.json)。
- 修改持久化規則時要同步檢查功能分組 module：[evidence store](../../scripts/evidence_store.py)。
- 所有函數都經共用 runner 以 JSON stdin／stdout 呼叫：[run function](../../scripts/run_function.py)。
- 修改後以決定性軌跡確認語意檢查仍在呼叫前生效：[tool execution traces](../../assets/evals/tool-execution-traces.json)。
