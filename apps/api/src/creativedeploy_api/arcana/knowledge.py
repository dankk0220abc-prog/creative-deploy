# ruff: noqa: RUF001

"""Local, auditable Tarot knowledge context for the Arcana Fixture adapter.

This is a retrieval foundation, not a remote inference integration.  It joins
the installed 78-card reference deck with compact semantic facets at dispatch
time and returns a small, serialisable context.  It deliberately has no
network, credential, or provider dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

Locale = Literal["zh-CN", "en-US"]

_SUIT_FACETS: Final[dict[str, dict[Locale, dict[str, str]]]] = {
    "wands": {
        "en-US": {"element": "fire", "theme": "initiative, desire, and momentum"},
        "zh-CN": {"element": "火", "theme": "行动意愿、热情与推进"},
    },
    "cups": {
        "en-US": {"element": "water", "theme": "feeling, relationship, and receptivity"},
        "zh-CN": {"element": "水", "theme": "感受、关系与接纳"},
    },
    "swords": {
        "en-US": {"element": "air", "theme": "thought, truth, and decision"},
        "zh-CN": {"element": "风", "theme": "思考、真相与决断"},
    },
    "pentacles": {
        "en-US": {"element": "earth", "theme": "resources, craft, and practical reality"},
        "zh-CN": {"element": "土", "theme": "资源、技艺与现实基础"},
    },
}

_NUMBER_FACETS: Final[dict[str, dict[Locale, str]]] = {
    "ace": {"en-US": "a concentrated beginning", "zh-CN": "能量集中的开端"},
    "two": {"en-US": "choice and pairing", "zh-CN": "选择与配对"},
    "three": {"en-US": "growth through participation", "zh-CN": "在参与中发展"},
    "four": {"en-US": "stability and containment", "zh-CN": "稳定与边界"},
    "five": {"en-US": "friction that reveals priorities", "zh-CN": "揭示优先级的摩擦"},
    "six": {"en-US": "adjustment and exchange", "zh-CN": "调整与交换"},
    "seven": {"en-US": "assessment under pressure", "zh-CN": "压力下的评估"},
    "eight": {"en-US": "movement through practice", "zh-CN": "通过练习推进"},
    "nine": {"en-US": "maturity near completion", "zh-CN": "接近完成的成熟"},
    "ten": {"en-US": "culmination and consequence", "zh-CN": "汇聚与后果"},
}

_COURT_FACETS: Final[dict[str, dict[Locale, str]]] = {
    "page": {"en-US": "curiosity and a first message", "zh-CN": "好奇与初次讯息"},
    "knight": {"en-US": "committed pursuit", "zh-CN": "投入的追寻"},
    "queen": {"en-US": "inward mastery and stewardship", "zh-CN": "内在掌握与照料"},
    "king": {"en-US": "outward responsibility and authority", "zh-CN": "外在责任与担当"},
}

_POSITION_FACETS: Final[dict[str, dict[Locale, str]]] = {
    "past": {
        "en-US": "a prior pattern, condition, or influence that still informs the question",
        "zh-CN": "仍在影响这个问题的既有模式、条件或经验",
    },
    "present": {
        "en-US": "the live choice, attention, or tension available to the querent now",
        "zh-CN": "当下可以看见、回应或调整的选择、注意力与张力",
    },
    "future": {
        "en-US": "a conditional direction that may develop from the present, not a fixed outcome",
        "zh-CN": "由当下延伸出的条件性方向，不是既定结果",
    },
}

_ORIENTATION_FACETS: Final[dict[str, dict[Locale, str]]] = {
    "upright": {
        "en-US": "the quality is available to be used with awareness",
        "zh-CN": "这股力量可以被有意识地调用",
    },
    "reversed": {
        "en-US": "the quality may be inward, obstructed, overextended, or asking for recalibration",
        "zh-CN": "这股力量可能向内、受阻、过度延伸，或需要重新校准",
    },
}

_PROVENANCE: Final[dict[str, object]] = {
    "source_id": "waite-pictorial-key-1910-plus-original-synthesis-v1",
    "source_title": (
        "A. E. Waite, The Pictorial Key to the Tarot (1910); CreativeDeploy concise synthesis"
    ),
    "source_type": "public-domain bibliographic reference plus original paraphrase",
    "usage": "compact semantic reference only; no long-form source text or artwork is reproduced",
    "retrieval_mode": "repository_local_only",
}


@dataclass(frozen=True, slots=True)
class TarotKnowledgeContext:
    """A deliberately small context record passed to the local interpreter."""

    card_id: str
    card_name: str
    orientation: str
    position_key: str
    meaning: str
    arcana: str
    suit: str | None
    rank: str
    theme: str
    semantic_facets: tuple[str, ...]
    provenance: dict[str, object]

    def as_payload(self) -> dict[str, object]:
        return {
            "card_id": self.card_id,
            "name": self.card_name,
            "orientation": self.orientation,
            "position_key": self.position_key,
            "meaning": self.meaning,
            "arcana": self.arcana,
            "suit": self.suit,
            "rank": self.rank,
            "theme": self.theme,
            "semantic_facets": list(self.semantic_facets),
            "provenance": self.provenance,
        }


class LocalTarotKnowledgeLayer:
    """Provider-neutral context builder whose only implementation is local data."""

    knowledge_version = "arcana-local-knowledge-v1"

    def context_for(
        self,
        *,
        card_id: str,
        card_name: str,
        orientation: str,
        position_key: str,
        meaning: str,
        arcana: str,
        suit: str | None,
        rank: str,
        theme: str,
        locale: Locale,
    ) -> TarotKnowledgeContext:
        facets = [
            _POSITION_FACETS[position_key][locale],
            _ORIENTATION_FACETS[orientation][locale],
        ]
        if suit is not None:
            suit_facet = _SUIT_FACETS[suit][locale]
            facets.append(f"{suit_facet['element']}: {suit_facet['theme']}")
            rank_facet = _NUMBER_FACETS.get(rank, _COURT_FACETS.get(rank))
            if rank_facet is not None:
                facets.append(rank_facet[locale])
        else:
            facets.append(theme.replace("-", " "))
        return TarotKnowledgeContext(
            card_id=card_id,
            card_name=card_name,
            orientation=orientation,
            position_key=position_key,
            meaning=meaning,
            arcana=arcana,
            suit=suit,
            rank=rank,
            theme=theme,
            semantic_facets=tuple(facets),
            provenance={
                **_PROVENANCE,
                "card_locator": card_id,
                "knowledge_version": self.knowledge_version,
            },
        )

    @staticmethod
    def safety_note(locale: Locale) -> str:
        if locale == "zh-CN":
            return "本地知识层用于反思，不提供决定论预测，也不替代医疗、法律或财务专业意见。"
        return (
            "This local knowledge layer supports reflection, not deterministic prediction "
            "or medical, legal, or financial advice."
        )
