# 完整報告 run 的呼叫序列

以下是 `full-research-report` playbook 的一次實際呼叫序列。所有呼叫都透過共用 runner，以 JSON stdin 傳入、JSON stdout 取回結果。

## 1. 建立研究計畫

```bash
echo '{"run_dir":"D:/research/grid-2026","question":"台灣資料中心用電成長對電網調度的影響","sub_questions":["用電量成長幅度為何","電網調度目前的彈性資源有多少"],"mode":"standard","language":"zh-TW"}' | python scripts/run_function.py research-plan.build_plan
```

回傳的 `plan.retrieval_budget` 固定了本輪的來源下限與檢索次數上限；`plan.stop_conditions` 是後續階段的停止依據。

## 2. 登錄來源並持久化證據

```bash
echo '{"run_dir":"D:/research/grid-2026","sources":[{"url":"https://www.example.gov.tw/datacenter-2026?utm_source=news","title":"資料中心供電調度說明","publisher":"能源主管機關","published_at":"2026-03-01","language":"zh-TW"}]}' | python scripts/run_function.py source-ledger.register_sources
```

網址中的追蹤參數與 credential 參數會在正規化時移除，回傳的 `source_id` 是後續證據與書目的唯一身分。取得 `source_id` 後再寫入逐字引文：

```bash
echo '{"run_dir":"D:/research/grid-2026","evidence":[{"source_id":"S1a2b3c4d5e","quote":"尖峰負載期間資料中心的需量反應能力仍然有限。","locator":"第 3 節"}]}' | python scripts/run_function.py evidence-store.append_evidence
```

## 3. 驗證草稿

草稿寫好後放進工作區，依序執行三項檢查：

```bash
echo '{"run_dir":"D:/research/grid-2026","report_path":"report.md"}' | python scripts/run_function.py claim-ledger.extract_claims
echo '{"run_dir":"D:/research/grid-2026","report_path":"report.md","min_length":600}' | python scripts/run_function.py report-verify.check_structure
echo '{"run_dir":"D:/research/grid-2026","report_path":"report.md"}' | python scripts/run_function.py report-verify.check_citations
echo '{"run_dir":"D:/research/grid-2026","strict":true}' | python scripts/run_function.py report-verify.check_claim_support
```

`check_citations` 會產生 `citation_map.json`，`check_claim_support` 依賴它，因此順序不可對調。

## 4. 渲染交付物

`report-render.render_html` 宣告 `external_write` 效果，必須附上 approval record：

```bash
echo '{"run_dir":"D:/research/grid-2026","title":"台灣資料中心用電趨勢研究","report_path":"report.md","output_path":"report.html","_approval":{"decision":"granted","granted_by":"專案負責人","granted_at":"2026-08-29T09:00:00Z","scope":"write-report-deliverable","target":"report.html","expires_at":"2026-08-30T09:00:00Z"}}' | python scripts/run_function.py report-render.render_html
```

缺少 approval 或缺少 `target` 欄位時，runner 以 exit code 3 回傳 `approval_denied`，不會寫出任何檔案。既有檔案也不會被覆寫，除非同時傳入 `"overwrite": true`。

## 5. 記錄階段狀態

```bash
echo '{"run_dir":"D:/research/grid-2026","phase":"verification","phase_status":"complete","gate_results":[{"gate":"check_structure","status":"PASS"},{"gate":"check_citations","status":"PASS"},{"gate":"check_claim_support","status":"PASS"}]}' | python scripts/run_function.py run-manifest.write_manifest
```

manifest 保留既有階段紀錄與產物 digest，中斷後可以直接續跑未完成的階段。
