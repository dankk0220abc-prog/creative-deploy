"""Deterministic, non-predictive relationship signals for a three-card spread."""

# ruff: noqa: RUF001

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from creativedeploy_api.ai.retrieval import RetrievedContextUnit
from creativedeploy_api.arcana.question_analysis import QuestionAnalysis

Locale = Literal["zh-CN", "en-US"]
SignalKind = Literal["reinforcement", "tension", "transition", "turning_point", "pattern"]

_ELEMENTS: Final[dict[str, str]] = {
    "wands": "fire",
    "cups": "water",
    "swords": "air",
    "pentacles": "earth",
}
_CONFLICTING_ELEMENTS: Final[frozenset[frozenset[str]]] = frozenset(
    {frozenset({"fire", "water"}), frozenset({"air", "earth"})}
)
_NUMBER_VALUES: Final[dict[str, int]] = {
    "ace": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_COURTS: Final[frozenset[str]] = frozenset({"page", "knight", "queen", "king"})
_DOMAIN_LABELS: Final[dict[str, dict[Locale, str]]] = {
    "love_relationship": {"zh-CN": "感情与关系", "en-US": "love and relationship"},
    "career_work": {"zh-CN": "事业与工作", "en-US": "career and work"},
    "money_finance": {"zh-CN": "金钱与财务", "en-US": "money and finance"},
    "self_growth": {"zh-CN": "自我成长", "en-US": "self-growth"},
    "decision": {"zh-CN": "选择与决策", "en-US": "decision-making"},
    "family_social": {"zh-CN": "家庭与社交", "en-US": "family and social relationships"},
    "general": {"zh-CN": "综合反思", "en-US": "general reflection"},
}
_SUIT_LABELS: Final[dict[str, dict[Locale, str]]] = {
    "wands": {"zh-CN": "权杖", "en-US": "Wands"},
    "cups": {"zh-CN": "圣杯", "en-US": "Cups"},
    "swords": {"zh-CN": "宝剑", "en-US": "Swords"},
    "pentacles": {"zh-CN": "星币", "en-US": "Pentacles"},
}
_ELEMENT_LABELS: Final[dict[str, dict[Locale, str]]] = {
    "fire": {"zh-CN": "火元素", "en-US": "fire"},
    "water": {"zh-CN": "水元素", "en-US": "water"},
    "air": {"zh-CN": "风元素", "en-US": "air"},
    "earth": {"zh-CN": "土元素", "en-US": "earth"},
}
_ORIENTATION_LABELS: Final[dict[str, dict[Locale, str]]] = {
    "upright": {"zh-CN": "正位", "en-US": "upright"},
    "reversed": {"zh-CN": "逆位", "en-US": "reversed"},
}


@dataclass(frozen=True, slots=True)
class RelationshipCard:
    card_id: str
    card_name: str
    position_key: str
    orientation: str
    arcana: str
    suit: str | None
    rank: str
    meaning: str


@dataclass(frozen=True, slots=True)
class RelationshipSignal:
    signal_id: str
    kind: SignalKind
    card_ids: tuple[str, ...]
    headline: str
    content: str
    heuristic: str

    def as_payload(self) -> dict[str, object]:
        return {
            "signal_id": self.signal_id,
            "kind": self.kind,
            "card_ids": list(self.card_ids),
            "headline": self.headline,
            "content": self.content,
            "heuristic": self.heuristic,
            "provenance": {
                "source_id": "creativedeploy-arcana-relationship-heuristics-v2",
                "source_type": "CreativeDeploy-authored derived interpretive heuristic",
                "retrieval_mode": "repository_local_only",
            },
        }

    def as_retrieved_unit(self, *, locale: Locale) -> RetrievedContextUnit:
        return RetrievedContextUnit(
            source_id="creativedeploy-arcana-relationship-heuristics-v2",
            source_title="CreativeDeploy Arcana relationship heuristics v2",
            source_type="CreativeDeploy-authored derived interpretive heuristic",
            repository_reference=(
                "repo://apps/api/src/creativedeploy_api/arcana/relationships.py"
                f"#signal/{self.signal_id}"
            ),
            chunk_id=f"arcana:relationship:{self.signal_id}:{locale}:v2",
            section=f"relationship/{self.kind}",
            content=self.content,
            retrieval_rationale=(
                "Deterministic relationship signal derived from the exact saved three-card draw."
            ),
            retrieval_score_ppm=970_000,
            locale=locale,
            corpus_id="arcana-question-aware-local-knowledge",
            corpus_version="arcana-local-knowledge-v2",
        )


def _signal(
    *,
    key: str,
    kind: SignalKind,
    cards: tuple[RelationshipCard, ...],
    headline_en: str,
    headline_zh: str,
    content_en: str,
    content_zh: str,
    heuristic: str,
    locale: Locale,
) -> RelationshipSignal:
    return RelationshipSignal(
        signal_id=key,
        kind=kind,
        card_ids=tuple(card.card_id for card in cards),
        headline=headline_zh if locale == "zh-CN" else headline_en,
        content=content_zh if locale == "zh-CN" else content_en,
        heuristic=heuristic,
    )


def assemble_relationship_signals(
    cards: tuple[RelationshipCard, RelationshipCard, RelationshipCard],
    analysis: QuestionAnalysis,
) -> tuple[RelationshipSignal, ...]:
    """Return a bounded set of signals; none of them is a deterministic prediction."""

    locale = analysis.locale
    past, present, future = cards
    signals: list[RelationshipSignal] = []
    domain_label = _DOMAIN_LABELS[analysis.domain][locale]
    signals.append(
        _signal(
            key="past-to-present-continuity",
            kind="transition",
            cards=(past, present),
            headline_en="How the past conditions the present",
            headline_zh="过去如何塑造现在",
            content_en=(
                f"In this {domain_label} question, {past.card_name} describes a prior pattern "
                f"that conditions how {present.card_name} is being met now; read the pair as "
                "cause and current response, not two separate definitions."
            ),
            content_zh=(
                f"在这个{domain_label}问题里，{past.card_name}描述的既有模式正在影响你如何"
                f"面对{present.card_name}；应把两张牌读成原因与当前反应，而不是两个孤立释义。"
            ),
            heuristic="past_present_causal_continuity",
            locale=locale,
        )
    )
    signals.append(
        _signal(
            key="present-to-future-direction",
            kind="transition",
            cards=(present, future),
            headline_en="The direction created by the present",
            headline_zh="当下正在形成的方向",
            content_en=(
                f"{present.card_name} is the active condition and {future.card_name} is a "
                "conditional direction if that condition is handled consciously; the future "
                "card is a tendency, never a guarantee."
            ),
            content_zh=(
                f"{present.card_name}是当前有效条件，{future.card_name}是在有意识处理这一条件后"
                "可能形成的方向；未来牌只表达趋势，不构成保证。"
            ),
            heuristic="present_future_directional_change",
            locale=locale,
        )
    )

    suits = [card.suit for card in cards if card.suit is not None]
    if len(suits) >= 2 and len(set(suits)) < len(suits):
        repeated = next(suit for suit in suits if suits.count(suit) > 1)
        repeated_label = _SUIT_LABELS[repeated][locale]
        repeated_cards = tuple(card for card in cards if card.suit == repeated)
        signals.append(
            _signal(
                key=f"repeated-suit-{repeated}",
                kind="reinforcement",
                cards=repeated_cards,
                headline_en="Repeated suit emphasis",
                headline_zh="重复花色形成强化",
                content_en=(
                    f"Repeated {repeated_label} energy reinforces one mode of responding across "
                    "the "
                    "spread; it is emphasis to examine, not proof of an outcome."
                ),
                content_zh=(
                    f"重复出现的{repeated_label}能量强化了牌阵中的同一种回应方式；这是需要检视的重点，"
                    "不是结果证据。"
                ),
                heuristic="suit_repetition",
                locale=locale,
            )
        )

    for left, right in ((past, present), (present, future)):
        left_element = _ELEMENTS.get(left.suit or "")
        right_element = _ELEMENTS.get(right.suit or "")
        if left_element is not None and left_element == right_element:
            element_label = _ELEMENT_LABELS[left_element][locale]
            signals.append(
                _signal(
                    key=f"element-reinforcement-{left.position_key}-{right.position_key}",
                    kind="reinforcement",
                    cards=(left, right),
                    headline_en="Elemental reinforcement",
                    headline_zh="元素能量彼此强化",
                    content_en=(
                        f"{left.card_name} and {right.card_name} repeat {element_label} energy, "
                        "strengthening a shared mode while also risking overreliance on it."
                    ),
                    content_zh=(
                        f"{left.card_name}与{right.card_name}重复{element_label}，强化共同模式，"
                        "也提醒不要只依赖这一种回应。"
                    ),
                    heuristic="element_repetition",
                    locale=locale,
                )
            )
        elif (
            left_element is not None
            and right_element is not None
            and frozenset({left_element, right_element}) in _CONFLICTING_ELEMENTS
        ):
            left_element_label = _ELEMENT_LABELS[left_element][locale]
            right_element_label = _ELEMENT_LABELS[right_element][locale]
            signals.append(
                _signal(
                    key=f"element-tension-{left.position_key}-{right.position_key}",
                    kind="tension",
                    cards=(left, right),
                    headline_en="Conflicting modes of response",
                    headline_zh="回应方式之间的张力",
                    content_en=(
                        f"The shift from {left_element_label} in {left.card_name} to "
                        f"{right_element_label} in "
                        f"{right.card_name} marks tension between different ways of responding."
                    ),
                    content_zh=(
                        f"{left.card_name}的{left_element_label}与{right.card_name}的"
                        f"{right_element_label}形成张力，"
                        "提示两种回应方式需要协调。"
                    ),
                    heuristic="element_conflict",
                    locale=locale,
                )
            )

    orientations = tuple(card.orientation for card in cards)
    if orientations[0] == "reversed" and orientations[1:] == ("upright", "upright"):
        signals.append(
            _signal(
                key="orientation-recalibration-turn",
                kind="turning_point",
                cards=cards,
                headline_en="Recalibration becomes forward movement",
                headline_zh="从重新校准转向向前推进",
                content_en=(
                    "A reversed past followed by two upright cards marks a turning point: an old "
                    "blocked or overextended pattern can be named before the present and future "
                    "qualities become usable."
                ),
                content_zh=(
                    "逆位的过去之后连续出现两张正位牌，构成转折信号：先命名旧有的受阻或过度模式，"
                    "当下与未来的力量才更可能被实际使用。"
                ),
                heuristic="upright_reversed_sequence",
                locale=locale,
            )
        )
    elif len(set(orientations)) == 1:
        orientation_label = _ORIENTATION_LABELS[orientations[0]][locale]
        signals.append(
            _signal(
                key=f"orientation-sequence-{orientations[0]}",
                kind="reinforcement",
                cards=cards,
                headline_en="Consistent orientation sequence",
                headline_zh="一致的正逆位序列",
                content_en=(
                    f"All three cards are {orientation_label}, reinforcing a consistent mode "
                    "across "
                    "the timeline without making the outcome certain."
                ),
                content_zh=(
                    f"三张牌均为{orientation_label}，强化了时间线上的一致模式，但不使结果成为定论。"
                ),
                heuristic="upright_reversed_sequence",
                locale=locale,
            )
        )

    numeric = [_NUMBER_VALUES.get(card.rank) for card in cards]
    if all(value is not None for value in numeric):
        values = [int(value) for value in numeric if value is not None]
        if values[0] < values[1] < values[2] or values[0] > values[1] > values[2]:
            direction = "progression" if values[0] < values[1] else "regression"
            direction_label = (
                "递增"
                if locale == "zh-CN" and direction == "progression"
                else "递减"
                if locale == "zh-CN"
                else direction
            )
            signals.append(
                _signal(
                    key=f"numeric-{direction}",
                    kind="pattern",
                    cards=cards,
                    headline_en="Numerical sequence",
                    headline_zh="数字序列",
                    content_en=(
                        f"The ranks form a {direction_label}; use it as a structural change "
                        "signal, not "
                        "a calendar or certainty claim."
                    ),
                    content_zh=(
                        f"牌面数字形成{direction_label}序列；它只用于描述结构变化，不能推导日期或确定结果。"
                    ),
                    heuristic="numerical_progression_regression",
                    locale=locale,
                )
            )

    court_cards = tuple(card for card in cards if card.rank in _COURTS)
    if len(court_cards) >= 2:
        signals.append(
            _signal(
                key="court-emphasis",
                kind="pattern",
                cards=court_cards,
                headline_en="Court-card emphasis",
                headline_zh="宫廷牌形成重点",
                content_en=(
                    "Multiple court cards emphasize roles, maturity, or interpersonal stance; "
                    "they do not identify a particular person."
                ),
                content_zh="多张宫廷牌强调角色、成熟度或互动姿态，但不能据此认定某个具体人物。",
                heuristic="court_emphasis",
                locale=locale,
            )
        )

    major_count = sum(card.arcana == "major" for card in cards)
    signals.append(
        _signal(
            key=f"major-minor-balance-{major_count}",
            kind="pattern",
            cards=cards,
            headline_en="Major and Minor Arcana balance",
            headline_zh="大牌与小牌的比例",
            content_en=(
                "The spread leans toward broad archetypal change."
                if major_count >= 2
                else (
                    "The spread leans toward practical conditions and choices rather than a "
                    "fixed fate."
                )
            ),
            content_zh=(
                "牌阵更偏向整体性的原型变化。"
                if major_count >= 2
                else "牌阵更偏向现实条件和可调整的选择，而不是既定命运。"
            ),
            heuristic="major_minor_balance",
            locale=locale,
        )
    )

    priority = {"turning_point": 0, "transition": 1, "tension": 2, "reinforcement": 3, "pattern": 4}
    return tuple(sorted(signals, key=lambda item: (priority[item.kind], item.signal_id))[:6])
