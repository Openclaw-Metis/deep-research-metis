# report-render 模組

把通過驗證的報告寫成單檔 HTML。這是本技能唯一需要 approval 的效果。

## 函數

### `report-render.render_html`

- 能力：確認三項驗證產物皆為 PASS 且 report digest 與目前草稿一致後，渲染成單檔、全跳脫、無外部資源的 HTML 交付物。
- Use when：三項檢查皆 PASS 且已取得寫入授權。
- Avoid when：仍有 error 級 finding，或沒有 approval record。
- 規則：`external_write` 效果需要 approval record，含 decision、granted_by、granted_at、expires_at、scope、target 與目前報告的 subject_digest；既有檔案只在明示 `overwrite` 時才取代。行內引用連到書目條目的錨點，書目內的網址自動成為連結。頁尾預設語言跟隨 `language`，只陳述已執行的檢查。

## Playbook：`report-delivery`

- 專家任務：為已通過三項檢查的報告取得 scoped approval 後，產生自包含 HTML 交付物。
- 允許工具：`report-render.render_html`、`run-manifest.write_manifest`
- 選擇規則：報告已通過三項檢查，使用者只要交付物時採用；尚未驗證或草稿已改動時先走 `report-verification`。
- 前置條件：`structure_check.json`、`citation_map.json` 與 `claim_support.json` 皆為目前 report digest 的 PASS；已取得綁定 scope、target、report digest 與期限的 approval record。
- 執行步驟：計算目前報告的 digest 並向使用者取得 scoped approval；以 `report-render.render_html` 寫出交付物；以 `run-manifest.write_manifest` 記錄 `delivery` 階段與交付物 digest。
- 成功條件：交付物為單檔、全跳脫且無外部資源；manifest 記錄 `delivery` 階段。
- 替代方案：未取得授權時只交付 Markdown 報告與檢查結果。
- 替代政策：runtime 不可用時停止；函數失敗時停止；成功條件未達成時停止。
- 停止條件：任一驗證產物不是目前 report digest 的 PASS；approval 缺失、過期或與輸出不符。

## 執行依據

- approval record 的完整呼叫範例在此：[full report run](../../examples/full-report-run.md)。
- 呼叫前先確認函數狀態與 digest 綁定：[tool registry](../../tools/registry.json)。
- 效果、approval 綁定與 result policy 以函數 contract 為準：[render_html contract](../../tools/contracts/report-render.render_html.json)。
- Python 入口、章節別名相依與環境 allowlist 以 runtime metadata 為準：[render_html runtime](../../tools/runtime/report-render.render_html.json)。
- 修改渲染或跳脫規則時要同步檢查功能分組 module：[report render](../../scripts/report_render.py)。
- approval 的核對由共用 runner 在呼叫前執行：[run function](../../scripts/run_function.py)。
- 修改後以決定性軌跡確認 approval denial 與 stale verification 仍會阻擋：[tool execution traces](../../assets/evals/tool-execution-traces.json)。
