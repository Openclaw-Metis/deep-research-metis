# NOTICE

deep-research-metis 由 Openclaw-Metis 維護，以 MIT 授權釋出。

## 設計來源

- 研究流程的階段劃分（計畫、檢索、證據、撰寫、驗證、交付）與「以持久化證據支撐每個主張」的核心概念，參考 [Openclaw-Metis/deep-research](https://github.com/Openclaw-Metis/deep-research)（MIT），該專案本身改編自 199-biotechnologies/claude-deep-research-skill（MIT）。
- 本技能的 Python 實作、函數契約、runtime metadata、決定性軌跡與測試皆為重新撰寫；未複製上游程式碼。與上游相比，本技能改採 Python Code as Tool 架構，並把驗證器改寫為中英文雙語模型（CJK 句子切分、雙語長度量測、跨語系錨點計分）。

## 骨架與契約 schema

- `schemas/` 內的 `skill-contract.schema.json`、`tool-contract.schema.json`、`tool-registry.schema.json`、`tool-runtime-metadata.schema.json`、`tool-execution-trace.schema.json`、`module-registry.schema.json`、`lifecycle.schema.json`、`release_evidence.schema.json`，以及 `policies/` 的政策樣板，由 [SkillOps Studio](https://github.com/AllanYiin/skills/tree/main/skills/skillops-studio)（MIT，作者 Allan Yiin）的 skill 初始化器產生，用於驗證本技能的 Code as Tool 契約。

## 執行面聲明

- 本技能不進行任何網路呼叫，也不安裝套件；所有函數僅使用 Python 標準函式庫，第三方相依若日後需要，必須隨技能放入 `assets/`。
- 所有可變狀態都寫在呼叫端指定的 run 工作區；技能資料夾本身在執行期間保持唯讀。
