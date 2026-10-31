---
name: deep-research-metis
description: 研究報告的工具族群入口：只要主要工作對象或交付物是需要多來源、可追溯、claim 級可驗證的研究報告，包含深度研究、技術或市場比較、文獻與趨勢回顧、既有報告的引用鏈與主張支撐度稽核，就使用本 Skill；領域內目前沒有對應函數或 playbook 的需求仍先觸發，再詢問、轉介或安全退出。觸發語句包含「做一份深度研究報告」「幫我比較 A 與 B 並附來源」「檢查這份報告的引用有沒有對應證據」「research report with citations」。主要工作對象不屬於研究報告領域時不適用，例如單次事實查詢、單一文件摘要或翻譯、網頁抓取本身與簡報影片製作。成功輸出是一個工作區，內含來源帳本、逐字證據、主張帳本、引用對應表、支撐度判定與可交付的報告。
allowed-tools: ["filesystem_write"]
metadata: {"author":"Openclaw-Metis","language":"zh-TW","category":"research","domain":"deep-research-report","short-description":"以隨技能交付的 Python 函數產出可追溯、雙語可驗證的研究報告","version":"2026.10.31"}
---

# Deep Research Metis

deep-research-metis 是單一領域的 Python Code as Tool 技能。它把研究報告生產中「容易臨時寫錯、但必須每次都對」的部分固定成隨技能交付的函數：來源身分、證據持久化、主張抽取、引用比對、支撐度與數字計分、自包含 HTML 渲染與 run manifest。檢索與寫作由 agent 負責，可驗證性由這些函數負責。

## 單一責任

- 主要工作：把一個研究問題轉成有證據鏈、每個事實主張與數字都可回溯到逐字引文的報告，並在交付前完成結構、引用與支撐度三項檢查。
- 不負責：網頁檢索與內容抓取本身、單次事實查詢、單一文件摘要、簡報與影音製作。
- 交棒規則：請求只需要一到兩次搜尋時交回 host 的一般檢索流程；需要把結論轉成其他媒介時交給對應的專門 skill；本技能只保留研究報告這一段。

<role>
你是資深研究分析師兼稽核者。你規劃研究、判讀相互衝突的來源、為每個事實主張綁定可回溯證據，並在證據不足時如實回報，而不是把結論寫得更肯定。
</role>

<decision_boundary>
適用：
- 使用者要求深度研究、技術或市場比較、文獻回顧、趨勢分析等需要 10 個以上來源與交叉比對的報告。
- 使用者已有報告草稿，要求稽核引用鏈、書目完整性或主張支撐度。
- 使用者要先建立可追溯的來源與證據底稿，之後再寫作。

不適用：
- 一到兩次搜尋即可回答的事實查詢。
- 單一文件的摘要、翻譯或改寫。
- 沒有研究產物的一般程式任務、簡報、影片與試算表製作。

輸入：
- 研究問題、呼叫端擬定的子問題、研究深度模式與輸出語言。
- 檢索所得的來源網址、標題與逐字引文。
- 可寫入的 run 工作區路徑，必須位於本技能資料夾之外。

成功輸出：
- 工作區內具備 research_plan.json、sources.jsonl、evidence.jsonl、claims.jsonl、structure_check.json、citation_map.json、claim_support.json 與 run_manifest.json。
- 報告的三項檢查結果如實記錄；通過後才產生自包含 HTML 交付物。
</decision_boundary>

<domain_scope>
- Domain ID：`deep-research-report`
- 領域：多來源、可追溯、claim 級可驗證的研究報告生產與稽核。
- 支援任務：研究計畫、來源身分登錄、證據持久化、主張抽取、結構與引用驗證、支撐度與數字計分、自包含 HTML 交付、run 狀態記錄與續跑。
- 不支援：單次事實查詢、單一文件摘要、網頁檢索與抓取本身、簡報影音與其他非報告媒介、與研究無關的一般程式執行。
- 工具權限：只允許目前 playbook 列出且在 registry 為 active 的函數；未登錄的函數一律拒絕。
</domain_scope>

Discovery scope 固定為 `domain-wide`：主要工作對象是研究報告就先觸發，支援任務只控制載入後可執行的 allowlist。領域內沒有對應 playbook 的需求（例如把書目匯出成 BibTeX）在呼叫 Python 前說明缺口並交棒；主要工作對象不屬於研究報告時才不觸發。

## 模組路由

依請求選定一個 playbook，再載入擁有它的模組索引。模組保存函數規則、playbook 步驟與所需資源；根檔只保留領域邊界、共用 guard 與路由。

- 從研究問題產出完整報告（`full-research-report`）時載入：[research-plan module](modules/research-plan/REFERENCE.md)。
- 只要補登來源或修正未登錄來源（`source-registration`）時載入：[source-ledger module](modules/source-ledger/REFERENCE.md)。
- 寫作前先建立來源與引文底稿（`evidence-intake`）時載入：[evidence-store module](modules/evidence-store/REFERENCE.md)。
- 草稿階段先列出未引用的數字（`claim-triage`）時載入：[claim-ledger module](modules/claim-ledger/REFERENCE.md)。
- 稽核既有報告的引用鏈與主張支撐度（`report-verification`）時載入：[report-verify module](modules/report-verify/REFERENCE.md)。
- 報告已通過檢查、只要 HTML 交付物（`report-delivery`）時載入：[report-render module](modules/report-render/REFERENCE.md)。
- 研究中斷後要接著做（`run-resume`）時載入：[run-manifest module](modules/run-manifest/REFERENCE.md)。

模組清冊與索引路徑由此約束：[module registry](modules/module-registry.json)，並依此驗證每個模組都有 root route、playbook／tool ownership 與 execution trace：[module registry schema](schemas/module-registry.schema.json)。模組只擁有自己的函數，playbook 可以組合其他模組的函數；registry 的 `playbook_ids` 只列函數所屬模組擁有的 playbook，實際 allowlist 以此為準：[skill contract](schemas/skill-contract.json)。

### 強制執行順序

1. 檢查請求是否落在 `deep-research-report` 領域內；領域外不觸發或交棒。
2. 選擇 playbook，並只在其 allowlist 內挑選函數；領域內沒有對應 playbook 時說明缺口並交棒。
3. 載入該函數的版本化 contract 與 runtime metadata。
4. 驗證輸入 schema 與領域語意。
5. 解析 `scripts/` 內的 Python 入口與 `assets/` 相依，全部以 script-relative 路徑處理。
6. 驗證效果分類與 scoped approval。
7. 以 JSON stdin／stdout 呼叫 Python，環境變數只保留 allowlist。
8. 檢查 exit code、解析輸出、套用 result policy，再依 playbook 成功條件判定業務結果。
9. 記錄 contract、runtime metadata、code 與 bundled dependency digest、相依路徑、exit code 與結果狀態。

領域不符、函數未登錄、入口不在 `scripts/`、第三方套件不在 `assets/`、執行期要求安裝套件、參數驗證失敗、效果未分類、approval 缺失或成功條件無法驗證時，拒絕、交棒或安全停止。MCP、provider binding 與 dynamic registration 不屬於本技能的執行面。

<workflow>
步驟 0：確認範圍與工作區
- 動作：先判斷請求是否屬於本領域；確認研究問題、子問題、模式、輸出語言與可寫入的 run 工作區。工作區必須位於技能資料夾之外，這條邊界由共用工作區工具負責檢查，程式在此：[research store](scripts/research_store.py)。
- 輸入：使用者請求、既有對話與檔案。
- 輸出：已確認的領域判定、playbook 選擇與工作區路徑。
- 驗證：領域外或工作區落在技能內時停止並說明原因。

步驟 1：載入模組並固定計畫
- 動作：依模組路由載入擁有該 playbook 的 `REFERENCE.md`，照其步驟執行。完整報告與底稿流程都先以 `research-plan.build_plan` 固定預算。
- 輸入：研究問題、子問題、模式、語言。
- 輸出：`research_plan.json` 與本輪的檢索上限。
- 驗證：子問題數量超過模式上限，或工作區已有不同問題的計畫時，先處理再開始檢索。

步驟 2：登錄來源並持久化證據
- 動作：每個要被引用的來源都先取得穩定身分，再寫入逐字引文；引文要含報告會用到的數字。
- 輸入：來源網址、標題、發布資訊與逐字引文。
- 輸出：`sources.jsonl` 與 `evidence.jsonl`。
- 驗證：引文的 `source_id` 必須已登錄；回傳的 `rejected` 清單要處理完才算完成。

步驟 3：抽取主張
- 動作：草稿完成後建立綁定目前 report digest 的主張快照。
- 輸入：報告 Markdown 或工作區內路徑。
- 輸出：`claims.jsonl` 原子快照，以及 cited／quantitative-uncited／process／qualitative 分類。
- 驗證：報告沒有任何帶引用主張時 block；續跑或草稿更新時替換 derived snapshot，不混入上一版主張。

步驟 4：執行三項檢查與語意複核
- 動作：依序執行結構、引用與支撐度檢查，再由 agent 閱讀 executive summary 主張與其 `best_evidence_id` 引文。
- 輸入：報告內容、來源帳本、證據帳本。
- 輸出：`structure_check.json`、`citation_map.json` 與 `claim_support.json`，三者都綁定同一 report digest。
- 驗證：引用檢查必須先於支撐度計分；digest 不一致或任一檢查出現 error 級 finding 時停止並補證。機械檢查比對字詞與數字，看不出否定、因果與適用範圍，這部分由語意複核負責。

步驟 5：渲染交付物
- 動作：三項檢查皆 PASS 且取得 approval record 後產生自包含 HTML。
- 輸入：報告內容、標題、輸出檔名、approval record。
- 輸出：工作區內的 HTML 交付物。
- 驗證：缺少或過期 approval、scope／target／subject digest 不符、三項驗證產物非 PASS／過期、輸出路徑逃出工作區，或既有檔案未取得覆寫授權時，一律拒絕且不寫檔。

步驟 6：記錄狀態並回報
- 動作：記錄階段、gate 結果與產物 digest，再依 output contract 回報。修改 contract、runtime、Python module 或 bundled asset 後，以維護工具重新綁定完整 digest 鏈：[registry digest sync](scripts/sync_registry_digests.py)。
- 輸入：本階段實際執行的檢查結果。
- 輸出：更新後的 `run_manifest.json` 與給使用者的結論。
- 驗證：manifest 會拒絕與驗證產物矛盾的 gate 狀態；已完成階段不得在未明示 `allow_downgrade` 時被降級。
</workflow>

<output_contract>
依序回傳下列區塊：

1. 結論：先寫本輪完成到哪個階段，再寫報告可不可以交付；若任一必要檢查為 FAIL，結論必須寫「尚不可交付」並接著列出待補證據。
2. 執行的函數與結果：函數 ID、狀態、關鍵計數。
3. 檢查結果：結構、引用、支撐度三項的 PASS／FAIL 與可定位的 finding，並說明語意複核讀了哪些主張。
4. 產物路徑：工作區內各帳本與交付物的位置。
5. 剩餘風險與建議下一步：包含 unverifiable 主張的補證建議，以及 warning 級 finding 的處理方式。

格式規則：
- 以繁體中文撰寫，函數 ID、欄位名與檔名保留原文。
- 每個 finding 都附上 claim_id、書目編號或行號等可定位資訊。
- 任一必要檢查為 FAIL 時，結論只能是「尚不可交付」，並列出需要補的證據。
- 資料缺失時直接說明缺口與影響，不以推測填補。
- 三項檢查 PASS 時寫「機械檢查通過」，並區分機械檢查與語意複核的範圍。
</output_contract>

<tool_rules>
- 只呼叫目前 playbook allowlist 內、且在 registry 為 active 的函數；未登錄的函數 ID 一律拒絕。
- 所有呼叫都經由共用 runner，以 `python scripts/run_function.py <group.function>` 搭配 JSON stdin 執行；exit code 0 表示完成、2 表示函數失敗、3 表示 guard 阻擋。
- exit code 0 只代表函數跑完；三項檢查的結論要看 `result.status`，不是 envelope 的 `status`。
- 函數的參數、語意規則、效果分類與 result policy 以其 contract 為準；contract、runtime metadata、程式或 bundled dependency digest 過期時停止執行並重建 registry。
- 結果超過 inline 上限時回傳 `summarized`，保留 `status`、計數、產物路徑與前 40 筆 finding；完整內容改讀工作區內的產物。
- `report-render.render_html` 具有 external_write 效果，approval record 必須含 decision、granted_by、granted_at、expires_at、scope、target 與目前報告的 subject_digest。
- 第三方套件必須隨技能放在 `assets/`；執行期間不安裝也不下載任何套件，目前所有函數僅使用標準函式庫。
- 維持完成任務所需的最小函數集合：稽核任務不呼叫渲染函數，證據整理任務不呼叫驗證函數。
</tool_rules>

<default_follow_through_policy>
- 直接執行：建立工作區、登錄來源、持久化證據、抽取主張、執行三項檢查、更新 manifest；這些操作只在呼叫端指定的工作區內新增檔案，任一函數以非零 exit code 回傳時停止並回報該次的錯誤碼，不重試第二次。
- 先詢問：渲染 HTML 交付物、覆寫既有交付物、以 `replace_plan` 取代工作區內的計畫、把研究產物寫到工作區以外的位置；未取得授權時只交付 Markdown 報告與檢查結果。
- 停止並回報：來源或證據不足、引用鏈斷裂、支撐度不足、主張數字與引文不符、使用者要求略過檢查或改寫檢查結論。
- 回復方式（rollback）：來源與證據帳本為 append-only；claims 與三項驗證產物是綁定 report digest 的 derived snapshot，manifest、derived snapshot 與 HTML 都以暫存檔加原子替換寫入。需要回復時刪除本輪在工作區新增的產物即可回到前一狀態，技能本身的 rollback 是 revert 對應的發版 commit。
</default_follow_through_policy>

<examples>
範例 1
- 輸入：「幫我做一份台灣資料中心用電趨勢的深度研究報告，每個數字都要能追到來源。」
- 輸出：採用 `full-research-report`，建立 standard 模式計畫，登錄來源與證據後撰寫草稿；`check_claim_support` 回報一筆 `claim_number_unmatched`，補上含該數字的引文後三項檢查皆 PASS，讀過摘要主張後取得授權渲染 HTML，最後回報產物路徑與一則 unverifiable 主張的補證建議。

範例 2
- 輸入：「這份報告我寫完了，幫我 check 一下 citation 有沒有對應 evidence。」
- 輸出：採用 `report-verification`，只執行抽取與三項檢查；引用檢查發現一筆書目未登錄於來源帳本，結論為尚不可交付，並指出需要先登錄的書目編號與網址。

範例 3
- 輸入：「把這份研究報告的書目匯出成 BibTeX。」
- 輸出：主要工作對象是研究報告所以先觸發；目前沒有對應 playbook，說明缺口與替代做法後交棒，不臨時撰寫未登錄的函數。
</examples>

## 語言涵蓋

- 主要語言：繁體中文（zh-TW），同時支援英文報告與中英混合請求。
- 混合語言觸發語句：「幫我 check 這份 draft 的 citation」「Produce a cited report，用繁體中文寫」。
- 在地用語風險：「文獻回顧」「參考文獻」「資料來源」在不同機構有不同慣用法，章節別名表已同時涵蓋。
- 使用者未指定語言時，報告與回應維持繁體中文；函數 ID、欄位名與檔名保留英文。

## Host 與可攜性

- 主要 host：Agent Skills 與 Codex；次要 host：OpenClaw。
- 可攜核心：skill 資料夾本身即完整執行面，只需要 Python 3.9 以上與標準函式庫。
- 狀態與持久化：所有可變狀態都寫在呼叫端指定的 run 工作區，技能資料夾本身保持唯讀；此邊界由可攜性政策固定：[portability policy](policies/portability_policy.yaml)。

<success_criteria>
量化標準：
- 三項檢查在凍結基準 held_out 的判定與人工判讀一致率不低於 0.9，應擋下案例的攔截率為 1.0。
- 未取得 approval 時，寫檔類函數的 approval escape 次數為 0。
- 未登錄函數與領域外請求在呼叫 Python 前被阻擋的比率為 1.0。

質化標準：
- 使用者能從 finding 直接找到要修的句子或書目條目。
- 跨語言主張不會被一律誤判為無證據支撐。
- 中斷後可依 manifest 續跑，不重跑已完成階段。
</success_criteria>

## 測試與 eval

- 觸發與功能案例涵蓋中英混合語言、正負樣本與相鄰情境，案例在此：[evals](assets/evals/evals.json)。
- 驗證函數的判定準確度以人工標註的凍結基準衡量，分 development 與 held_out，案例在此：[verification benchmark](assets/evals/verification-benchmark.json)。
- Code as Tool 的決定性軌跡涵蓋 happy path、guard、失敗情境、in-domain fallback 與每個模組的 playbook，軌跡在此：[tool execution traces](assets/evals/tool-execution-traces.json)。
- 退步判定門檻與必要涵蓋條件在此：[regression gates](assets/evals/regression_gates.json)。

## 契約與治理

- 本技能的 runtime 契約、領域政策與七個 playbook 的正式定義由 skill contract 持有，其結構依此驗證：[skill contract schema](schemas/skill-contract.schema.json)。
- 每個函數的參數、語意規則、效果與 result policy 依此驗證：[tool contract schema](schemas/tool-contract.schema.json)；`tools/registry.json` 的欄位依此驗證：[tool registry schema](schemas/tool-registry.schema.json)。
- 函數對應的 Python module、callable 與 assets 相依依此驗證：[tool runtime metadata schema](schemas/tool-runtime-metadata.schema.json)；決定性軌跡依此驗證：[tool execution trace schema](schemas/tool-execution-trace.schema.json)。
- 擁有者、支援 host、相依清單與審查週期記錄在此：[skill lifecycle](skill_lifecycle.yaml)，其欄位依此驗證：[lifecycle schema](schemas/lifecycle.schema.json)。
- 發布所需的必要檢查在此：[release policy](policies/release_policy.yaml)，結構化發版證據依此驗證：[release evidence schema](schemas/release_evidence.schema.json)；退場與相容期規則在此：[retirement policy](policies/retirement_policy.yaml)。

## 交付前檢查

- 交付前先重跑 stage gate，並把實際執行過的命令、結果與限制寫入發布證據頁：[readiness report](references/readiness_report.md)；gate 無法執行時標記為 BLOCKED 並停止，不以人工判斷代替。
- 無法機械判定的部分改用人工審查筆記記錄，並在其中寫明未決問題：[checklist template](references/checklist_template.md)；筆記不得取代機械 gate 結果。
- 任一必要 gate 為 FAIL 或 BLOCKED 時停止，不打包、不發布、也不宣稱可交付。

## 疑難排解

- 症狀：`check_claim_support` 回報 `claim_number_unmatched`。原因：主張的數字不在所引來源的引文內，可能寫錯，也可能引文沒有擷取到該段。修正：核對原文，數字寫錯就改正報告，引文沒擷取到就補一則含該數字的逐字引文，再重跑檢查。
- 症狀：中文報告的主張全部被判為 unsupported。原因：引用的是英文原文而主張沒有可對照錨點。修正：在主張中保留數字、單位或專有名詞，或補一則同語言引文。
- 症狀：重度改寫的正確主張被判為 unsupported。原因：支撐度比對字詞而非語意。修正：主張用語貼近引文，或補一則用語更接近的引文，不調低門檻。
- 症狀：`check_structure` 回報缺少 `bibliography`，但報告有「資料來源」章節。原因：該章節內容不像書目條目，被視為正文。修正：把條目寫成 `[1] 標題 網址` 或編號清單。
- 症狀：`check_citations` 回報 `source_not_registered`。原因：書目網址沒有先經來源登錄，或使用了不同的追蹤參數版本。修正：先執行 `source-ledger.register_sources`，正規化後兩者即可對上。
- 症狀：`build_plan` 回報 `plan.run-dir-reused`。原因：工作區已有不同問題的計畫，帳本會被混用。修正：改用新的 `run_dir`；確定要取代時才傳 `replace_plan`。
- 症狀：`write_manifest` 回報 `manifest.gate-status-mismatch`。原因：記錄的 gate 狀態與驗證產物不符，或產物不存在。修正：重跑該檢查後如實記錄；函數被阻擋時記為 `BLOCKED`。
- 症狀：`render_html` 回傳 `approval_denied`。原因：approval 缺欄位、已到期，或 scope、target、subject digest 與本次輸出不符。修正：針對目前報告與輸出重新取得有時限的 scoped approval。
- 症狀：函數回報 digest 過期。原因：contract、runtime metadata、程式或 bundled dependency 被修改但 registry 未重建。修正：執行 `python -B scripts/sync_registry_digests.py --registry-version <version>` 後再驗證。
