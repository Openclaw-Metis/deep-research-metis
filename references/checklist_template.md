# 人工審查筆記範本

本檔只記錄尚無法安全機械判定的 reviewer judgment，不得當成發布證據。完成後把可驗證結論與證據寫入 `references/readiness_report.md`。

## 邊界審查
- Skill 是否只有一個直覺且清楚的 primary job？
- 相鄰 skills、negative triggers 與 handoff 是否明確？
- 新使用者是否能理解何時不該使用本 skill？

## 觸發審查
- Trigger examples 是否貼近真實使用者用語？
- 是否涵蓋繁體中文、英文與混合語言的必要變體？

## 輸出品質審查
- Worked examples 是否真的教出期望品質？
- Output contract 與 follow-through policy 是否足以重複執行？

## 維護審查
- 是否應 rename、merge、split、deprecate 或 retire？
- Host wrappers 是否足夠輕薄，沒有產生 contract drift？
