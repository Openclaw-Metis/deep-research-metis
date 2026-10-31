# report-verify 模組

交付前的三項機械檢查：結構、引用鏈與主張支撐度。三者綁定同一 report digest，任一 FAIL 就不可交付。

## 函數

### `report-verify.check_structure`

- 能力：檢查必要章節、雙語標題、佔位字串、正文行內引用與雙語長度下限，結果持久化為 `structure_check.json`。
- Use when：每次要判斷報告是否具備可交付結構。
- Avoid when：只想確認引用鏈，該用引用檢查。
- 規則：`bibliography` 章節要同時符合別名與內容；標題含「資料來源」但內文是一般段落時視為正文。

### `report-verify.check_citations`

- 能力：比對行內引用、書目條目與來源帳本，輸出引用對應表，支援 `[1, 2]`、`[1-3]`、全形括號與編號清單書目。
- Use when：報告已有書目章節。
- Avoid when：來源帳本仍為空，應先登錄來源。
- 規則：實際引用的來源少於計畫下限時回報 `source_count_below_plan` warning，要在限制章節說明或補足來源。

### `report-verify.check_claim_support`

- 能力：逐則引文計分並取最強判定，同語系以詞彙覆蓋率、跨語系以錨點比對；主張的數字必須出現在所引來源的引文內。
- Use when：引用檢查已產生 `citation_map.json`。
- Avoid when：證據帳本為空，計分沒有意義。
- 規則：`claim_number_unmatched` 在 `strict` 下是 error，即使字詞完全重疊也判定失敗。含「約」「about」等概數詞的主張容許 5% 差距；年份與章節編號不參與比對。判定與引文順序無關。

## Playbook：`report-verification`

- 專家任務：對既有草稿執行引用鏈、主張支撐度與數字一致性稽核。
- 允許工具：`claim-ledger.extract_claims`、`report-verify.check_structure`、`report-verify.check_citations`、`report-verify.check_claim_support`、`run-manifest.write_manifest`
- 選擇規則：使用者已有草稿並要求檢查時採用；報告尚未存在時改用 `full-research-report`；只想登錄來源時改用 `source-registration`；只想知道哪些數字未引用時改用 `claim-triage`。
- 前置條件：工作區已有來源與證據帳本；草稿可由內容或工作區路徑取得。

執行步驟：

1. 以 `claim-ledger.extract_claims` 建立可定位的 `claim_id`。
2. 執行 `report-verify.check_structure` 與 `report-verify.check_citations`，兩者不共用輸出檔。
3. 取得 `citation_map.json` 後以 `report-verify.check_claim_support` 計分。
4. PASS 後由 agent 逐則閱讀 executive summary 主張與其 `best_evidence_id` 引文。否定、因果與適用範圍是否相符不在機械檢查內，有疑慮時列為待查證項目。
5. 以 `run-manifest.write_manifest` 寫入三項結果；manifest 會拒絕與驗證產物矛盾的 PASS／FAIL。

- 成功條件：每個 finding 都可定位、支撐度報告區分四種判定、稽核結論如實反映 FAIL。
- 替代方案：證據帳本為空時交回 `evidence-intake`；缺少書目章節時只回傳結構檢查結果並說明缺口。
- 替代政策：runtime 不可用時交棒；函數失敗時停止；成功條件未達成時停止。
- 停止條件：沒有可比對的帳本，或使用者要求把 FAIL 直接改寫成 PASS。

## 執行依據

- 章節標題以隨技能交付的中英文別名表比對，新增別名不需要改程式：[section aliases](../../assets/lexicon/section_aliases.json)。
- 計分方法、門檻與判定語彙的完整說明在此：[bilingual verification](../../references/bilingual-verification.md)。
- 只做稽核時的最小請求範例在此：[verification request](../../examples/verification-request.json)。
- 呼叫前先確認函數狀態與 digest 綁定：[tool registry](../../tools/registry.json)。
- 三個函數的參數、語意規則與 result policy 各以其 contract 為準：[check_structure contract](../../tools/contracts/report-verify.check_structure.json)、[check_citations contract](../../tools/contracts/report-verify.check_citations.json)、[check_claim_support contract](../../tools/contracts/report-verify.check_claim_support.json)。
- 三個函數的 Python 入口與 bundled 相依各以其 runtime metadata 為準：[check_structure runtime](../../tools/runtime/report-verify.check_structure.json)、[check_citations runtime](../../tools/runtime/report-verify.check_citations.json)、[check_claim_support runtime](../../tools/runtime/report-verify.check_claim_support.json)。
- 修改檢查規則時要同步檢查共用的功能分組 module：[report verify](../../scripts/report_verify.py)。
- 所有函數都經共用 runner 以 JSON stdin／stdout 呼叫：[run function](../../scripts/run_function.py)。
- 修改後以決定性軌跡確認 expert validation 仍會失敗：[tool execution traces](../../assets/evals/tool-execution-traces.json)。
- 改動判定邏輯時重播人工標註的凍結基準，held-out 案例維持原樣並如實回報分數：[verification benchmark](../../assets/evals/verification-benchmark.json)。
