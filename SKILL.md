---
name: deep-research-metis
description: 用於需要多來源、可追溯、claim 級可驗證的研究報告：深度研究、技術或市場比較、文獻與趨勢回顧、既有報告的引用鏈與主張支撐度稽核。觸發語句包含「做一份深度研究報告」「幫我比較 A 與 B 並附來源」「檢查這份報告的引用有沒有對應證據」「research report with citations」。單次事實查詢、單一文件摘要、網頁抓取本身與簡報影片製作不適用，應交回一般檢索流程或對應的專門 skill。成功輸出是一個工作區，內含來源帳本、逐字證據、主張帳本、引用對應表、支撐度判定與可交付的報告。
version: 2026.8.29
allowed-tools: ["filesystem_write"]
metadata: {"author":"Openclaw-Metis","language":"zh-TW","category":"research","domain":"deep-research-report","short-description":"以隨技能交付的 Python 函數產出可追溯、雙語可驗證的研究報告"}
---

# Deep Research Metis

deep-research-metis 是單一領域的 Python Code as Tool 技能。它把研究報告生產中「容易臨時寫錯、但必須每次都對」的部分固定成隨技能交付的函數：來源身分、證據持久化、主張抽取、引用比對、支撐度計分、自包含 HTML 渲染與 run manifest。檢索與寫作由 agent 負責，可驗證性由這些函數負責。

## 單一責任

- 主要工作：把一個研究問題轉成有證據鏈、每個事實主張都可回溯到逐字引文的報告，並在交付前完成結構、引用與支撐度三項檢查。
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
- 工作區內具備 research_plan.json、sources.jsonl、evidence.jsonl、claims.jsonl、citation_map.json、claim_support.json 與 run_manifest.json。
- 報告的三項檢查結果如實記錄；通過後才產生自包含 HTML 交付物。
</decision_boundary>

## 主要使用情境

1. **完整研究報告**
   - 觸發範例：「幫我做一份台灣資料中心用電趨勢的深度研究報告」、「Produce a cited research report comparing storage vendors」
   - 必要輸入：研究問題、子問題、工作區路徑。
   - 預期結果：三項檢查皆 PASS 的報告與 HTML 交付物，且每個事實主張都對應到已持久化證據。

2. **既有報告稽核**
   - 觸發範例：「這份 draft 我寫完了，幫我 check citation 有沒有對應 evidence」
   - 必要輸入：報告草稿、既有的來源與證據帳本。
   - 預期結果：可定位的 finding 清單與 supported／partial／unsupported／unverifiable 判定。

3. **證據底稿建立**
   - 觸發範例：「先把這十幾個來源和重點引文整理成可追溯的底稿」
   - 必要輸入：來源網址與逐字引文。
   - 預期結果：來源帳本與證據帳本完成，manifest 記錄 evidence 階段狀態。

<domain_scope>
- Domain ID：`deep-research-report`
- 領域：多來源、可追溯、claim 級可驗證的研究報告生產與稽核。
- 支援任務：研究計畫、來源身分登錄、證據持久化、主張抽取、結構與引用驗證、支撐度計分、自包含 HTML 交付、run 狀態記錄。
- 不支援：單次事實查詢、單一文件摘要、網頁檢索與抓取本身、簡報影音與其他非報告媒介、與研究無關的一般程式執行。
- 工具權限：只允許 registry 與目前 playbook 同時列出的函數；未登錄的函數一律拒絕，領域外請求交棒而非勉強執行。
</domain_scope>

### 能力目錄

#### `research-plan.build_plan`

- 能力：把問題與子問題固定成含檢索預算、必要章節與停止條件的 run plan。
- Use when：研究剛開始，還沒有工作區或預算。
- Avoid when：只是要稽核既有報告；此時不需要重新規劃。

#### `source-ledger.register_sources`

- 能力：正規化網址、指派穩定 `source_id`、合併重複來源並記錄諮詢性權威訊號。
- Use when：任何來源要被引用之前。
- Avoid when：來源沒有可追溯網址，應先取得原始出處。

#### `evidence-store.append_evidence`

- 能力：把逐字引文綁定到已登錄來源並以 append-only 方式持久化。
- Use when：寫作前需要固定引文內容。
- Avoid when：手上只有改寫過的摘要而非原文。

#### `claim-ledger.extract_claims`

- 能力：以中英文共用規則切分句子，抽出主張、所屬章節與引用編號。
- Use when：草稿完成、要進入驗證階段。
- Avoid when：報告仍在大幅改寫，抽取結果很快就會過期。

#### `report-verify.check_structure`

- 能力：檢查必要章節、雙語標題、佔位字串與雙語長度下限。
- Use when：每次要判斷報告是否具備可交付結構。
- Avoid when：只想確認引用鏈，該用引用檢查。

#### `report-verify.check_citations`

- 能力：比對行內引用、書目條目與來源帳本，輸出引用對應表。
- Use when：報告已有書目章節。
- Avoid when：來源帳本仍為空，應先登錄來源。

#### `report-verify.check_claim_support`

- 能力：以同語系詞彙覆蓋率或跨語系錨點比對，為每個帶引用主張計分。
- Use when：引用檢查已產生 `citation_map.json`。
- Avoid when：證據帳本為空，計分沒有意義。

#### `report-render.render_html`

- 能力：把通過驗證的報告渲染成單檔、全跳脫、無外部資源的 HTML 交付物。
- Use when：三項檢查皆 PASS 且已取得寫入授權。
- Avoid when：仍有 error 級 finding，或沒有 approval record。

#### `run-manifest.write_manifest`

- 能力：合併階段狀態、gate 結果與產物 digest，維持可續跑的 run manifest。
- Use when：每完成一個階段。
- Avoid when：想用它覆蓋真實的 FAIL 結果。

<expert_playbooks>
### `full-research-report`

- 專家任務：從研究問題完成到通過驗證的報告與 HTML 交付物。
- 允許工具：`research-plan.build_plan`、`source-ledger.register_sources`、`evidence-store.append_evidence`、`claim-ledger.extract_claims`、`report-verify.check_structure`、`report-verify.check_citations`、`report-verify.check_claim_support`、`report-render.render_html`、`run-manifest.write_manifest`
- 選擇規則：使用者要完整報告且尚無草稿時採用；已有草稿只需稽核時改用 `report-verification`；只需整理來源時改用 `evidence-intake`。
- 前置條件：已取得研究問題與可寫入的工作區；檢索能力由 host 提供；渲染前已備妥 approval record。
- 執行步驟：先建立計畫，再登錄來源、持久化證據、抽取主張，接著執行結構與引用檢查，最後計分支撐度、渲染交付物並記錄 manifest。
- 成功條件：結構檢查 PASS 且無佔位字串、引用檢查沒有 error 級 finding、支撐度沒有 unsupported 主張、manifest 記錄本輪實際 gate 結果。
- 替代方案：來源不足時改為部分交付並在限制章節說明；支撐度不足時補證據重跑，而不是調高門檻。
- 替代政策：Python runtime 不可用時停止並回報；函數失敗時停止；成功條件未達成時停止。允許的替代函數僅限本 playbook allowlist 內的 `run-manifest.write_manifest`。
- 停止條件：工作區落在技能資料夾內、存在無法對應來源的行內引用、或請求其實是單次查詢。

### `report-verification`

- 專家任務：對既有草稿執行引用鏈與主張支撐度稽核。
- 允許工具：`claim-ledger.extract_claims`、`report-verify.check_structure`、`report-verify.check_citations`、`report-verify.check_claim_support`、`run-manifest.write_manifest`
- 選擇規則：使用者已有草稿並要求檢查時採用；報告尚未存在時改用 `full-research-report`；只想登錄來源時改用 `evidence-intake`。
- 前置條件：工作區已有來源與證據帳本；草稿可由內容或工作區路徑取得。
- 執行步驟：先抽取主張建立可定位的 claim_id，再執行結構檢查與引用檢查，取得引用對應表後計分支撐度，最後把結果寫入 manifest。
- 成功條件：每個 finding 都可定位、支撐度報告區分四種判定、稽核結論如實反映 FAIL。
- 替代方案：證據帳本為空時交回 `evidence-intake`；缺少書目章節時只回傳結構檢查結果並說明缺口。
- 替代政策：runtime 不可用時交棒；函數失敗時停止；成功條件未達成時停止。
- 停止條件：沒有可比對的帳本，或使用者要求把 FAIL 直接改寫成 PASS。

### `evidence-intake`

- 專家任務：在寫作前建立可追溯的來源身分與逐字證據底稿。
- 允許工具：`research-plan.build_plan`、`source-ledger.register_sources`、`evidence-store.append_evidence`、`run-manifest.write_manifest`
- 選擇規則：使用者要先蒐集整理、暫不產出報告時採用；已有完整證據要寫報告時改用 `full-research-report`。
- 前置條件：已知研究問題與工作區；每筆引文都能對應到具體來源網址。
- 執行步驟：先固定檢索預算，再分批登錄來源，逐字引文附上 locator，最後記錄 evidence 階段狀態。
- 成功條件：來源數量達到模式下限或已記錄未達標原因、每筆證據都綁定已登錄的 `source_id`、manifest 狀態與實際結果一致。
- 替代方案：來源不足時記錄為 partial 並列出仍缺的子問題；引文過長時擷取關鍵段落並保留 locator。
- 替代政策：runtime 不可用時交棒；函數失敗時停止；成功條件未達成時停止。
- 停止條件：來源沒有可追溯網址，或引文是改寫而非原文。
</expert_playbooks>

### 強制執行順序

1. 檢查請求是否落在 `deep-research-report` 領域內；領域外交棒。
2. 選擇 playbook，並只在其 allowlist 內挑選函數。
3. 載入該函數的版本化 contract 與 runtime metadata。
4. 驗證輸入 schema 與領域語意。
5. 解析 `scripts/` 內的 Python 入口與 `assets/` 相依，全部以 script-relative 路徑處理。
6. 驗證效果分類與 scoped approval。
7. 以 JSON stdin／stdout 呼叫 Python，環境變數只保留 allowlist。
8. 檢查 exit code、解析輸出、套用 result policy，再依 playbook 成功條件判定業務結果。
9. 記錄 contract digest、code digest、相依路徑、exit code 與結果狀態。

領域不符、函數未登錄、入口不在 `scripts/`、第三方套件不在 `assets/`、執行期要求安裝套件、參數驗證失敗、效果未分類、approval 缺失或成功條件無法驗證時，拒絕、交棒或安全停止。MCP、provider binding 與 dynamic registration 不屬於本技能的執行面。

<workflow>
步驟 0：確認範圍與工作區
- 動作：先判斷請求是否屬於本領域；確認研究問題、子問題、模式、輸出語言與可寫入的 run 工作區。工作區必須位於技能資料夾之外，這條邊界由共用工作區工具負責檢查，程式在此：[research store](scripts/research_store.py)。
- 輸入：使用者請求、既有對話與檔案。
- 輸出：已確認的領域判定、playbook 選擇與工作區路徑。
- 驗證：領域外或工作區落在技能內時停止並說明原因。

步驟 1：建立研究計畫
- 動作：以 `research-plan.build_plan` 固定模式預算、必要章節與停止條件，實作在此：[research plan](scripts/research_plan.py)。各階段的完成條件與停止條件另見階段契約：[methodology](references/methodology.md)。
- 輸入：研究問題、子問題、模式、語言。
- 輸出：`research_plan.json` 與本輪的檢索上限。
- 驗證：子問題數量超過模式上限時 block，先收斂問題再開始檢索。

步驟 2：登錄來源並持久化證據
- 動作：每個要被引用的來源都先經 `source-ledger.register_sources` 取得穩定身分，程式在此：[source ledger](scripts/source_ledger.py)；再以 `evidence-store.append_evidence` 寫入逐字引文，程式在此：[evidence store](scripts/evidence_store.py)。
- 輸入：來源網址、標題、發布資訊與逐字引文。
- 輸出：`sources.jsonl` 與 `evidence.jsonl`。
- 驗證：引文的 `source_id` 必須已登錄；網址中的 credential 參數會被移除後才寫入帳本。

步驟 3：抽取主張
- 動作：草稿完成後以 `claim-ledger.extract_claims` 切分句子並標記引用，程式在此：[claim ledger](scripts/claim_ledger.py)。中英文的切分與計分規則另見雙語驗證模型：[bilingual verification](references/bilingual-verification.md)。
- 輸入：報告 Markdown 或工作區內路徑。
- 輸出：`claims.jsonl` 與 cited／quantitative-uncited／qualitative 分類。
- 驗證：報告沒有任何帶引用主張時 block，要求先補引用。

步驟 4：執行三項檢查
- 動作：依序執行 `report-verify.check_structure`、`report-verify.check_citations` 與 `report-verify.check_claim_support`，三者共用同一份驗證程式：[report verify](scripts/report_verify.py)。章節標題以隨技能交付的中英文別名表比對，資料在此：[section aliases](assets/lexicon/section_aliases.json)。
- 輸入：報告內容、來源帳本、證據帳本。
- 輸出：結構 finding、`citation_map.json` 與 `claim_support.json`。
- 驗證：引用檢查必須先於支撐度計分；任一檢查出現 error 級 finding 時停止並補證，不調整門檻。

步驟 5：渲染交付物
- 動作：三項檢查皆 PASS 且取得 approval record 後，以 `report-render.render_html` 產生自包含 HTML，程式在此：[report render](scripts/report_render.py)。完整呼叫序列與 payload 範例在此：[full report run](examples/full-report-run.md)。
- 輸入：報告內容、標題、輸出檔名、approval record。
- 輸出：工作區內的 HTML 交付物。
- 驗證：缺少 approval、輸出路徑逃出工作區或既有檔案未取得覆寫授權時，一律拒絕且不寫檔。

步驟 6：記錄狀態並回報
- 動作：以 `run-manifest.write_manifest` 記錄階段、gate 結果與產物 digest，程式在此：[run manifest](scripts/run_manifest.py)。所有函數都必須經由共用 runner 呼叫，入口在此：[run function](scripts/run_function.py)。只做稽核時的最小請求範例在此：[verification request](examples/verification-request.json)。
- 輸入：本階段實際執行的檢查結果。
- 輸出：更新後的 `run_manifest.json` 與給使用者的結論。
- 驗證：manifest 內容必須與實際結果一致；已完成階段不得在未明示 `allow_downgrade` 時被降級。
</workflow>

<output_contract>
依序回傳下列區塊：

1. 結論：先寫本輪完成到哪個階段，再寫報告可不可以交付；若任一必要檢查為 FAIL，結論必須寫「尚不可交付」並接著列出待補證據。
2. 執行的函數與結果：函數 ID、狀態、關鍵計數。
3. 檢查結果：結構、引用、支撐度三項的 PASS／FAIL 與可定位的 finding。
4. 產物路徑：工作區內各帳本與交付物的位置。
5. 剩餘風險與建議下一步：包含 unverifiable 主張的補證建議。

格式規則：
- 以繁體中文撰寫，函數 ID、欄位名與檔名保留原文。
- 每個 finding 都附上 claim_id、書目編號或行號等可定位資訊。
- 任一必要檢查為 FAIL 時，結論只能是「尚不可交付」，並列出需要補的證據。
- 資料缺失時直接說明缺口與影響，不以推測填補。
</output_contract>

<tool_rules>
- 只呼叫 registry 與目前 playbook 同時列出的函數；未登錄的函數 ID 一律拒絕。
- 所有呼叫都經由共用 runner，以 `python scripts/run_function.py <group.function>` 搭配 JSON stdin 執行；exit code 0 表示完成、2 表示函數失敗、3 表示 guard 阻擋。
- 函數的參數、語意規則、效果分類與 result policy 以其 contract 為準；contract 或程式 digest 過期時停止執行並重建 registry。
- `report-render.render_html` 具有 external_write 效果，必須附帶含 decision、granted_by、granted_at、scope 與 target 的 approval record。
- 第三方套件必須隨技能放在 `assets/`；執行期間不安裝也不下載任何套件，目前所有函數僅使用標準函式庫。
- 維持完成任務所需的最小函數集合：稽核任務不呼叫渲染函數，證據整理任務不呼叫驗證函數。
</tool_rules>

<default_follow_through_policy>
- 直接執行：建立工作區、登錄來源、持久化證據、抽取主張、執行三項檢查、更新 manifest；這些操作只在呼叫端指定的工作區內新增檔案，任一函數以非零 exit code 回傳時停止並回報該次的錯誤碼，不重試第二次。
- 先詢問：渲染 HTML 交付物、覆寫既有交付物、把研究產物寫到工作區以外的位置；未取得授權時只交付 Markdown 報告與檢查結果。
- 停止並回報：來源或證據不足、引用鏈斷裂、支撐度不足、使用者要求略過檢查或改寫檢查結論。
- 回復方式（rollback）：帳本為 append-only，manifest 與引用對應表以暫存檔加原子替換寫入；需要回復時刪除本輪在工作區新增的產物即可回到前一狀態，技能本身的 rollback 是 revert 對應的發版 commit。
</default_follow_through_policy>

<examples>
範例 1
- 輸入：「幫我做一份台灣資料中心用電趨勢的深度研究報告，每個數字都要能追到來源。」
- 輸出：採用 `full-research-report`，建立 standard 模式計畫，登錄來源與證據後撰寫草稿，三項檢查皆 PASS 後取得授權渲染 HTML，最後回報產物路徑與一則 unverifiable 主張的補證建議。

範例 2
- 輸入：「這份報告我寫完了，幫我 check 一下 citation 有沒有對應 evidence。」
- 輸出：採用 `report-verification`，只執行抽取與三項檢查；引用檢查發現一筆書目未登錄於來源帳本，結論為尚不可交付，並指出需要先登錄的書目編號與網址。
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
- 三項檢查在測試報告上的判定與人工判讀一致率不低於 0.9。
- 未取得 approval 時，寫檔類函數的 approval escape 次數為 0。
- 未登錄函數與領域外請求在呼叫 Python 前被阻擋的比率為 1.0。

質化標準：
- 使用者能從 finding 直接找到要修的句子或書目條目。
- 跨語言主張不會被一律誤判為無證據支撐。
- 中斷後可依 manifest 續跑，不重跑已完成階段。
</success_criteria>

## 測試與 eval

- 觸發與功能案例涵蓋中英混合語言、正負樣本與相鄰情境，案例在此：[evals](assets/evals/evals.json)。
- Code as Tool 的十三種決定性軌跡涵蓋 happy path、領域外、未登錄函數、參數錯誤、approval denial、語意驗證失敗、專家驗證失敗、輸出遮罩、Python-only、assets 相依、workflow 組合、工作目錄獨立與函數失敗，軌跡在此：[tool execution traces](assets/evals/tool-execution-traces.json)。
- 退步判定門檻與必要涵蓋條件在此：[regression gates](assets/evals/regression_gates.json)。

## 契約與治理

- 本技能的 runtime 契約、領域政策與三個 playbook 的正式定義在此：[skill contract](schemas/skill-contract.json)，其結構依此驗證：[skill contract schema](schemas/skill-contract.schema.json)。
- 每個函數的參數、語意規則、效果與 result policy 依此驗證：[tool contract schema](schemas/tool-contract.schema.json)；`tools/registry.json` 的欄位依此驗證：[tool registry schema](schemas/tool-registry.schema.json)。
- 函數對應的 Python module、callable 與 assets 相依依此驗證：[tool runtime metadata schema](schemas/tool-runtime-metadata.schema.json)；決定性軌跡依此驗證：[tool execution trace schema](schemas/tool-execution-trace.schema.json)。
- 擁有者、支援 host、相依清單與審查週期記錄在此：[skill lifecycle](skill_lifecycle.yaml)，其欄位依此驗證：[lifecycle schema](schemas/lifecycle.schema.json)。
- 發布所需的必要檢查在此：[release policy](policies/release_policy.yaml)，結構化發版證據依此驗證：[release evidence schema](schemas/release_evidence.schema.json)；退場與相容期規則在此：[retirement policy](policies/retirement_policy.yaml)。

## 交付前檢查

- 交付前先重跑 stage gate，並把實際執行過的命令、結果與限制寫入發布證據頁：[readiness report](references/readiness_report.md)；gate 無法執行時標記為 BLOCKED 並停止，不以人工判斷代替。
- 無法機械判定的部分改用人工審查筆記記錄，並在其中寫明未決問題：[checklist template](references/checklist_template.md)；筆記不得取代機械 gate 結果。
- 任一必要 gate 為 FAIL 或 BLOCKED 時停止，不打包、不發布、也不宣稱可交付。

## 疑難排解

- 症狀：中文報告的主張全部被判為 unsupported。原因：引用的是英文原文而主張沒有可對照錨點。修正：在主張中保留數字、單位或專有名詞，或補一則同語言引文。
- 症狀：`check_citations` 回報 `source_not_registered`。原因：書目網址沒有先經來源登錄，或使用了不同的追蹤參數版本。修正：先執行 `source-ledger.register_sources`，正規化後兩者即可對上。
- 症狀：`render_html` 回傳 `approval_denied`。原因：payload 缺少 approval record 或缺少 target 欄位。修正：補齊 decision、granted_by、granted_at、scope 與 target 後重試。
- 症狀：函數回報 digest 過期。原因：程式或 contract 被修改但 registry 未重建。修正：重新產生 contract 與 code digest 後再執行。
