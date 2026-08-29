# deep-research-metis

> Citation-tracked research reports as a Python **Code as Tool** skill: stable source identity, append-only evidence, bilingual (zh-TW / en) claim verification, and self-contained HTML delivery. Standard library only — no network calls, no package installs.

把研究報告生產中「容易臨時寫錯、但必須每次都對」的部分，固定成隨技能交付的 Python 函數：來源身分、證據持久化、主張抽取、引用比對、支撐度計分、自包含 HTML 渲染與 run manifest。檢索與寫作由 agent 負責，**可驗證性由這些函數負責**。

## 為什麼有這個技能

一般研究流程最常見的失效不是「找不到資料」，而是交付時沒人能證明每個數字出自哪一句原文。本技能把這件事變成機械可檢查的事：

- **來源有穩定身分**：網址正規化後產生 `source_id`，重複來源自動合併，追蹤參數與 credential 參數在寫入帳本前移除。
- **證據先於寫作**：逐字引文以 append-only 方式持久化，寫作只能引用已存在的引文。
- **主張逐句可驗**：報告切成 claim，每個帶引用的主張都對照它所引來源的引文計分。
- **交付前三道檢查**：結構、引用鏈、主張支撐度，任一不過就不交付。

### 雙語驗證模型

英文中心的驗證器在繁體中文報告上會系統性誤判：句子切分只認 ASCII 句號、字數以空白斷詞、支撐度以英文詞彙重疊計分，於是整節中文被當成一句話、篇幅被低估、幾乎每個主張都落入 `unsupported`。本技能的做法：

| 情境 | 計分方式 | 判定 |
| --- | --- | --- |
| 中文主張對中文引文 | CJK 字元 bigram 覆蓋率 | `supported` ≥ 0.45、`partial` ≥ 0.22 |
| 英文主張對英文引文 | 拉丁詞彙覆蓋率 | 同上 |
| 中文主張對英文引文 | 翻譯後仍保留的錨點：數字、單位、百分比、縮寫、專有名詞 | `supported` ≥ 0.60、`partial` ≥ 0.34 |
| 跨語言且沒有任何錨點 | 無法逐字比對 | `unverifiable` + 補證建議（預設 warning，不假裝有結論） |

行內引用標記 `[N]` 在計分前一律移除，否則編號會被當成主張裡的數字而扭曲比對。細節見 [references/bilingual-verification.md](../references/bilingual-verification.md)。

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
| `claim-ledger.extract_claims` | 中英文共用規則切句，標記引用與主張類型 |
| `report-verify.check_structure` | 必要章節、雙語標題、佔位字串、雙語長度下限 |
| `report-verify.check_citations` | 行內引用、書目條目與來源帳本三方比對，產生引用對應表 |
| `report-verify.check_claim_support` | 同語系／跨語系兩套計分，輸出四種判定 |
| `report-render.render_html` | 單檔、全跳脫、無外部資源的 HTML 交付物 |
| `run-manifest.write_manifest` | 階段狀態、gate 結果與產物 digest，支援續跑 |

三個 expert playbook：`full-research-report`（完整報告）、`report-verification`（既有草稿稽核）、`evidence-intake`（先建證據底稿）。每個 playbook 只能組合自己 allowlist 內的函數。

## 執行治理

- **closed-world allowlist**：未登錄的 function ID 在載入 contract 前就被拒絕。
- **digest 綁定**：registry 以 sha256 綁住每個 contract 與程式檔；任一方被改動而未重建 registry，執行即停止。
- **驗證順序**：input schema → 領域語意規則（回傳 `failed_rule_id`）→ 效果分類 → scoped approval → 呼叫 Python → 輸出驗證與 result policy。
- **approval**：`report-render.render_html` 是唯一具 `external_write` 效果的函數，必須附 approval record，且既有檔案預設不覆寫。
- **工作區邊界**：所有可變狀態寫在呼叫端指定的 `run_dir`，落在 skill 資料夾內會被拒絕；技能本身執行期唯讀。
- **無網路、無安裝**：目前所有函數僅用標準函式庫；未來若需第三方套件，必須隨技能放入 `assets/`。

## 產物

一次 run 會在工作區留下 `research_plan.json`、`sources.jsonl`、`evidence.jsonl`、`claims.jsonl`、`citation_map.json`、`claim_support.json`、`run_manifest.json`，以及通過驗證後的報告與 HTML 交付物。manifest 保留既有階段紀錄，中斷後可只補跑未完成階段。

## 測試與驗證證據

```bash
python -m unittest discover -s tests
```

20 項回歸測試（純標準庫）涵蓋網址正規化與 credential 移除、雙語計分、工作區邊界、帳本去重、佔位字串偵測、runner 四種 guard，以及 registry digest 與磁碟檔案一致性。

本版本以 SkillOps Studio 的 stage gate 驗證：create、evaluate、security 與 publish release gate 皆為 `PASS`（security 0 error / 0 warning，Code as Tool 稽核 9 函數 / 13 決定性軌跡）。frozen live benchmark 標記為 `SKIPPED`，因此本專案不提出速度、品質或取代其他技能的宣稱。逐項證據見 [references/readiness_report.md](../references/readiness_report.md)。

## 授權與來源

MIT。研究階段劃分與「每個主張都要有持久化證據」的概念參考 Openclaw-Metis/deep-research（MIT，改編自 199-biotechnologies/claude-deep-research-skill）；本技能的程式、契約、軌跡與測試皆為重新撰寫。完整聲明見 [NOTICE.md](../NOTICE.md)。
