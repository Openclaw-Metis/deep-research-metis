# research-plan 模組

固定一次研究的範圍與預算，並擁有從研究問題走到交付物的主流程。新研究一律從這裡開始。

## 函數

### `research-plan.build_plan`

- 能力：把問題與子問題固定成含檢索預算、必要章節與停止條件的 run plan，並保護工作區不被第二個問題混用。
- Use when：研究剛開始，還沒有工作區或預算。
- Avoid when：只是要稽核既有報告，此時不需要重新規劃。
- 規則：子問題數量超過模式上限時 block，先收斂問題再開始檢索。同一工作區已有不同問題的計畫時以 `plan.run-dir-reused` 拒絕，改用新的 `run_dir`；`replace_plan` 只在使用者明示要取代時才傳入。

## Playbook：`full-research-report`

- 專家任務：從研究問題完成到通過驗證的報告與 HTML 交付物。
- 允許工具：`research-plan.build_plan`、`source-ledger.register_sources`、`evidence-store.append_evidence`、`claim-ledger.extract_claims`、`report-verify.check_structure`、`report-verify.check_citations`、`report-verify.check_claim_support`、`report-render.render_html`、`run-manifest.write_manifest`
- 選擇規則：使用者要完整報告且尚無草稿時採用；已有草稿只需稽核時改用 `report-verification`；只需整理來源時改用 `evidence-intake`；報告已驗證完成只要交付物時改用 `report-delivery`。
- 前置條件：已取得研究問題與可寫入的工作區；檢索能力由 host 提供；渲染前已備妥 approval record。

執行步驟：

1. 以 `research-plan.build_plan` 固定模式預算、必要章節與停止條件。
2. 檢索後以 `source-ledger.register_sources` 登錄每個要引用的來源，再以 `evidence-store.append_evidence` 寫入逐字引文；引文要包含報告會用到的數字。
3. 依計畫的 `required_sections` 撰寫草稿，每個事實主張與數字都帶行內引用，寫作時只引用已持久化的內容。判讀與推論是報告自己的判斷，不掛引用；引用只標在來源確實說過的事實上，否則支撐度會判為 `unsupported`。
4. 草稿完成後依序執行 `claim-ledger.extract_claims`、`report-verify.check_structure`、`report-verify.check_citations`。
5. 以 `report-verify.check_claim_support` 評分，補證據後重跑，不調整門檻。
6. PASS 後由 agent 逐則閱讀 executive summary 主張與其 `best_evidence_id` 引文。否定、因果與適用範圍是否相符不在機械檢查內，機械檢查只比對字詞與數字。
7. 三項檢查皆 PASS、產物綁定目前 report digest 且取得 scoped approval 後，才執行 `report-render.render_html`。
8. 以 `run-manifest.write_manifest` 記錄階段狀態、gate 結果與產物 digest。

- 成功條件：結構檢查 PASS 且無佔位字串；引用檢查沒有 error 級 finding；支撐度沒有 unsupported 主張與 `claim_number_unmatched`；三項驗證產物的 report digest 與交付草稿一致；manifest 記錄本輪實際 gate 結果。
- 替代方案：來源不足時改為部分交付並在限制章節說明，`source_count_below_plan` warning 就是這個訊號；支撐度不足時補證據重跑，而不是放寬門檻；無法取得寫入授權時只交付 Markdown 報告與檢查結果。
- 替代政策：Python runtime 不可用時停止並回報；函數失敗時停止；成功條件未達成時停止。允許的替代函數僅限本 playbook allowlist 內的 `run-manifest.write_manifest`。
- 停止條件：工作區落在技能資料夾內、存在無法對應來源的行內引用、或請求其實是單次查詢。

## 執行依據

- 各階段的完成條件與停止條件是續跑與判定完成的共同語彙，定義在此：[methodology](../../references/methodology.md)。
- 第一次走完整流程時，可對照一次實際的呼叫序列與 payload：[full report run](../../examples/full-report-run.md)。
- 呼叫前先確認函數狀態與 digest 綁定：[tool registry](../../tools/registry.json)。
- 參數、語意規則與 result policy 以函數 contract 為準：[build_plan contract](../../tools/contracts/research-plan.build_plan.json)。
- Python 入口、環境 allowlist 與 bundled 相依以 runtime metadata 為準：[build_plan runtime](../../tools/runtime/research-plan.build_plan.json)。
- 修改規劃邏輯時要同步檢查功能分組 module：[research plan](../../scripts/research_plan.py)。
- 所有函數都經共用 runner 以 JSON stdin／stdout 呼叫：[run function](../../scripts/run_function.py)。
- 修改後以決定性軌跡確認 happy path 與 guard 仍成立：[tool execution traces](../../assets/evals/tool-execution-traces.json)。
