from __future__ import annotations

from .schema import default_interpreted_event
from .validators import validate_interpreted_event


class InputInterpreter:
    ENGINEERING_KEYS = [
        "runtime", "orchestrator", "_brain_loop", "_presence_min_flow", "_emit_presence_reply",
        "stateauthority", "presencetrace", "memory_gate", "relationship_guard", "action_mixer",
        "trace", "wrapper", "route", "api", "fallback", "test", "pytest", "golden case", "工程", "主链路",
    ]
    VISUAL_KEYS = ["商业手游", "ai 女友", "偶像感", "恋爱游戏", "视觉", "原画", "安静", "克制", "暖灰", "旧纸黄", "轻盈", "live2d", "renderer", "avatar", "画风"]
    DEP_KEYS = ["我只需要你", "不能离开我", "我只相信你", "没有你不行", "不需要别人", "只有你"]
    UNCERTAIN_KEYS = ["不确定", "不知道", "是不是", "会不会", "太自我", "做不出来", "方向错了", "有点担心"]

    def interpret(self, raw_input: str, context: dict | None = None) -> dict:
        text = str(raw_input or "").strip()
        low = text.lower()
        out = default_interpreted_event()
        warnings = []
        context = context or {}

        engineering_hit = any(k in low for k in self.ENGINEERING_KEYS)
        visual_hit = any(k in low for k in self.VISUAL_KEYS)
        dep_hit = any(k in text for k in self.DEP_KEYS) or any(k in low for k in ["only need you", "only you"])
        uncertain_hit = any(k in text for k in self.UNCERTAIN_KEYS)
        project_origin_hit = any(k in text for k in ["起点", "最早", "之前文档", "body-mind", "presence loop", "Aphrodite"])
        correction_hit = text.startswith(("不是", "不对")) or any(k in text for k in ["我说的是", "刚才", "我的意思是", "更准确地说"])
        supplement_hit = text.startswith(("补充", "补充一下")) or "补充" in text
        ambiguous_followup = text in {"对，就这个。", "对，就这个", "就这个", "嗯", "好"}

        if dep_hit:
            out["semantic_event"].update({"event_type": "dependency_expression", "speech_act": "dependency_claim"})
            out["relationship_signal"].update({"dependency_risk": 0.92, "boundary_pressure": 0.85, "over_intimacy_risk": 0.85})
            out["boundary_signal"].update({"needs_boundary": True})
            out["goal_signal"].update({"asks_for_presence": 0.88, "asks_for_reassurance": 0.82})
            out["performance_signal"].update({"requires_softness": 0.75, "requires_direct_eye_contact": 0.3})
            out["confidence"].update({"boundary_signal": 0.85, "semantic_event": 0.8})

        if correction_hit:
            out["semantic_event"].update({"event_type": "correction", "speech_act": "correction"})
            out["goal_signal"].update({"asks_for_analysis": max(out["goal_signal"]["asks_for_analysis"], 0.6)})
            warnings.append("context_dependent")

        if supplement_hit and out["semantic_event"]["event_type"] != "correction":
            out["semantic_event"].update({"event_type": "supplement", "speech_act": "supplement"})
            out["goal_signal"].update({"asks_for_analysis": max(out["goal_signal"]["asks_for_analysis"], 0.5), "asks_for_solution": max(out["goal_signal"]["asks_for_solution"], 0.5)})
            warnings.append("context_dependent")

        if project_origin_hit:
            out["semantic_event"].update({"event_type": "memory_reference", "topic": "project_origin"})
            out["memory_trigger_signal"].update({"memory_relevance": 0.85, "memory_type": "project_origin", "recall_importance": 0.8, "self_narrative_relevance": 0.75})
            out["performance_signal"].update({"requires_pause": 0.75, "requires_stillness": 0.7})

        if visual_hit:
            if out["semantic_event"]["event_type"] in {"unknown", "casual_chat"}:
                out["semantic_event"].update({"event_type": "aesthetic_judgment", "speech_act": "evaluation"})
            out["semantic_event"]["topic"] = "visual_direction"
            out["memory_trigger_signal"].update({"memory_relevance": 0.65, "memory_type": "visual_direction", "recall_importance": 0.6})
            out["goal_signal"]["asks_for_solution"] = max(out["goal_signal"]["asks_for_solution"], 0.72)
            out["performance_signal"]["requires_lightness"] = max(out["performance_signal"]["requires_lightness"], 0.65)
            if any(k in low for k in ["ai 女友", "恋爱", "companion drift"]):
                out["relationship_signal"]["over_intimacy_risk"] = max(out["relationship_signal"]["over_intimacy_risk"], 0.7)

        if engineering_hit:
            if out["semantic_event"]["event_type"] in {"unknown", "casual_chat"}:
                et = "technical_question" if ("?" in text or "？" in text or "是不是" in text) else "project_planning"
                out["semantic_event"].update({"event_type": et})
            if "不要改公开 api" in low or "不要改api" in low:
                out["semantic_event"]["topic"] = "engineering_constraint"
            else:
                out["semantic_event"]["topic"] = "runtime_or_engineering"
            out["goal_signal"].update({"asks_for_analysis": max(out["goal_signal"]["asks_for_analysis"], 0.72), "asks_for_solution": max(out["goal_signal"]["asks_for_solution"], 0.62)})
            out["memory_trigger_signal"].update({"memory_relevance": max(out["memory_trigger_signal"]["memory_relevance"], 0.5), "memory_type": "engineering_plan", "recall_importance": max(out["memory_trigger_signal"]["recall_importance"], 0.58)})
            out["confidence"]["semantic_event"] = max(out["confidence"]["semantic_event"], 0.75)

        if "下一阶段" in text or "先别做" in text:
            out["semantic_event"].update({"event_type": "project_planning", "speech_act": "instruction"})
            out["goal_signal"].update({"asks_for_analysis": max(out["goal_signal"]["asks_for_analysis"], 0.55), "asks_for_solution": max(out["goal_signal"]["asks_for_solution"], 0.55)})
            out["memory_trigger_signal"].update({"memory_relevance": 0.6, "memory_type": "engineering_plan"})

        if uncertain_hit:
            if out["semantic_event"]["event_type"] == "unknown":
                out["semantic_event"]["event_type"] = "self_disclosure"
            out["affective_signal"]["uncertainty"] = max(out["affective_signal"]["uncertainty"], 0.78)
            out["goal_signal"].update({"asks_for_reflection": 0.72, "asks_for_reassurance": 0.55})
            out["relationship_signal"]["recognition_need"] = max(out["relationship_signal"]["recognition_need"], 0.68)

        if ambiguous_followup:
            out["semantic_event"]["event_type"] = "supplement" if context.get("previous_topic") else "unknown"
            out["semantic_event"]["speech_act"] = "supplement" if context.get("previous_topic") else "unknown"
            out["affective_signal"]["uncertainty"] = max(out["affective_signal"]["uncertainty"], 0.7)
            out["confidence"].update({"semantic_event": 0.35, "goal_signal": 0.35})
            warnings.append("context_needed")
            if context.get("previous_topic"):
                out["semantic_event"]["topic"] = str(context.get("previous_topic"))
                warnings.append("context_inherited")

        if out["semantic_event"]["event_type"] == "unknown" and any(k in low for k in ["bug", "runtime", "python", "code", "怎么", "为什么"]):
            out["semantic_event"].update({"event_type": "technical_question", "topic": "runtime_or_engineering", "speech_act": "question"})

        if "?" in text or "？" in text:
            out["semantic_event"]["explicit_question"] = True
            out["semantic_event"]["requires_answer"] = True

        out["warnings"] = list(dict.fromkeys(warnings))
        return validate_interpreted_event(out)
