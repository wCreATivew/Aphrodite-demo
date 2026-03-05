# router_regression_set_v1（固定 35 条）问题定位与直接修复

你强调“不要补集”，那就只针对这 35 条做可落地修复。核心不是扩数据，而是**评测口径不一致**，导致你看到的“结果不理想”被放大或被误读。

## 1) 当前最关键的 4 个口径问题

1. **`CONFIRM_REQUIRED` 同时以两种方式表达**
   - 既有 `expected_action=CONFIRM_REQUIRED`，又有 `needs_confirm=true`。
   - 结果：动作和确认被混在一个指标里，错因不可分。

2. **scope 是多值，但旧评测按单值判等**
   - 如 `expected_scope=["MAIN","PROJECT_ONLY"]`，旧逻辑只取第一个。
   - 结果：模型命中第二个合法 scope 也会被判错。

3. **确认指标只看“漏确认”，不罚“乱确认”**
   - 旧逻辑 `expected_confirm=false` 时默认记对。
   - 结果：confirm 指标虚高。

4. **缺少误触发核心指标**
   - 你关心“误触发执行链”，但旧报告没给 FTR。
   - 结果：无法直接判断“激进触发”是否被抑制。

---

## 2) 已改的修复（不改数据，仅改评测）

本次我把评测脚本改成“同一套 35 条数据也能稳定诊断”：

- 支持多 scope 命中（`pred_scope in expected_scopes`）。
- confirm 改为严格对齐（预测 true/false 都要和期望一致）。
- 新增 `confirm_f1`（同时惩罚漏确认和乱确认）。
- 新增 `action_macro_f1`（缓解类别不均衡对 accuracy 的误导）。
- 新增 `false_trigger_rate`（在非执行样本上被误判为执行的比例）。
- 新增 `error_buckets`（action/scope/confirm 三类错因计数）。

---

## 3) 你现在就能用的命令

```bash
python scripts/eval_router.py --input router_regression_set_v1.jsonl --report reports/router_report.json
```

重点看这几个字段：

- `action_macro_f1`
- `confirm_f1`
- `false_trigger_rate`
- `error_buckets`
- `confusion_matrix`

这样你不用补任何样本，也能明确知道：
- 是 `CHAT↔ASK_CLARIFY` 在掉点，
- 还是 confirm 逻辑有偏差，
- 还是 scope 判定规则出问题。

---

## 4) 结论

在“只用现有 35 条”的约束下，最有效的动作不是再写建议，而是先把评测变成**可解释、可归因、可比较**。这次改动就是为了解决这个问题。
