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

from creativedeploy_api.ai.retrieval import RetrievedContextUnit
from creativedeploy_api.arcana.question_analysis import QuestionAnalysis, QuestionDomain

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

_DOMAIN_CONTEXTS: Final[dict[QuestionDomain, dict[Locale, str]]] = {
    "love_relationship": {
        "en-US": (
            "For a relationship question, use this card to examine openness, reciprocity, "
            "boundaries, barriers, and practical stability. It cannot guarantee that a partner "
            "will appear."
        ),
        "zh-CN": (
            "面对关系问题，用这张牌检视开放度、互惠、边界、现实阻碍与稳定性；它不能保证某个伴侣"
            "一定出现。"
        ),
    },
    "career_work": {
        "en-US": (
            "For a work question, connect this card to agency, constraints, collaboration, and "
            "observable next steps rather than a promised promotion or job."
        ),
        "zh-CN": (
            "面对工作问题，把这张牌连接到能动性、限制、协作和可观察的下一步，而不是承诺职位或机会。"
        ),
    },
    "money_finance": {
        "en-US": (
            "For a finance question, treat this card as a lens on resources, risk, habits, and "
            "trade-offs, never as investment advice or a profit prediction."
        ),
        "zh-CN": "面对财务问题，用这张牌检视资源、风险、习惯与取舍；它不是投资建议或收益预测。",
    },
    "self_growth": {
        "en-US": (
            "For self-reflection, connect this card to a pattern the querent can name, test, and "
            "revise through a small action."
        ),
        "zh-CN": "面对自我成长，把这张牌连接到一个可以命名、检验并通过小行动调整的模式。",
    },
    "decision": {
        "en-US": (
            "For a decision, use this card to expose criteria, consequences, and reversible next "
            "steps rather than choosing on the querent's behalf."
        ),
        "zh-CN": "面对选择，用这张牌澄清判断标准、后果和可逆的下一步，而不是替提问者作决定。",
    },
    "family_social": {
        "en-US": (
            "For a family or social question, connect this card to roles, boundaries, mutual "
            "expectations, and communication patterns."
        ),
        "zh-CN": "面对家庭或社交问题，把这张牌连接到角色、边界、彼此期待和沟通模式。",
    },
    "general": {
        "en-US": (
            "Use this card as a reflective lens tied to the exact question and observable choices."
        ),
        "zh-CN": "把这张牌作为紧扣原问题与可观察选择的反思视角。",
    },
}

_CARD_QUESTION_LENSES: Final[dict[tuple[str, str, QuestionDomain], dict[Locale, str]]] = {
    ("minor-wands-nine", "reversed", "love_relationship"): {
        "en-US": (
            "Prior hurt or prolonged vigilance may have become defensive exhaustion, closing "
            "the door before a new connection can be evaluated on its own evidence."
        ),
        "zh-CN": "过去的受伤或长期戒备可能已变成防御性疲惫，让你在新关系尚未被现实检验前就先关闭。",
    },
    ("minor-swords-three", "upright", "love_relationship"): {
        "en-US": (
            "The present asks for an honest encounter with grief, disappointment, or a painful "
            "truth so a new relationship is not used to cover an unprocessed wound."
        ),
        "zh-CN": "当下需要诚实面对尚未消化的伤痛、失望或事实，避免把新关系当成遮盖旧伤的办法。",
    },
    ("minor-pentacles-ten", "upright", "love_relationship"): {
        "en-US": (
            "Long-term values, reciprocal support, and practical stability offer criteria for "
            "recognizing a connection that could grow beyond initial attraction."
        ),
        "zh-CN": "长期价值、彼此支持与现实稳定性，可以成为辨认一段关系能否超越短期吸引的标准。",
    },
    ("minor-cups-king", "upright", "love_relationship"): {
        "en-US": (
            "Emotional steadiness and responsible reciprocity may be an established strength or "
            "a standard carried forward from earlier relationships."
        ),
        "zh-CN": "情绪稳定与负责任的互惠，可能是过往已经形成的能力，也可能是你带入新关系的高标准。",
    },
    ("minor-pentacles-four", "reversed", "love_relationship"): {
        "en-US": (
            "The live issue is whether control is loosening into openness or insecurity is making "
            "stability feel scarce and therefore something to grip."
        ),
        "zh-CN": (
            "当下要辨认的是：控制正在松动为开放，还是不安全感让稳定显得稀缺，因而更想抓紧确定答案。"
        ),
    },
    ("major-20-judgement", "reversed", "love_relationship"): {
        "en-US": (
            "Self-judgment, avoidance, or reluctance to answer a clear inner call can delay "
            "recognition of a viable connection; this is a barrier signal, not a promise."
        ),
        "zh-CN": (
            "自我评判、回避或不愿回应已经看见的内在事实，可能延迟你识别可发展关系的能力；"
            "这是阻碍信号，不是承诺。"
        ),
    },
}

_DOMAIN_SUIT_LENSES: Final[dict[QuestionDomain, dict[str, dict[Locale, str]]]] = {
    "love_relationship": {
        "wands": {
            "zh-CN": "吸引力、主动性与关系推进的节奏",
            "en-US": "attraction, initiative, and the pace of a connection",
        },
        "cups": {
            "zh-CN": "情感开放、彼此感受与接纳能力",
            "en-US": "emotional openness, mutual feeling, and receptivity",
        },
        "swords": {
            "zh-CN": "诚实沟通、事实判断与关系边界",
            "en-US": "honest communication, discernment, and relationship boundaries",
        },
        "pentacles": {
            "zh-CN": "现实投入、互惠支持与长期稳定性",
            "en-US": "practical investment, reciprocity, and long-term stability",
        },
    },
    "career_work": {
        "wands": {"zh-CN": "行动动力与推进节奏", "en-US": "initiative and pace"},
        "cups": {
            "zh-CN": "协作感受与团队连接",
            "en-US": "collaboration and team connection",
        },
        "swords": {
            "zh-CN": "判断、沟通与决策边界",
            "en-US": "judgment, communication, and decisions",
        },
        "pentacles": {
            "zh-CN": "资源、技能与可持续执行",
            "en-US": "resources, skill, and sustainable execution",
        },
    },
    "money_finance": {
        "wands": {
            "zh-CN": "行动冲动与风险节奏",
            "en-US": "impulse, action, and risk pace",
        },
        "cups": {
            "zh-CN": "情绪需求与消费动机",
            "en-US": "emotional needs and spending motives",
        },
        "swords": {
            "zh-CN": "信息判断与风险边界",
            "en-US": "information, judgment, and risk boundaries",
        },
        "pentacles": {
            "zh-CN": "资源配置与现实承受力",
            "en-US": "resource allocation and practical capacity",
        },
    },
}

_RELATIONSHIP_RANK_LENSES: Final[dict[str, dict[Locale, str]]] = {
    "ace": {
        "zh-CN": "观察新的开始是否有现实回应",
        "en-US": "test whether a new beginning receives a real response",
    },
    "two": {
        "zh-CN": "检视配对、选择与双方参与",
        "en-US": "examine pairing, choice, and participation by both sides",
    },
    "three": {
        "zh-CN": "辨认共同发展或需要正视的第三项因素",
        "en-US": "identify shared growth or a third factor that must be faced",
    },
    "four": {
        "zh-CN": "区分稳定边界与封闭控制",
        "en-US": "distinguish stable boundaries from closed control",
    },
    "five": {
        "zh-CN": "让冲突显出真正的优先级",
        "en-US": "let friction reveal the real priority",
    },
    "six": {
        "zh-CN": "核对给予与接受是否平衡",
        "en-US": "check whether giving and receiving are balanced",
    },
    "seven": {
        "zh-CN": "在压力下检验标准与耐心",
        "en-US": "test standards and patience under pressure",
    },
    "eight": {
        "zh-CN": "看持续行动能否带来真实变化",
        "en-US": "see whether sustained action creates real change",
    },
    "nine": {
        "zh-CN": "辨认接近完成时的成熟与防御",
        "en-US": "distinguish maturity from defensiveness near completion",
    },
    "ten": {
        "zh-CN": "评估这段关系能否承载长期后果",
        "en-US": "assess whether the connection can carry long-term consequences",
    },
    "page": {
        "zh-CN": "把初次讯息当作线索而非承诺",
        "en-US": "treat an initial message as evidence, not a promise",
    },
    "knight": {
        "zh-CN": "主动追求可能带来速度，也要核验持续性",
        "en-US": "active pursuit can create speed, but consistency still needs evidence",
    },
    "queen": {
        "zh-CN": "以成熟的内在判断照料自己与边界",
        "en-US": "use mature inner judgment to care for self and boundaries",
    },
    "king": {
        "zh-CN": "以稳定、负责的方式表达关系立场",
        "en-US": "express a relationship stance with steadiness and responsibility",
    },
}


def _fallback_question_context(
    *,
    card_name: str,
    orientation: str,
    position_key: str,
    meaning: str,
    suit: str | None,
    rank: str,
    theme: str,
    locale: Locale,
    analysis: QuestionAnalysis,
) -> str:
    suit_lens = _DOMAIN_SUIT_LENSES.get(analysis.domain, {}).get(suit or "", {}).get(locale)
    if suit_lens is None:
        suit_lens = theme.replace(":", " ").replace("-", " ") if locale == "en-US" else meaning
    rank_lens = (
        _RELATIONSHIP_RANK_LENSES.get(rank, {}).get(locale)
        if analysis.domain == "love_relationship"
        else None
    )
    if rank_lens is None:
        rank_lens = (
            "translate the stated quality into one observable choice"
            if locale == "en-US"
            else "把这项牌面特质转成一个可观察的选择"
        )
    if locale == "zh-CN":
        position_lead = {
            "past": "回看过去",
            "present": "面对当下",
            "future": "观察未来的条件性方向",
        }[position_key]
        orientation_note = (
            "正位表示这项能力可以被主动使用。"
            if orientation == "upright"
            else "逆位提醒这项能力可能受阻、过度或被回避，需要先重新校准。"
        )
        return f"{position_lead}，{card_name}把焦点放在{suit_lens}；{rank_lens}。{orientation_note}"
    position_lead = {
        "past": "Looking at the past",
        "present": "In the present",
        "future": "As a conditional future direction",
    }[position_key]
    orientation_note = (
        "Upright, this capacity is available for conscious use."
        if orientation == "upright"
        else "Reversed, it may be blocked, excessive, or avoided and needs recalibration first."
    )
    return f"{position_lead}, {card_name} focuses on {suit_lens}; {rank_lens}. {orientation_note}"


_PROVENANCE: Final[dict[str, object]] = {
    "source_id": "waite-pictorial-key-1910-derived-v2",
    "source_title": (
        "A. E. Waite, The Pictorial Key to the Tarot (1910); CreativeDeploy derived summaries"
    ),
    "source_type": "public-domain source-informed CreativeDeploy concise derived summary",
    "usage": (
        "source-informed compact summary only; no long-form text, modern interpretation, or "
        "commercial artwork is reproduced"
    ),
    "retrieval_mode": "repository_local_only",
}

_DERIVED_PROVENANCE: Final[dict[str, object]] = {
    "source_id": "creativedeploy-arcana-question-position-heuristics-v2",
    "source_title": "CreativeDeploy Arcana question and position heuristics v2",
    "source_type": "CreativeDeploy-authored derived interpretive heuristic",
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
    archetype: str
    shadow_tension: str
    symbols_themes: tuple[str, ...]
    element: str | None
    rank_number: str
    court_archetype: str | None
    position_context: str
    question_context: str
    question_analysis: QuestionAnalysis
    provenance: dict[str, object]

    def as_retrieved_units(self, *, locale: Locale) -> tuple[RetrievedContextUnit, ...]:
        source_id = str(self.provenance["source_id"])
        primary = RetrievedContextUnit(
            source_id=source_id,
            source_title=str(self.provenance["source_title"]),
            source_type=str(self.provenance["source_type"]),
            repository_reference=(
                "repo://apps/api/migrations/versions/"
                f"4c01a2b3c4d5_add_arcana_core_proof_slice.py#card/{self.card_id}"
            ),
            chunk_id=f"arcana:{self.card_id}:core:{self.orientation}:{locale}:v2",
            section=f"card/{self.orientation}/core",
            content=(
                f"{self.card_name}: {self.meaning}. Archetype: {self.archetype}. "
                f"Shadow/tension: {self.shadow_tension}. Themes: {'; '.join(self.symbols_themes)}."
            ),
            retrieval_rationale="Exact drawn card identity and orientation match.",
            retrieval_score_ppm=1_000_000,
            locale=locale,
            corpus_id="arcana-question-aware-local-knowledge",
            corpus_version=str(self.provenance["knowledge_version"]),
        )
        position = RetrievedContextUnit(
            source_id=str(_DERIVED_PROVENANCE["source_id"]),
            source_title=str(_DERIVED_PROVENANCE["source_title"]),
            source_type=str(_DERIVED_PROVENANCE["source_type"]),
            repository_reference=(
                "repo://apps/api/src/creativedeploy_api/arcana/knowledge.py"
                f"#position/{self.position_key}"
            ),
            chunk_id=(
                f"arcana:{self.card_id}:position:{self.position_key}:{self.orientation}:{locale}:v2"
            ),
            section=f"position/{self.position_key}",
            content=(
                f"{self.card_name} in {self.position_key}: {self.position_context} "
                f"Orientation lens: {_ORIENTATION_FACETS[self.orientation][locale]}."
            ),
            retrieval_rationale="Exact card, orientation, and spread position match.",
            retrieval_score_ppm=990_000,
            locale=locale,
            corpus_id="arcana-question-aware-local-knowledge",
            corpus_version=str(self.provenance["knowledge_version"]),
        )
        analysis = self.question_analysis
        question = RetrievedContextUnit(
            source_id=str(_DERIVED_PROVENANCE["source_id"]),
            source_title=str(_DERIVED_PROVENANCE["source_title"]),
            source_type=str(_DERIVED_PROVENANCE["source_type"]),
            repository_reference=(
                "repo://apps/api/src/creativedeploy_api/arcana/knowledge.py"
                f"#question/{analysis.domain}"
            ),
            chunk_id=(
                f"arcana:{self.card_id}:question:{analysis.domain}:{self.position_key}:{locale}:v2"
            ),
            section=f"question/{analysis.domain}",
            content=(
                f"{self.card_name} for domain {analysis.domain}, intents "
                f"{', '.join(analysis.intents)}, temporal frame {analysis.temporal_frame}: "
                f"{self.question_context}"
            ),
            retrieval_rationale=(
                "Exact card plus deterministic question domain, intent, temporal frame, and "
                "spread position match."
            ),
            retrieval_score_ppm=980_000,
            locale=locale,
            corpus_id="arcana-question-aware-local-knowledge",
            corpus_version=str(self.provenance["knowledge_version"]),
        )
        return primary, position, question

    def primary_knowledge_id(self, *, locale: Locale) -> str:
        return f"arcana:{self.card_id}:core:{self.orientation}:{locale}:v2"

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
            "archetype": self.archetype,
            "shadow_tension": self.shadow_tension,
            "symbols_themes": list(self.symbols_themes),
            "element": self.element,
            "rank_number": self.rank_number,
            "court_archetype": self.court_archetype,
            "position_context": self.position_context,
            "question_context": self.question_context,
            "question_analysis": self.question_analysis.as_payload(),
            "provenance": self.provenance,
        }


class LocalTarotKnowledgeLayer:
    """Provider-neutral context builder whose only implementation is local data."""

    knowledge_version = "arcana-local-knowledge-v2"

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
        question_analysis: QuestionAnalysis,
    ) -> TarotKnowledgeContext:
        facets = [
            _POSITION_FACETS[position_key][locale],
            _ORIENTATION_FACETS[orientation][locale],
        ]
        element: str | None = None
        court_archetype: str | None = None
        if suit is not None:
            suit_facet = _SUIT_FACETS[suit][locale]
            element = suit_facet["element"]
            facets.append(f"{suit_facet['element']}: {suit_facet['theme']}")
            rank_facet = _NUMBER_FACETS.get(rank, _COURT_FACETS.get(rank))
            if rank_facet is not None:
                facets.append(rank_facet[locale])
            if rank in _COURT_FACETS:
                court_archetype = _COURT_FACETS[rank][locale]
        else:
            facets.append(theme.replace("-", " "))
        position_context = _POSITION_FACETS[position_key][locale]
        question_context = _CARD_QUESTION_LENSES.get(
            (card_id, orientation, question_analysis.domain), {}
        ).get(locale)
        if question_context is None:
            question_context = _fallback_question_context(
                card_name=card_name,
                orientation=orientation,
                position_key=position_key,
                meaning=meaning,
                suit=suit,
                rank=rank,
                theme=theme,
                locale=locale,
                analysis=question_analysis,
            )
        archetype = theme.replace(":", " ").replace("-", " ")
        shadow_tension = (
            "the expressed quality can become blocked, excessive, or avoidant"
            if locale == "en-US"
            else "这股力量可能受阻、过度或转为回避"
        )
        symbols_themes = tuple(
            dict.fromkeys(
                item
                for item in (
                    theme.replace(":", " ").replace("-", " "),
                    suit or arcana,
                    rank,
                )
                if item
            )
        )
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
            archetype=archetype,
            shadow_tension=shadow_tension,
            symbols_themes=symbols_themes,
            element=element,
            rank_number=rank,
            court_archetype=court_archetype,
            position_context=position_context,
            question_context=question_context,
            question_analysis=question_analysis,
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
