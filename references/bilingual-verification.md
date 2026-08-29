# 雙語驗證模型

英文中心的驗證器在繁體中文報告上會系統性誤判：句子切分只認 ASCII 句號、長度以空白斷詞、主張支撐度以英文詞彙重疊計分，於是整節中文被視為單一句子、字數被低估、幾乎每個主張都落入 `unsupported`。本 skill 的三個檢查改以下列規則運作。

## 句子切分

`claim-ledger.extract_claims` 以 `。！？；?!.` 為斷點，並允許斷點後緊接 `[N]` 引用標記，因此「……成長 [1]。」會被完整切成一個帶引用的主張。程式碼區塊、表格列、引言列與書目章節都不進入主張抽取。

## 長度量測

`bilingual_length` 把 CJK 字元逐字計數、拉丁字串以詞計數，兩者相加。這讓 `check_structure` 的 `min_length` 對中英文都有一致意義，不會因為中文沒有空白而低估篇幅。

## 章節比對

章節標題以中英文別名表比對，因此 `## Executive Summary 執行摘要`、`## 執行摘要` 與 `## Executive Summary` 都算通過。別名表是隨 Skill 交付的資料資產，新增別名不需要改程式。

## 主張支撐度計分

`report-verify.check_claim_support` 先判斷主張與引文的主要書寫系統：

- **同語系（same-script-lexical）**：中文對中文以字元 bigram 覆蓋率計分，英文對英文以詞彙覆蓋率計分。`supported` 門檻 0.45，`partial` 門檻 0.22。
- **跨語系（cross-script-anchor）**：中文主張引用英文原文時，逐字重疊必然為零，因此改以翻譯後仍會保留的錨點計分：數字、單位、百分比、縮寫與專有名詞。門檻較嚴，`supported` 0.60、`partial` 0.34。
- **無錨點（insufficient-signal）**：跨語系但主張沒有任何數字或專有名詞可對照時，判為 `unverifiable` 並回傳 warning，建議補上可對照的錨點或同語言引文。只有在呼叫端明示 `require_cross_language_anchor` 時才升級為 error。

行內引用標記在計分前一律移除，否則 `[2]` 會被當成主張中的數字「2」而扭曲錨點比對。

## 判定語彙

`supported` 表示引文足以支撐該句；`partial` 表示部分重疊，建議補強；`unsupported` 表示重疊過低，預設在 `strict` 模式下判為 error；`unverifiable` 表示跨語言且無錨點，需要人工補證而非自動放行。四種判定都寫入 `claim_support.json`，並附上 `method` 欄位說明分數的來源方法。
