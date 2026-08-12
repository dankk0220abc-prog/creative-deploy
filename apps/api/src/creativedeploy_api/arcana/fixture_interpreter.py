"""Network-incapable deterministic Tarot interpretation adapter."""

# ruff: noqa: E501, RUF001

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from creativedeploy_api.schemas.arcana import TarotInterpretationDocument


class TarotFixtureInterpreter:
    provider_key = "fixture_local"
    model_id = "fixture-tarot-structured-v1"
    adapter_version = "arcana-fixture-adapter-v2"
    prompt_version = 2

    @staticmethod
    def canonical_input_hash(payload: Mapping[str, object]) -> str:
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    def interpret(self, payload: Mapping[str, object]) -> tuple[str, TarotInterpretationDocument]:
        digest = self.canonical_input_hash(payload)
        locale = payload.get("generation_locale")
        cards = payload.get("cards")
        if locale not in {"zh-CN", "en-US"} or not isinstance(cards, Sequence) or len(cards) != 3:
            raise ValueError("invalid Arcana fixture input")
        positions: list[dict[str, object]] = []
        prepared_cards: list[dict[str, object]] = []
        for raw in cards:
            if not isinstance(raw, Mapping):
                raise ValueError("invalid Arcana fixture card")
            meaning = raw.get("meaning")
            card_name = raw.get("name")
            position_name = raw.get("position_name")
            orientation = raw.get("orientation")
            if not all(
                isinstance(value, str) for value in (meaning, card_name, position_name, orientation)
            ):
                raise ValueError("invalid Arcana fixture card fields")
            facets = raw.get("semantic_facets")
            if not isinstance(facets, Sequence) or not all(
                isinstance(item, str) for item in facets
            ):
                raise ValueError("invalid Arcana fixture knowledge context")
            facet_text = "；".join(facets) if locale == "zh-CN" else "; ".join(facets)
            is_reversed = orientation == "reversed"
            if locale == "zh-CN":
                headline = f"{position_name} / {card_name}"
                contribution = (
                    f"{card_name}以{'逆位' if is_reversed else '正位'}落在{position_name}。"
                    f"它把“{meaning}”带进这里，并提示{facet_text}。"
                    "把它作为辨认经验的线索，而不是对结果的宣判。"
                )
            else:
                headline = f"{position_name} / {card_name}"
                contribution = (
                    f"{card_name} appears {orientation} in the {position_name} position. "
                    f"It brings {meaning} into view, with {facet_text}. Treat this as a cue "
                    "for discernment rather than a verdict."
                )
            positions.append(
                {
                    "position_key": raw.get("position_key"),
                    "card_id": raw.get("card_id"),
                    "orientation": orientation,
                    "headline": headline,
                    "contribution": contribution,
                }
            )
            prepared_cards.append(
                {"name": card_name, "meaning": meaning, "orientation": orientation}
            )
        past, present, future = prepared_cards
        provenance = [raw.get("provenance") for raw in cards if isinstance(raw, Mapping)]
        if not all(isinstance(item, Mapping) for item in provenance):
            raise ValueError("invalid Arcana fixture provenance")
        if locale == "zh-CN":
            document = {
                "schema_version": "tarot-reading.v2",
                "generation_locale": locale,
                "question_restatement": (
                    f"你想借这次阅读看清的是“{payload.get('question')}”。以下从已保存的三张牌出发，"
                    "把它放回可选择、可调整的现实脉络里。"
                ),
                "summary": (
                    f"{past['name']}留下的“{past['meaning']}”成为背景；"
                    f"{present['name']}把注意力带到当下的“{present['meaning']}”；"
                    f"{future['name']}则把未来打开为“{future['meaning']}”这一可调整的方向。"
                ),
                "positions": positions,
                "synthesis": (
                    f"从过去到现在，这组牌不是要求你否定{past['name']}所指向的经验，"
                    f"而是请你带着它进入{present['name']}提出的当下工作。"
                    f"如果你能分辨“{past['meaning']}”中哪些部分仍值得保留、哪些已变成惯性，"
                    f"{future['name']}的“{future['meaning']}”就更可能成为下一步的方向，而非被动等待的结果。"
                ),
                "relationship_analysis": [
                    {
                        "kind": "relationship",
                        "headline": "过去如何进入现在",
                        "content": f"{past['name']}与{present['name']}形成一条线：过去的{past['meaning']}正在影响你如何理解当下的{present['meaning']}。",
                    },
                    {
                        "kind": "trend",
                        "headline": "趋势并非命定",
                        "content": f"{present['name']}到{future['name']}显示的不是保证，而是当下选择持续时，可能向“{future['meaning']}”发展的趋势。",
                    },
                    {
                        "kind": "tension",
                        "headline": "需要辨认的拉力",
                        "content": f"当{past['orientation']}的{past['meaning']}遇到{present['orientation']}的{present['meaning']}，你可能需要区分真正的需要与自动反应。",
                    },
                    {
                        "kind": "turning_point",
                        "headline": "可行动的转折点",
                        "content": f"转折不在未来牌自行发生，而在你能否把{present['name']}的提醒落实成一个小而可观察的选择。",
                    },
                ],
                "actionable_reflections": [
                    f"写下一个仍受“{past['meaning']}”影响的具体情境，并标出其中可保留的一部分。",
                    f"在未来七天，为“{present['meaning']}”安排一个不超过二十分钟的行动。",
                    f"行动后回看：它是否让“{future['meaning']}”变得更清晰，而不是更急迫？",
                ],
                "reflection_prompts": [
                    f"当你读到{past['name']}时，哪个旧模式最值得被诚实命名？",
                    f"{present['name']}要求你把注意力从哪里收回来？",
                    f"若未来不是保证，{future['name']}为你保留了什么选择空间？",
                ],
                "knowledge_basis": [
                    {
                        "card_id": str(raw["card_id"]),
                        "knowledge_id": f"arcana:{raw['card_id']}:{raw['orientation']}:{locale}:local-v1",
                        "source_id": str(raw["provenance"]["source_id"]),
                        "source_title": str(raw["provenance"]["source_title"]),
                        "retrieval_mode": "repository_local_only",
                    }
                    for raw in cards
                    if isinstance(raw, Mapping)
                ],
                "uncertainty": (
                    f"本地确定性 Fixture 解读（{digest[:8]}）只用于个人反思。它不构成决定论预测，"
                    "也不替代医疗、法律或财务专业建议。"
                ),
            }
        else:
            document = {
                "schema_version": "tarot-reading.v2",
                "generation_locale": locale,
                "question_restatement": (
                    f"You are using this reading to look more clearly at “{payload.get('question')}”. "
                    "The saved cards are lenses for a practical, revisable reflection."
                ),
                "summary": (
                    f"{past['name']} sets the earlier context of {past['meaning']}; "
                    f"{present['name']} brings {present['meaning']} into present focus; "
                    f"{future['name']} opens {future['meaning']} as an adjustable direction."
                ),
                "positions": positions,
                "synthesis": (
                    f"The spread does not ask you to discard the experience named by {past['name']}. "
                    f"It asks you to bring it into the live work of {present['name']}. If you can tell "
                    f"which part of {past['meaning']} is still useful and which part has become habit, "
                    f"the direction named by {future['name']} can become a choice rather than a waiting room."
                ),
                "relationship_analysis": [
                    {
                        "kind": "relationship",
                        "headline": "How the past enters the present",
                        "content": f"{past['name']} and {present['name']} form a thread: the prior {past['meaning']} is shaping how you meet the present {present['meaning']}.",
                    },
                    {
                        "kind": "trend",
                        "headline": "A tendency, not a promise",
                        "content": f"The movement from {present['name']} to {future['name']} suggests a possible development toward {future['meaning']} if the present choice continues.",
                    },
                    {
                        "kind": "tension",
                        "headline": "The tension to name",
                        "content": f"Where {past['orientation']} {past['meaning']} meets {present['orientation']} {present['meaning']}, distinguish an actual need from an automatic reaction.",
                    },
                    {
                        "kind": "turning_point",
                        "headline": "The usable turning point",
                        "content": f"The turn is not something the future card does for you. It is the small observable choice that answers {present['name']} now.",
                    },
                ],
                "actionable_reflections": [
                    f"Name one concrete situation still shaped by {past['meaning']}, and identify one part worth keeping.",
                    f"Give {present['meaning']} one action of no more than twenty minutes in the next week.",
                    f"Afterward, ask whether it made {future['meaning']} clearer instead of more urgent.",
                ],
                "reflection_prompts": [
                    f"What old pattern becomes easier to name through {past['name']}?",
                    f"Where is {present['name']} asking you to bring your attention back?",
                    f"If the future is not guaranteed, what choice-space does {future['name']} preserve?",
                ],
                "knowledge_basis": [
                    {
                        "card_id": str(raw["card_id"]),
                        "knowledge_id": f"arcana:{raw['card_id']}:{raw['orientation']}:{locale}:local-v1",
                        "source_id": str(raw["provenance"]["source_id"]),
                        "source_title": str(raw["provenance"]["source_title"]),
                        "retrieval_mode": "repository_local_only",
                    }
                    for raw in cards
                    if isinstance(raw, Mapping)
                ],
                "uncertainty": (
                    f"This deterministic local Fixture interpretation ({digest[:8]}) supports personal reflection only. "
                    "It is not deterministic prediction or medical, legal, or financial advice."
                ),
            }
        return digest, TarotInterpretationDocument.model_validate(document)
