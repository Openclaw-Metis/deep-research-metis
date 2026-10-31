# Readiness Report

本檔是 deep-research-metis `2026.10.31` 的發布證據，只記錄本輪實際執行且可重跑的檢查。未執行的 live benchmark 明確標為 `SKIPPED`，不拿舊版證據或人工判斷代替。

## 最終 Gate

- Skill version：2026.10.31
- Audit date：2026-10-31
- 稽核環境：local Windows、Python 3.13.15、SkillOps validator 3.11.0
- 候選來源：`v2026.8.30` / `af40f39`
- 路線：`evolve`（失敗驅動修正）加 `revise`（遷移到模組索引）
- Current status：PASS（evaluation、security、Code as Tool 與 publish release gate）
- 阻擋問題：無
- Frozen live benchmark：SKIPPED；不提出速度、真實 host 品質、觸發準確率或取代其他 skill 的宣稱

## 本版變更與 failure evidence

上一版在現行 validator 下 revise、evaluate、security 與 publish gate 全部 FAIL，因為 tool-executor 規格已改為 `modules/<module>/REFERENCE.md` 索引。另以對抗案例重播舊版，確認下列可重現失敗，全部先寫成凍結基準或回歸測試再修正：

| 類型 | 舊版行為 | 修正 |
| --- | --- | --- |
| 誤放行 | 主張數字被改動（18% 寫成 81%）仍判 supported | 主張數字必須出現在所引引文內 |
| 誤放行 | 表格內的數字完全不受檢 | 表格資料列進入主張抽取 |
| 誤放行 | 標題含「資料來源」的正文章節被當成書目，其中主張全數跳過 | 書目判定加上內容檢查 |
| 誤放行 | 判定取決於引文寫入順序，可落回 unverifiable 放行 | 逐則判定後依固定順序取最強 |
| 誤放行 | manifest 接受與驗證產物矛盾的 PASS | 以 `manifest.gate-status-mismatch` 拒絕 |
| 誤擋 | `3.5 TWh`、`12.4%` 在小數點斷句，帶引用的數據句被切碎 | `.` 只在空白、行尾或引用前斷句 |
| 誤擋 | 硬換行段落被拆成未引用片段 | 相鄰行合併為一段 |
| 誤擋 | `[1, 2]`、`[1-3]`、全形括號不被視為引用，數字反被判未引用 | 共用 `citation_numbers` |
| 誤擋 | `## References`、編號清單書目、黏著中文標點的網址、中文路徑網址都失敗 | 別名、書目解析與網址正規化 |
| 誤擋 | 方法章節的檢索次數被要求引用 | 歸類為 `process` |
| 其他 | 超過 inline 上限時 status 與 findings 都被丟棄 | 摘要保留 status、計數、路徑與前 40 筆 finding |
| 其他 | 同一工作區可換研究問題，帳本混用 | `plan.run-dir-reused` |
| 其他 | 來源數低於計畫下限沒有任何 gate 察覺 | `source_count_below_plan` warning |
| 其他 | 書目錨點落在正文清單項，書目條目沒有錨點；頁尾宣稱所有主張都對應證據 | 錨點只在書目；頁尾只陳述已執行的檢查 |
| 其他 | `netflix.com` 被判為 community、`fake.gov.evil.com` 被判為 primary | 以完整網域比對 |

自審另修正一個新引入的風險：自動連結的網址字元類別原本允許引號，會讓文字跳出 `href` 屬性，已排除並加回歸測試。

## 凍結基準

`assets/evals/verification-benchmark.json` 含 15 個 development 與 28 個 held_out 案例，以人工判讀標註三項檢查應得的結論。commit `30632ae` 在修改任何驗證程式前凍結，held_out 只在驗證程式定稿後重播，事後未調整案例、標註或程式。

| Held-out 28 案例 | v2026.8.30 | 2026.10.31 |
| --- | --- | --- |
| 判定一致率 | 0.5000 | 0.9286 |
| 應擋案例攔截率（15 案例） | 0.6667 | 1.0000 |
| 誤放行 | 5 | 0 |
| 誤擋 | 9 | 2 |

`decide_candidate.py --min-delta 0.2` 判定 `ACCEPT`，pass-rate delta 0.4286。Development 為 0.20 → 1.00。

剩下兩個誤擋如實保留：

- `ho-en-accurate-paraphrase`：正確但用詞完全不同的改寫。字詞比對的已知限制，寫入疑難排解。
- `ho-zh-two-sources-two-numbers`：案例的第二則引文只有 7 字元，被 `MIN_QUOTE_LENGTH` 拒收，數字因此找不到。屬於案例設計問題，凍結後不修改；真實使用時 `rejected` 清單會顯示這件事。

## 實際執行命令

```bash
python -B scripts/sync_registry_digests.py --registry-version 2026.10.31
python -B -m unittest discover -s tests
python -B tests/verification_benchmark.py --split development
python -B tests/verification_benchmark.py --split held_out
python -B tests/verification_benchmark.py --skill-root <v2026.8.30 checkout> --split held_out
python -B skillops-studio/modules/skill-optimization/scripts/decide_candidate.py <comparison> --min-delta 0.2
python -B skillops-studio/scripts/stage_gate.py <skill-path> --stage revise --json
python -B skillops-studio/scripts/stage_gate.py <skill-path> --stage evolve --json
python -B skillops-studio/scripts/stage_gate.py <skill-path> --stage evaluate --json
python -B skillops-studio/scripts/stage_gate.py <skill-path> --stage security --json
python -B skillops-studio/scripts/stage_gate.py <skill-path> --stage package --json
python -B skillops-studio/scripts/release_gate.py <skill-path> --stage publish --json
python -B skillops-studio/modules/skill-evaluation-validation/scripts/audit_tool_execution_skill.py <skill-path> --json
python -B skillops-studio/modules/skill-evaluation-validation/scripts/audit_orphan_modules.py <skill-path> --json
```

Gate 在不含 `.git` 的匯出副本上執行，因為 `package_file_budget` 會把 `.git` 算進檔案數。

## 格式與結構檢查

| Gate | 結果 | 實際數字 |
| --- | --- | --- |
| revise / evolve / evaluate | PASS | 0 blocking finding |
| format | PASS | frontmatter 改用 `metadata.version`，0 warning |
| reference / orphan | PASS | 61 個被引用資源，84 條 point-of-use 連結，0 orphan |
| orphan modules | PASS | 7 個模組，皆有 route、playbook、tool 與 trace |
| discovery description | PASS | 採 domain-entrypoint，含 activation policy |
| package file budget | PASS | 69 個檔案，上限 100 |
| Code as Tool audit | PASS | 9 個函數、22 條決定性軌跡 |

## 要求與政策檢查

| Gate | 結果 | 實際數字 |
| --- | --- | --- |
| eval coverage | PASS | 24 個 eval，含 in-domain unsupported 與 action-object contrast |
| security | PASS | 0 error、2 warning |
| package gate | PASS | 必要 audit 全數通過 |
| publish release gate | PASS | evaluation 與 security 均通過 |
| optimize stage | BLOCKED | 需要 live benchmark 證據；本次未走此路線，也不做對應宣稱 |
| frozen live benchmark | SKIPPED | 未執行 |

兩個 security warning 都來自測試 harness 以 `subprocess.run(..., shell=False)` 呼叫固定 Python runner；runtime 沒有 shell function、沒有 network call，也沒有把 shell 加入 `allowed-tools`。這些 finding 維持可見，不以放寬 production permission 消除。

## 常見錯誤檢查

- `unittest`：58/58 PASS。新增 30 項涵蓋切句、引用解析、數量判定、書目判定、數字比對、manifest 核對、計畫保護、結果摘要與 HTML 跳脫。
- 端到端：以一份中文比較報告經 runner 走完九個函數，含矛盾 gate 被拒、第二個研究問題被擋與 `replace_plan`。渲染結果以 HTML parser 確認行內引用皆連到書目錨點、0 條斷連、標籤成對、無 script 或外部資源；未在瀏覽器目視版面。
- 靜態確認 `scripts/` 符合 Python 3.9 語法。實際只在 Python 3.13 執行，3.9 未實測。
- 函數 ID 與既有 payload 欄位不變；`replace_plan` 是新增的選填欄位。

## 相容性

- 驗證變嚴：舊報告若有與引文不符的數字、未引用的表格數字，現在會 FAIL。這是本版的目的。
- `claims.jsonl` 新增 `origin` 欄位與 `process` 類別，舊快照仍可計分。
- 中文路徑網址的 `source_id` 會與舊版不同；`check_citations` 比對前會重新正規化帳本網址，舊帳本仍可比對。
- `tools/registry.json` 的 `playbook_ids` 改為只列函數所屬模組擁有的 playbook，實際 allowlist 以 `schemas/skill-contract.json` 為準。

## Rollback path

- 上一個可用來源版本：Git tag `v2026.8.30`。
- 發布後若需撤回，以 `git revert` 回復完整 release merge；不得只還原 `SKILL.md` 而留下 scripts、contracts、runtime metadata 或 registry 的混合版本。
- Run 工作區內的 `sources.jsonl` 與 `evidence.jsonl` 保持 append-only；claims、verification artifacts、manifest 與 HTML 採原子替換。本技能不自動刪除使用者研究資料。

## 剩餘限制

- 支撐度比對字詞與數字，不理解語意：否定、因果、適用範圍錯誤可能拿到 `supported`。已在 playbook 加入語意複核步驟，這是指令層控制，尚無量測。
- 數字比對不比單位也不換算，`18 GW` 對 `18 MW` 會通過，`40 億美元` 對 `4 billion` 會不符。年份不參與比對，寫錯年份不會被抓到。
- 引文是否真的逐字出自來源仍由 agent 負責，函數不連網查證。
- `description` 改為 domain-entrypoint 後未跑真實 host 的 trigger eval，實際觸發行為的變化未量測。
- 基準的案例與標註由同一位作者撰寫，held_out 分數代表這組案例上的表現，不是對真實報告的準確率估計。
