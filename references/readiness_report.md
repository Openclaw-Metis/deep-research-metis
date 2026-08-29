# Readiness Report

本檔是 deep-research-metis `2026.8.30` 的發布證據，只記錄本輪實際執行且可重跑的檢查。未執行的 live benchmark 明確標為 `SKIPPED`，不拿舊版證據或人工判斷代替。

## 最終 Gate

- Skill version：2026.8.30
- Audit date：2026-08-30
- 稽核環境：local Windows、Python 3.10.11
- 候選來源：`v2026.8.29` / `dada22935582e7dad2e49aece07c2c5a295b5853`
- Current status：PASS（本地決定性 evaluation、security、Code as Tool 與 publish release gate）
- 阻擋問題：無
- Frozen live benchmark：SKIPPED；不提出速度、真實 host 品質或取代其他 skill 的宣稱

## 本版變更與 failure evidence

本輪由四個可重現 failure 驅動，先加入 regression，再實作最小修正：

1. 書目自身的 `[N]` 被誤算成正文行內引用，會漏報 `entry_without_citation`。
2. `claims.jsonl` 以 append-only 方式混入舊草稿主張，續跑後可能驗證錯誤 revision。
3. `render_html` 沒有機械核對三項 gate freshness，approval 也只檢查欄位存在，未綁定 scope、target、subject digest 與期限。
4. registry 只綁 contract 與主 module，runtime metadata、共用 helper 與 bundled asset 的 drift 不會在執行前被攔截。

修正後，claims 與三項驗證產物皆綁定 report digest；HTML 只接受目前 revision 的三項 PASS 與有效 scoped approval；registry 另綁 runtime 與 bundled dependency digest。來源 URL 也只接受 http(s)，拒絕 userinfo credential，runner 的 JSON stdin/stdout 固定使用 UTF-8。

## 實際執行命令

```bash
python -B scripts/sync_registry_digests.py --registry-version 2026.8.30
python -m unittest discover -s tests -v
python -m compileall -q -f scripts tests
python skillops-studio/scripts/stage_gate.py <skill-path> --stage revise --json
python skillops-studio/scripts/stage_gate.py <skill-path> --stage evolve --json
python skillops-studio/scripts/stage_gate.py <skill-path> --stage evaluate --json
python skillops-studio/scripts/stage_gate.py <skill-path> --stage security --json
python skillops-studio/modules/skill-evaluation-validation/scripts/audit_tool_execution_skill.py <skill-path> --json
python skillops-studio/scripts/release_gate.py <skill-path> --stage publish --json
```

另以 PowerShell `ConvertFrom-Json` 逐一解析 `assets/`、`schemas/` 與 `tools/` 的 JSON，並執行 `git diff --check`；兩者皆成功。

## Gate 結果

| Gate | 結果 | 實際數字 |
| --- | --- | --- |
| `unittest` | PASS | 28/28 |
| Python compile | PASS | `scripts/` 與 `tests/` |
| revise / evolve / evaluate | PASS | 0 blocking finding |
| reference / orphan | PASS | 32 個 point-of-use resource，0 orphan |
| eval coverage | PASS | 15 個 eval，七種 tag、三種語言 |
| Code as Tool audit | PASS | 9 個 `group.function`、15 條 deterministic trace |
| security | PASS | 97 個掃描項目、0 error、2 warning、100% required analysis coverage |
| publish release gate | PASS | evaluation 與 security 均通過 |
| frozen live benchmark | SKIPPED | 未執行 |

兩個 security warning 都來自 `tests/test_deep_research_metis.py` 以 `subprocess.run(..., shell=False)` 呼叫固定 Python runner 的測試 harness；runtime 沒有 shell function、沒有 network call，也沒有把 shell 加入 `allowed-tools`。這些 finding 維持可見，不以放寬 production permission 消除。

## 功能與安全回歸

- 書目區與 code fence 的編號不再計入正文 `inline_citations`。
- 草稿更新後，`claims.jsonl` 原子替換為目前 revision；support gate 拒絕 claims／citation map digest 不一致。
- `structure_check.json`、`citation_map.json`、`claim_support.json` 必須全部 PASS 且 report digest 相同，否則渲染停止。
- approval 必須具備正確 scope、target、subject digest 與有效期限；錯誤或過期授權不產生 HTML。
- runtime metadata、module、`research_store.py` 與 lexicon 任一 digest stale 時，runner 在 import／invoke 前阻擋。
- 合法的完整驗證與綁定 approval 可透過 runner 成功產生自包含 HTML。
- 非 http(s) URL 與 userinfo credential 會被拒絕；query credential 仍在持久化前移除。

## Rollback path

- 上一個可用來源版本：Git tag `v2026.8.29`。
- 發布後若需撤回，以 `git revert` 回復完整 release commit；不得只還原 `SKILL.md` 而留下 scripts、contracts、runtime metadata 或 registry 的混合版本。
- Run 工作區內的 `sources.jsonl` 與 `evidence.jsonl` 保持 append-only；claims、verification artifacts、manifest 與 HTML 採原子替換。本技能不自動刪除使用者研究資料。

## 剩餘限制

- Frozen live trajectory benchmark 未執行，因此沒有 route accuracy、task completion、token cost 或 replacement claim。
