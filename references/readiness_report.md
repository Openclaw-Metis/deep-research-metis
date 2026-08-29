# Readiness Report

本檔是 deep-research-metis 目前版本的發布證據。只記錄本輪實際執行過、且可重跑的命令與結果；未執行的項目一律標為 SKIPPED 或 BLOCKED。

## 最終 Gate

- Skill version: 2026.8.29
- Audit date: 2026-08-29
- 稽核執行者：local（Windows 11、Python 3.10.11、cp950 主控台以 `PYTHONUTF8=1` 執行）
- Git commit：見發版 commit；本檔隨每次 gate 重跑更新。
- Current status: PASS（僅限本地決定性 stage gate 與結構檢查；frozen live benchmark 為 SKIPPED，因此不含真實 host 品質宣稱）
- 阻擋問題：無。

## 實際執行的命令

```bash
python skillops-studio/scripts/stage_gate.py <skill-path> --stage create --json
python skillops-studio/scripts/stage_gate.py <skill-path> --stage evaluate --json
python skillops-studio/scripts/stage_gate.py <skill-path> --stage security --json
python skillops-studio/scripts/release_gate.py <skill-path> --stage publish --json
python -m unittest discover -s tests
```

結果：create、evaluate、security 三個 stage gate 與 publish release gate 皆為 `PASS`；unittest 20 項全數通過。各稽核項目的實際數字如下。

| 稽核 | 結果 | 數字 |
| --- | --- | --- |
| `stage_contract` / `format` / `skill_references` | PASS | 0 error |
| `unreferenced_files` | PASS | 31 個資源全部有 point-of-use 連結，0 orphan、0 detached link |
| `skill_consistency` | PASS | 名稱、版本、稽核日期與 lifecycle 一致 |
| `eval_assets` | PASS | 12 個案例，涵蓋七種 tag、三種語言、三種 trigger class |
| `tool_execution_skill` | PASS | 9 個 `group.function`、13 種決定性軌跡 |
| `skill_security` | PASS | 52 檔案、0 error、0 warning；風險訊號只有 filesystem_write |
| `instruction_control`（advisory） | 4 observation | 0 blocking、0 warning |
| `benchmark` | SKIPPED | 未執行 frozen live benchmark |

## 格式與結構檢查

- Skill folder 名稱為 kebab-case，且與 frontmatter `name` 一致。
- `SKILL.md` 具備 `name`、`description` 與單行 compact JSON `metadata`（author、language、short-description、category、domain）。
- Frontmatter 不含角括號；skill 資料夾內沒有 `README.md`。
- `role`、`decision_boundary`、`domain_scope`、`expert_playbooks`、`workflow`、`output_contract`、`tool_rules` 與 `default_follow_through_policy` 都是實質內容。
- 每個本地資源連結都放在說明其用途的文字之後，unreferenced file 與 detached index link 皆為 0。

## 要求與政策檢查

- `archetype=tool-executor`、`execution_model=code-as-tool`、`language=python`，相依政策為 stdlib-or-assets 且執行期不安裝套件。
- 九個 `group.function` 都對應到實際存在的 Python callable，contract digest 與 code digest 與檔案內容一致。
- 三個 playbook 的 workflow 只組合自身 allowlist 內的函數，依賴圖無未知節點與 cycle。
- `report-render.render_html` 是唯一具 external_write 效果的函數，approval policy 為 required 並綁定 target。
- 所有可變狀態都寫在呼叫端指定的 run 工作區；技能資料夾內不保存任何執行期狀態。

## 功能驗證（實際執行）

以 `scripts/run_function.py` 對一份繁體中文測試報告執行端到端流程，結果如下：

- `research-plan.build_plan`、`source-ledger.register_sources`、`evidence-store.append_evidence`、`claim-ledger.extract_claims`、`report-verify.check_structure`、`report-verify.check_citations`、`report-verify.check_claim_support`、`report-render.render_html`、`run-manifest.write_manifest` 均以 exit code 0 完成。
- 結構檢查 PASS，七個必要章節全數以中英混合標題比對成功。
- 引用檢查 PASS，兩則行內引用都對應到已登錄來源。
- 支撐度計分：3 則 supported、1 則 partial、0 則 unsupported、1 則 unverifiable（中文主張引用英文原文且無錨點，依設計回報 warning 與補證建議）。
- Guard 行為：缺少 approval 的渲染呼叫、未登錄函數、參數違反 enum、以及引用未登錄來源的證據寫入，全部以 exit code 3 在呼叫 Python 前正確阻擋，並回傳對應的 `failed_rule_id`。
- 回歸測試：`python -m unittest discover -s tests` 20 項全數通過，涵蓋網址正規化與 credential 移除、雙語長度與跨語系計分、工作區邊界、帳本去重、書目不進入主張抽取、佔位字串偵測、runner 四種 guard，以及 registry digest 與磁碟檔案一致性。
- 建構期間由測試與端到端執行實際攔截到三個缺陷並已修正：書目網址未正規化導致來源比對失敗、引用標記 `[N]` 被誤判為主張中的數字錨點、數字錨點尾隨空白導致跨語系比對漏配。

## 常見錯誤

- 中文報告主張被誤判為無證據支撐：多半是引用英文原文且主張中沒有數字或專有名詞，補上可對照錨點或同語言引文即可。
- `source_not_registered`：書目網址未先登錄，或使用了含追蹤參數的版本；先執行來源登錄後即可對上。
- digest 過期：修改程式或 contract 後未重建 registry，重新產生 digest 後再執行。
- Windows cp950 主控台輸出中文時報 `UnicodeEncodeError`：以 `PYTHONUTF8=1` 執行。

## Rollback path

- 本技能不改寫使用者既有檔案：帳本均為 append-only，`run_manifest.json` 與 `citation_map.json` 以暫存檔加原子替換寫入。
- 需要回復時，刪除 run 工作區內本輪新增的產物即可回到前一狀態；技能本身的 rollback 為 `git revert` 對應的發版 commit。
- 交付物覆寫必須同時具備 approval record 與 `overwrite=true`，否則預設拒絕，避免不可逆的覆蓋。

## 未執行項目

- Frozen live trajectory benchmark：SKIPPED。未在固定 host、model 與資料集上量測路由準確率、任務完成率或 token 成本，因此不提出速度、品質或取代既有技能的宣稱。
