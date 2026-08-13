"""Network-incapable question-aware deterministic Tarot interpretation adapter."""

# ruff: noqa: E501, RUF001

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Final

from creativedeploy_api.schemas.arcana import TarotInterpretationDocument

_DOMAIN_LABELS: Final[dict[str, dict[str, str]]] = {
    "love_relationship": {"zh-CN": "感情与关系", "en-US": "love and relationship"},
    "career_work": {"zh-CN": "事业与工作", "en-US": "career and work"},
    "money_finance": {"zh-CN": "金钱与财务", "en-US": "money and finance"},
    "self_growth": {"zh-CN": "自我成长", "en-US": "self-growth"},
    "decision": {"zh-CN": "选择与决策", "en-US": "decision-making"},
    "family_social": {"zh-CN": "家庭与社交", "en-US": "family and social relationships"},
    "general": {"zh-CN": "综合反思", "en-US": "general reflection"},
}
_INTENT_LABELS: Final[dict[str, dict[str, str]]] = {
    "outcome_tendency": {"zh-CN": "结果趋势", "en-US": "outcome tendency"},
    "advice": {"zh-CN": "行动建议", "en-US": "advice"},
    "obstacle": {"zh-CN": "阻碍识别", "en-US": "obstacle identification"},
    "relationship_dynamic": {"zh-CN": "关系互动", "en-US": "relationship dynamics"},
    "decision_comparison": {"zh-CN": "方案比较", "en-US": "decision comparison"},
    "timing": {"zh-CN": "时间范围", "en-US": "timing"},
    "self_reflection": {"zh-CN": "自我反思", "en-US": "self-reflection"},
}
_TEMPORAL_LABELS: Final[dict[str, dict[str, str]]] = {
    "past": {"zh-CN": "过去", "en-US": "the past"},
    "present": {"zh-CN": "当下", "en-US": "the present"},
    "near_future": {"zh-CN": "近期", "en-US": "the near future"},
    "explicit_period": {"zh-CN": "明确时间段", "en-US": "an explicit time period"},
    "unspecified": {"zh-CN": "未限定时间", "en-US": "an unspecified time frame"},
}


class TarotFixtureInterpreter:
    provider_key = "fixture_local"
    model_id = "fixture-tarot-question-aware-v2"
    adapter_version = "arcana-fixture-adapter-v3"
    prompt_version = 3

    @staticmethod
    def canonical_input_hash(payload: Mapping[str, object]) -> str:
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _mapped(value: object, message: str) -> Mapping[str, object]:
        if not isinstance(value, Mapping):
            raise ValueError(message)
        return value

    def interpret(self, payload: Mapping[str, object]) -> tuple[str, TarotInterpretationDocument]:
        digest = self.canonical_input_hash(payload)
        locale = payload.get("generation_locale")
        question = payload.get("question")
        cards = payload.get("cards")
        analysis = self._mapped(payload.get("question_analysis"), "missing question analysis")
        raw_relationships = payload.get("relationship_signals")
        if (
            locale not in {"zh-CN", "en-US"}
            or not isinstance(question, str)
            or not question.strip()
            or not isinstance(cards, Sequence)
            or len(cards) != 3
            or not isinstance(raw_relationships, Sequence)
            or len(raw_relationships) < 3
        ):
            raise ValueError("invalid Arcana fixture input")
        domain = analysis.get("domain")
        intents = analysis.get("intents")
        temporal_frame = analysis.get("temporal_frame")
        temporal_anchor = analysis.get("temporal_anchor")
        if (
            not isinstance(domain, str)
            or not isinstance(intents, Sequence)
            or not all(isinstance(item, str) for item in intents)
            or not isinstance(temporal_frame, str)
            or (temporal_anchor is not None and not isinstance(temporal_anchor, str))
        ):
            raise ValueError("invalid question analysis")

        prepared_cards: list[dict[str, str]] = []
        positions: list[dict[str, object]] = []
        for raw_value in cards:
            raw = self._mapped(raw_value, "invalid Arcana fixture card")
            required = {
                key: raw.get(key)
                for key in (
                    "meaning",
                    "name",
                    "position_name",
                    "position_key",
                    "orientation",
                    "card_id",
                    "position_context",
                    "question_context",
                    "primary_knowledge_id",
                )
            }
            if not all(isinstance(value, str) and value for value in required.values()):
                raise ValueError("invalid Arcana fixture card fields")
            card = {key: str(value) for key, value in required.items()}
            card["suit"] = str(raw.get("suit") or "")
            card["theme"] = str(raw.get("theme") or "")
            prepared_cards.append(card)
            if locale == "zh-CN":
                contribution = (
                    f"{card['name']}以{'逆位' if card['orientation'] == 'reversed' else '正位'}落在"
                    f"{card['position_name']}，在“{question}”里承担的是{card['position_context']}。"
                    f"它把“{card['meaning']}”具体化为：{card['question_context']}"
                )
            else:
                contribution = (
                    f"{card['name']} appears {card['orientation']} in {card['position_name']}. "
                    f"For “{question}”, this position is {card['position_context']}. Its "
                    f"meaning—{card['meaning']}—is applied as follows: {card['question_context']}"
                )
            positions.append(
                {
                    "position_key": card["position_key"],
                    "card_id": card["card_id"],
                    "orientation": card["orientation"],
                    "headline": f"{card['position_name']} / {card['name']}",
                    "contribution": contribution,
                }
            )

        past, present, future = prepared_cards
        period_zh = temporal_anchor or "你关心的时间范围"
        period_en = temporal_anchor or "the time frame you asked about"
        future_is_reversed = future["orientation"] == "reversed"
        future_is_constructive = not future_is_reversed and (
            future["suit"] in {"cups", "pentacles"}
            or any(
                marker in future["theme"].lower()
                for marker in ("lovers", "star", "sun", "world", "empress")
            )
        )
        if locale == "zh-CN":
            if domain == "love_relationship":
                if future_is_reversed:
                    thesis = (
                        f"直接回答“{question}”：目前没有足够牌面依据说{period_zh}一定会出现正缘。"
                        f"未来位{future['name']}逆位更像延迟或阻碍信号：{future['question_context']}"
                        f"是否出现可发展的连接，取决于你先处理{present['name']}指出的当下问题："
                        f"{present['question_context']}"
                    )
                elif future_is_constructive:
                    thesis = (
                        f"直接回答“{question}”：这组三张牌不保证{period_zh}一定出现所谓正缘，但"
                        f"未来位{future['name']}让稳定关系的可能性值得观察：{future['question_context']}"
                        f"它能否发展，取决于你是否先处理{present['name']}指出的当下问题："
                        f"{present['question_context']}"
                    )
                else:
                    thesis = (
                        f"直接回答“{question}”：{period_zh}存在遇见或推进关系的可能，但牌面不足以"
                        f"保证这是正缘。未来位{future['name']}给出的条件是：{future['question_context']}"
                        f"关键仍是你如何回应{present['name']}指出的当下问题："
                        f"{present['question_context']}"
                    )
                action_focus = "区分真实的关系开放度、现实稳定性与因为焦虑而产生的确定性需求"
            else:
                thesis = (
                    f"直接回答“{question}”：{future['name']}显示的是“{future['meaning']}”这一"
                    f"有条件的方向，不是保证。更关键的变量是你如何处理当下{present['name']}所指向的"
                    f"“{present['meaning']}”，而不是等待未来牌自行兑现。"
                )
                action_focus = "把牌面趋势转成一个可观察、可复盘的小选择"
            synthesis = (
                f"因果线索从{past['name']}开始：{past['question_context']}这也解释了为什么"
                f"{present['name']}把当前任务推到问题中心：{present['question_context']}"
                "核心张力不是在希望与悲观之间猜结果，而是辨认旧经验何时在保护你、何时已变成"
                f"自动反应。转折发生在这个当下条件被实际处理之后；届时{future['name']}所提示的"
                f"方向才有现实基础：{future['question_context']}"
                f"因此，对原问题最有用的结论是：{action_focus}；牌阵提供条件和方向，不替你断言结果。"
            )
            actionable = [
                f"围绕“{question}”，写下一个由{past['name']}所指旧模式触发的具体情境。",
                f"从{present['name']}指出的当下任务中选一个七天内可完成的小行动："
                f"{present['question_context']}",
                f"到{period_zh}时，只用可观察的互惠、边界与稳定性检验{future['name']}所示趋势。",
            ]
            prompts = [
                f"关于“{question}”，你最想从牌里得到保证的部分是什么？",
                f"{past['name']}的旧模式如何影响你现在面对{present['name']}？",
                f"若{future['name']}只是趋势，什么现实证据会让你更信任或修正它？",
            ]
            uncertainty = (
                f"本地确定性 Fixture 解读（{digest[:8]}）只用于个人反思。它回应的是可能性、条件与"
                "行动空间，不保证正缘、结果或精确时间，也不替代医疗、法律或财务专业意见。"
            )
        else:
            if domain == "love_relationship":
                if future_is_reversed:
                    thesis = (
                        f"Direct answer to “{question}”: the cards do not provide enough basis to "
                        f"say a destined partner will appear during {period_en}. Reversed "
                        f"{future['name']} is instead a delay or barrier signal: "
                        f"{future['question_context']} Any viable connection depends on addressing "
                        f"the present issue named by {present['name']}: {present['question_context']}"
                    )
                elif future_is_constructive:
                    thesis = (
                        f"Direct answer to “{question}”: the spread does not guarantee a destined "
                        f"partner during {period_en}, but future-position {future['name']} makes a "
                        f"stable connection worth observing: {future['question_context']} Whether "
                        f"it develops depends on the present issue named by {present['name']}: "
                        f"{present['question_context']}"
                    )
                else:
                    thesis = (
                        f"Direct answer to “{question}”: a connection may emerge or develop during "
                        f"{period_en}, but the cards cannot guarantee it is destined. Future-position "
                        f"{future['name']} sets this condition: {future['question_context']} The key "
                        f"is how you respond to the present issue named by {present['name']}: "
                        f"{present['question_context']}"
                    )
                action_focus = "distinguish real openness, reciprocity, and stability from a need for certainty"
            else:
                thesis = (
                    f"Direct answer to “{question}”: {future['name']} describes "
                    f"{future['meaning']} as a conditional direction, not a promise. The active "
                    f"variable is how you handle {present['name']}'s {present['meaning']} now."
                )
                action_focus = "turn the tendency into one observable, reviewable choice"
            synthesis = (
                f"The causal line begins with {past['name']}: {past['question_context']} That "
                f"explains why {present['name']} places this task at the center now: "
                f"{present['question_context']} The central tension is not choosing between hope "
                "and pessimism, but noticing when an old response protects you and when it has "
                f"become automatic. Once that condition is handled, {future['name']} can become a "
                f"plausible direction in {period_en}: {future['question_context']} The useful "
                f"answer to the original question is to {action_focus}; "
                "the spread supplies conditions and direction, not certainty."
            )
            actionable = [
                f"For “{question}”, name one concrete situation triggered by {past['name']}'s old pattern.",
                f"Choose one small action within seven days from {present['name']}'s present task: "
                f"{present['question_context']}",
                f"At {period_en}, evaluate {future['name']}'s direction using observable reciprocity, boundaries, and stability.",
            ]
            prompts = [
                f"What part of “{question}” are you hoping the cards will guarantee?",
                f"How does {past['name']}'s old pattern shape the way you meet {present['name']} now?",
                f"If {future['name']} is a tendency, what evidence would strengthen or revise it?",
            ]
            uncertainty = (
                f"This deterministic local Fixture interpretation ({digest[:8]}) supports reflection "
                "on conditions, tendencies, and agency. It does not guarantee a partner, outcome, "
                "or exact timing, and is not medical, legal, or financial advice."
            )

        relationship_analysis: list[dict[str, str]] = []
        for index, raw_signal in enumerate(raw_relationships[:4]):
            signal = self._mapped(raw_signal, "invalid relationship signal")
            kind = signal.get("kind")
            headline = signal.get("headline")
            content = signal.get("content")
            signal_id = signal.get("signal_id")
            if not all(
                isinstance(value, str) and value for value in (kind, headline, content, signal_id)
            ):
                raise ValueError("invalid relationship signal fields")
            output_kind = {
                "transition": "relationship" if index == 0 else "trend",
                "reinforcement": "relationship",
                "pattern": "relationship",
                "tension": "tension",
                "turning_point": "turning_point",
            }.get(str(kind), "relationship")
            relationship_analysis.append(
                {"kind": output_kind, "headline": str(headline), "content": str(content)}
            )

        knowledge_basis = []
        for raw_value in cards:
            raw = self._mapped(raw_value, "invalid Arcana fixture provenance")
            provenance = self._mapped(raw.get("provenance"), "invalid Arcana fixture provenance")
            knowledge_basis.append(
                {
                    "card_id": str(raw["card_id"]),
                    "knowledge_id": str(raw["primary_knowledge_id"]),
                    "source_id": str(provenance["source_id"]),
                    "source_title": str(provenance["source_title"]),
                    "retrieval_mode": "repository_local_only",
                }
            )

        domain_label = _DOMAIN_LABELS.get(str(domain), {}).get(str(locale), str(domain))
        intent_labels = [
            _INTENT_LABELS.get(str(intent), {}).get(str(locale), str(intent)) for intent in intents
        ]
        time_label = temporal_anchor or _TEMPORAL_LABELS.get(temporal_frame, {}).get(
            str(locale), temporal_frame
        )
        document = TarotInterpretationDocument.model_validate(
            {
                "schema_version": "tarot-reading.v2",
                "generation_locale": locale,
                "question_restatement": (
                    f"问题是“{question}”。本次分析聚焦{domain_label}，重点为{'、'.join(intent_labels)}，"
                    f"时间框架为{time_label}。"
                    if locale == "zh-CN"
                    else f"The question is “{question}”. It focuses on {domain_label}, with "
                    f"{', '.join(intent_labels)} and time frame {time_label}."
                ),
                "summary": thesis,
                "positions": positions,
                "synthesis": synthesis,
                "relationship_analysis": relationship_analysis,
                "actionable_reflections": actionable,
                "reflection_prompts": prompts,
                "knowledge_basis": knowledge_basis,
                "uncertainty": uncertainty,
            }
        )
        return digest, document
