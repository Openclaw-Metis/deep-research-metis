# deep-research-metis

> Citation-tracked research reports as a Python **Code as Tool** skill: stable source identity, append-only evidence, bilingual (zh-TW / en) claim verification, and self-contained HTML delivery. Standard library only — no network calls, no package installs.

把研究報告生產中「容易臨時寫錯、但必須每次都對」的部分，固定成隨技能交付的 Python 函數：來源身分、證據持久化、主張抽取、引用比對、支撐度計分、自包含 HTML 渲染與 run manifest。檢索與寫作由 agent 負責，**可驗證性由這些函數負責**。

## 為什麼有這個技能

一般研究流程最常見的失效不是「找不到資料」，而是交付時沒人能證明每個數字出自哪一句原文。本技能把這件事變成機械可檢查的事：

- **來源有穩定身分**：只接受 http(s) 來源；userinfo credential 直接拒絕，query credential 與追蹤參數在寫入帳本前移除。
- **證據先於寫作**：逐字引文以 append-only 方式持久化，寫作只能引用已存在的引文。
- **主張逐句可驗**：報告切成 claim（含表格資料列），每個帶引用的主張都對照它所引來源的引文計分。
- **數字不能靠字詞過關**：主張的每個數字都要出現在所引引文內，把 18% 寫成 81% 不會因為其他字都對而通過。
- **交付前三道檢查**：結構、引用鏈、主張支撐度，任一不過就不交付。

### 雙語驗證模型

英文中心的驗證器在繁體中文報告上會系統性誤判：句子切分只認 ASCII 句號、字數以空白斷詞、支撐度以英文詞彙重疊計分，於是整節中文被當成一句話、篇幅被低估、幾乎每個主張都落入 `unsupported`。本技能的做法：

| 情境 | 計分方式 | 判定 |
| --- | --- | --- |
| 中文主張對中文引文 | CJK 字元 bigram 覆蓋率 | `supported` ≥ 0.45、`partial` ≥ 0.22 |
| 英文主張對英文引文 | 拉丁詞彙覆蓋率 | 同上 |
| 中文主張對英文引文 | 翻譯後仍保留的錨點：數字、單位、百分比、縮寫、專有名詞 | `supported` ≥ 0.60、`partial` ≥ 0.34 |
| 跨語言且沒有任何錨點 | 無法逐字比對 | `unverifiable` + 補證建議（預設 warning，不假裝有結論） |

行內引用標記在計分前一律移除，否則編號會被當成主張裡的數字而扭曲比對。`[1, 2]`、`[1-3]` 與全形括號都是有效引用。細節見 [references/bilingual-verification.md](../references/bilingual-verification.md)。

這些檢查比對字詞與數字，不理解語意。`supported` 的意思是用語與數字對得上，否定、因果與適用範圍要由 agent 閱讀引文複核；正確但用詞差很多的改寫也可能被判為 `unsupported`。

## 安裝

```bash
git clone https://github.com/Openclaw-Metis/deep-research-metis.git ~/.claude/skills/deep-research-metis
```

需求：Python 3.9 以上，只用標準函式庫。倉庫根目錄即 skill 資料夾，clone 後即可使用。

## 快速開始

所有函數都經由共用 runner 呼叫，JSON stdin 進、JSON stdout 出：

```bash
echo '{"run_dir":"D:/research/grid-2026","question":"台灣資料中心用電成長對電網調度的影響","sub_questions":["用電量成長幅度為何","電網調度的彈性資源有多少"],"mode":"standard","language":"zh-TW"}' | python scripts/run_function.py research-plan.build_plan
```

exit code `0` 表示完成、`2` 表示函數失敗、`3` 表示 guard 在呼叫前後阻擋。完整呼叫序列見 [examples/full-report-run.md](../examples/full-report-run.md)，只做稽核的最小請求見 [examples/verification-request.json](../examples/verification-request.json)。

## 能力目錄

| Function ID | 作用 |
| --- | --- |
| `research-plan.build_plan` | 固定模式預算、必要章節與停止條件 |
| `source-ledger.register_sources` | 網址正規化、穩定 `source_id`、重複合併、諮詢性權威訊號 |
| `evidence-store.append_evidence` | 逐字引文綁定來源並 append-only 持久化 |
| `claim-ledger.extract_claims` | 中英文共用規則切句，建立綁定 report digest 的 derived snapshot |
| `report-verify.check_structure` | 必要章節、正文引用、佔位字串與雙語長度，持久化檢查結果 |
| `report-verify.check_citations` | 行內引用、書目條目與來源帳本三方比對，產生引用對應表 |
| `report-verify.check_claim_support` | 同語系／跨語系兩套計分加數字比對，輸出四種判定 |
| `report-render.render_html` | 單檔、全跳脫、無外部資源的 HTML 交付物 |
| `run-manifest.write_manifest` | 階段狀態、gate 結果與產物 digest，拒絕與驗證產物矛盾的紀錄，支援續跑 |

七個 expert playbook 由七個模組各自擁有：`full-research-report`（完整報告）、`report-verification`（既有草稿稽核）、`evidence-intake`（先建證據底稿）、`source-registration`（補登來源）、`claim-triage`（草稿自查未引用數字）、`report-delivery`（已驗證報告的 HTML 交付）、`run-resume`（中斷續跑）。每個 playbook 只能組合自己 allowlist 內的函數，模組索引在 `modules/<module>/REFERENCE.md`。

## 執行治理

- **closed-world allowlist**：未登錄的 function ID 在載入 contract 前就被拒絕。
- **完整 digest 鏈**：registry 以 sha256 綁住 contract、runtime metadata、主程式、共用 helper 與 bundled asset；任一方被改動而未同步，執行即停止。
- **驗證順序**：input schema → 領域語意規則（回傳 `failed_rule_id`）→ 效果分類 → scoped approval → 呼叫 Python → 輸出驗證與 result policy。
- **approval**：`report-render.render_html` 只接受未到期且 scope、target、report subject digest 全部相符的 approval；三項驗證結果也必須綁定目前草稿。
- **工作區邊界**：所有可變狀態寫在呼叫端指定的 `run_dir`，落在 skill 資料夾內會被拒絕；技能本身執行期唯讀。
- **無網路、無安裝**：目前所有函數僅用標準函式庫；未來若需第三方套件，必須隨技能放入 `assets/`。

## 產物

一次 run 會在工作區留下 `research_plan.json`、`sources.jsonl`、`evidence.jsonl`、`claims.jsonl`、`structure_check.json`、`citation_map.json`、`claim_support.json`、`run_manifest.json`，以及通過驗證後的報告與 HTML 交付物。來源／證據帳本保持 append-only，derived snapshots 隨草稿版本原子替換。

## 測試與驗證證據

```bash
python -m unittest discover -s tests
```

回歸測試為純標準庫，涵蓋網址與 credential 邊界、切句與引用解析、雙語與數字計分、書目判定、續跑 snapshot、verification freshness、approval binding、HTML 跳脫，以及完整 registry digest 鏈。

驗證函數的準確度以人工標註的凍結基準衡量，held_out 28 案例在修改程式前凍結：

```bash
python -B tests/verification_benchmark.py --split held_out
```

| 版本 | 判定一致率 | 應擋案例攔截率 | 誤放行 | 誤擋 |
| --- | --- | --- | --- | --- |
| v2026.8.30 | 0.50 | 0.6667 | 5 | 9 |
| v2026.10.31 | 0.9286 | 1.0 | 0 | 2 |

Gate 結果、未執行項目與已知限制見 [references/readiness_report.md](../references/readiness_report.md)。沒有跑過真實 host 上的 live benchmark，因此本專案不提出速度、觸發準確率或取代其他技能的宣稱。

## 授權與來源

MIT。研究階段劃分與「每個主張都要有持久化證據」的概念參考 Openclaw-Metis/deep-research（MIT，改編自 199-biotechnologies/claude-deep-research-skill）；本技能的程式、契約、軌跡與測試皆為重新撰寫。完整聲明見 [NOTICE.md](../NOTICE.md)。
