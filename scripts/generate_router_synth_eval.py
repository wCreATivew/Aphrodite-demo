from __future__ import annotations

import json
import random
from pathlib import Path

random.seed(42)

PROFILES = ["general", "developer", "hybrid", "learner", "companion"]

CHAT_TEMPLATES = [
    "你怎么看待{topic}？",
    "我最近在想{topic}，你觉得靠谱吗？",
    "聊聊{topic}吧，不用执行任何操作。",
    "我有点{mood}，你陪我说两句。",
    "你觉得{topic}会不会被高估了？",
]

ASK_TEMPLATES = [
    "这个有点不太对劲。",
    "你看看这个。",
    "我感觉有问题但说不上来。",
    "这个能不能做得更好一点？",
    "我想让它更自动一点，你帮我想想办法。",
]

TOOL_TEMPLATES = [
    "帮我写一篇关于{topic}的短文案。",
    "请给我一个{days}天学习计划，主题是{topic}。",
    "帮我总结一下{topic}的优缺点。",
    "给我{n}个标题和{m}个标签，主题是{topic}。",
    "请解释{topic}并给一个简短模板。",
]

EXEC_LIGHT_TEMPLATES = [
    "帮我检查这个项目里可能的{issue}隐患。",
    "请在仓库里排查{issue}并给修复建议。",
    "帮我把这个配置调得更保守一点，减少误触发。",
    "帮我在本地代码里定位{issue}瓶颈。",
    "请执行一次轻量诊断，看看{issue}问题。",
]

EXEC_HEAVY_TEMPLATES = [
    "帮我批量修改仓库配置并推到主分支。",
    "请自动迭代修复并跑回归后合并到main。",
    "帮我删除旧文件并发布新版本。",
    "请跨系统同步配置并执行部署流程。",
    "帮我覆盖线上配置然后重启服务。",
]

TOPICS = ["强化学习", "AI Agent", "检索增强", "自动化办公", "代码评审", "提示词工程"]
MOODS = ["焦虑", "迷茫", "疲惫", "烦躁"]
ISSUES = ["性能", "安全", "稳定性", "触发", "延迟"]


def make_rows(total: int = 200):
    rows = []
    buckets = [
        ("CHAT", CHAT_TEMPLATES),
        ("ASK_CLARIFY", ASK_TEMPLATES),
        ("TOOL_LIGHT", TOOL_TEMPLATES),
        ("AGENT_EXECUTE_LIGHT", EXEC_LIGHT_TEMPLATES),
        ("AGENT_EXECUTE_HEAVY", EXEC_HEAVY_TEMPLATES),
    ]
    per = total // len(buckets)
    idx = 1

    for action, templates in buckets:
        for _ in range(per):
            tpl = random.choice(templates)
            text = tpl.format(
                topic=random.choice(TOPICS),
                mood=random.choice(MOODS),
                issue=random.choice(ISSUES),
                days=random.choice([7, 14, 30]),
                n=random.choice([3, 5, 8]),
                m=random.choice([5, 10, 12]),
            )

            if action in {"AGENT_EXECUTE_LIGHT", "AGENT_EXECUTE_HEAVY"}:
                scope = ["PROJECT_ONLY"]
            else:
                scope = ["MAIN"]

            needs_confirm = action == "AGENT_EXECUTE_HEAVY"
            if action == "CHAT" and random.random() < 0.15:
                needs_confirm = True

            rows.append(
                {
                    "id": f"s{idx:04d}",
                    "target_profile": random.choice(PROFILES),
                    "input": text,
                    "expected_action": action,
                    "expected_scope": scope,
                    "needs_confirm": needs_confirm,
                }
            )
            idx += 1

    random.shuffle(rows)
    return rows


def main() -> None:
    out = Path("evals/router_regression_synth_200.jsonl")
    rows = make_rows(200)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
