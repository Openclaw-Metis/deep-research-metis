# claim-ledger 模組

把報告拆成可定位的主張，是三項檢查共用的輸入，也可在草稿階段單獨用來自查。

## 函數

### `claim-ledger.extract_claims`

- 能力：以中英文共用規則切分句子，抽出主張、所屬章節與引用編號，並以 report digest 綁定的原子快照取代上一版 derived claims。
- Use when：草稿完成要進入驗證，或寫作途中要先看哪些數字還沒有引用。
- Avoid when：報告仍在大幅改寫，抽取結果很快就會過期。
- 分類：`cited` 帶引用；`quantitative-uncited` 含數據但未引用；`process` 是方法章節的流程紀錄；`qualitative` 是其餘文字。年份、第 N 節、表 N 不算數據。
- 範圍：硬換行段落視為一段，小數點與縮寫不斷句，分號不斷句以便共用句尾引用。表格資料列以 `origin=table` 進入抽取，表頭不算主張。程式碼區塊、引言列與書目章節不進入抽取。

## Playbook：`claim-triage`

- 專家任務：寫作途中抽取主張，列出未引用的數據句與可定位的 `claim_id`，不執行完整驗證。
- 允許工具：`claim-ledger.extract_claims`、`run-manifest.write_manifest`
- 選擇規則：使用者要在草稿階段先看哪些數字還沒有引用時採用；要判定能否交付時改用 `report-verification`。
- 前置條件：草稿可由 `report_markdown` 或工作區路徑取得。
- 執行步驟：以 `claim-ledger.extract_claims` 建立主張快照，草稿尚無引用時傳入 `require_cited_claims=false`；依 `kind` 列出 `quantitative-uncited` 主張的 `claim_id`、章節與原句；以 `run-manifest.write_manifest` 記錄 `drafting` 階段狀態。
- 成功條件：`quantitative-uncited` 主張全數列出且可定位；回報時明示這不是交付判定。
- 替代方案：草稿過長導致結果被摘要時改讀 `claims.jsonl`。
- 替代政策：runtime 不可用時交棒；函數失敗時停止；成功條件未達成時停止。
- 停止條件：草稿為空，或使用者其實要求判定可否交付。

## 執行依據

- 中英文切分與分類的完整規則在此：[bilingual verification](../../references/bilingual-verification.md)。
- 呼叫前先確認函數狀態與 digest 綁定：[tool registry](../../tools/registry.json)。
- 參數、語意規則與 result policy 以函數 contract 為準：[extract_claims contract](../../tools/contracts/claim-ledger.extract_claims.json)。
- Python 入口、章節別名相依與環境 allowlist 以 runtime metadata 為準：[extract_claims runtime](../../tools/runtime/claim-ledger.extract_claims.json)。
- 修改切分或分類規則時要同步檢查功能分組 module：[claim ledger](../../scripts/claim_ledger.py)。
- 所有函數都經共用 runner 以 JSON stdin／stdout 呼叫：[run function](../../scripts/run_function.py)。
- 修改後以決定性軌跡確認抽取流程仍成立：[tool execution traces](../../assets/evals/tool-execution-traces.json)。
