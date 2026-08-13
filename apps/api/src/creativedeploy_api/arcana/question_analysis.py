"""Small deterministic bilingual question analysis for Arcana retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

Locale = Literal["zh-CN", "en-US"]
QuestionDomain = Literal[
    "love_relationship",
    "career_work",
    "money_finance",
    "self_growth",
    "decision",
    "family_social",
    "general",
]
QuestionIntent = Literal[
    "outcome_tendency",
    "advice",
    "obstacle",
    "relationship_dynamic",
    "decision_comparison",
    "timing",
    "self_reflection",
]
TemporalFrame = Literal["past", "present", "near_future", "explicit_period", "unspecified"]

_DOMAIN_TERMS: Final[dict[QuestionDomain, dict[Locale, tuple[str, ...]]]] = {
    "love_relationship": {
        "zh-CN": ("正缘", "恋爱", "爱情", "感情", "伴侣", "对象", "婚姻", "复合", "约会", "关系"),
        "en-US": (
            "love",
            "romance",
            "relationship",
            "partner",
            "dating",
            "marriage",
            "soulmate",
            "breakup",
        ),
    },
    "career_work": {
        "zh-CN": ("工作", "职业", "事业", "求职", "升职", "同事", "业务", "项目"),
        "en-US": ("career", "work", "job", "profession", "promotion", "colleague", "business"),
    },
    "money_finance": {
        "zh-CN": ("金钱", "财务", "收入", "投资", "债务", "财富", "预算", "经济"),
        "en-US": ("money", "finance", "financial", "income", "investment", "debt", "wealth"),
    },
    "self_growth": {
        "zh-CN": ("成长", "自我", "内心", "人生方向", "目标", "疗愈", "反思"),
        "en-US": ("self", "growth", "purpose", "inner", "healing", "reflection", "personal goal"),
    },
    "decision": {
        "zh-CN": ("决定", "选择", "比较", "选哪个", "要不要"),
        "en-US": ("decision", "choose", "choice", "compare", "which option"),
    },
    "family_social": {
        "zh-CN": ("家庭", "家人", "父母", "孩子", "朋友", "友情", "社交"),
        "en-US": ("family", "parent", "child", "friend", "friendship", "social"),
    },
    "general": {"zh-CN": (), "en-US": ()},
}

_INTENT_TERMS: Final[dict[QuestionIntent, dict[Locale, tuple[str, ...]]]] = {
    "outcome_tendency": {
        "zh-CN": ("会不会", "会有", "能否", "结果", "可能吗", "是否会"),
        "en-US": ("will i", "will there", "outcome", "likely", "can i", "is it possible"),
    },
    "advice": {
        "zh-CN": ("怎么办", "怎么做", "应该", "建议", "如何改善"),
        "en-US": ("what should", "how should", "advice", "what can i do", "how can i"),
    },
    "obstacle": {
        "zh-CN": ("阻碍", "障碍", "卡点", "困难", "为什么不"),
        "en-US": ("obstacle", "barrier", "blocking", "difficulty", "why not"),
    },
    "relationship_dynamic": {
        "zh-CN": ("关系如何", "对方怎么看", "相处", "关系走向", "彼此"),
        "en-US": ("relationship dynamic", "how do they feel", "between us", "connection"),
    },
    "decision_comparison": {
        "zh-CN": ("还是", "哪个更", "二选一", "比较", "选哪个"),
        "en-US": (" or ", "which is better", "between", "compare", "which option"),
    },
    "timing": {
        "zh-CN": ("何时", "什么时候", "多久", "几月", "哪一天"),
        "en-US": ("when", "how long", "what month", "what date", "timing"),
    },
    "self_reflection": {
        "zh-CN": ("我需要看见", "我该理解", "反思", "内在", "学到什么"),
        "en-US": ("what do i need to see", "understand", "reflect", "within me", "learn"),
    },
}

_ZH_EXPLICIT_PERIOD = re.compile(
    r"(?:\d{1,2}|[一二三四五六七八九十]+)月份?|\d{4}年(?:\d{1,2}月)?|"
    r"本周|这周|下周|本月|这个月|下个月|今年|明年|未来\s*\d+\s*(?:天|周|个月|年)"
)
_EN_EXPLICIT_PERIOD = re.compile(
    r"\b(?:in\s+)?(?:january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\b|\b(?:this|next)\s+(?:week|month|year)\b|"
    r"\b(?:within|in)\s+\d+\s+(?:days?|weeks?|months?|years?)\b|\b20\d{2}\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class QuestionAnalysis:
    """Provider-independent facts used to route bounded Tarot context."""

    question: str
    locale: Locale
    domain: QuestionDomain
    intents: tuple[QuestionIntent, ...]
    temporal_frame: TemporalFrame
    temporal_anchor: str | None
    anchors: tuple[str, ...]
    analysis_version: str = "arcana-question-analysis.v2"

    def as_payload(self) -> dict[str, object]:
        return {
            "analysis_version": self.analysis_version,
            "question": self.question,
            "locale": self.locale,
            "domain": self.domain,
            "intents": list(self.intents),
            "temporal_frame": self.temporal_frame,
            "temporal_anchor": self.temporal_anchor,
            "anchors": list(self.anchors),
        }


def _contains(text: str, term: str, *, locale: Locale) -> bool:
    if locale == "zh-CN":
        return term in text
    return (
        term in text
        if term.startswith(" ") or term.endswith(" ")
        else bool(re.search(rf"\b{re.escape(term)}\b", text))
    )


def _classify_domain(text: str, locale: Locale) -> tuple[QuestionDomain, tuple[str, ...]]:
    matches: dict[QuestionDomain, tuple[str, ...]] = {}
    for domain, localized in _DOMAIN_TERMS.items():
        if domain == "general":
            continue
        found = tuple(term for term in localized[locale] if _contains(text, term, locale=locale))
        if found:
            matches[domain] = found
    if not matches:
        return "general", ()
    best_score = max(len(terms) for terms in matches.values())
    winners = [domain for domain, terms in matches.items() if len(terms) == best_score]
    if len(winners) > 1 and "decision" in winners:
        winners.remove("decision")
    if len(winners) != 1:
        return "general", tuple(term for terms in matches.values() for term in terms)
    winner = winners[0]
    return winner, matches[winner]


def _temporal(text: str, locale: Locale) -> tuple[TemporalFrame, str | None]:
    match = (_ZH_EXPLICIT_PERIOD if locale == "zh-CN" else _EN_EXPLICIT_PERIOD).search(text)
    if match is not None:
        return "explicit_period", match.group(0)
    if any(
        term in text
        for term in (
            ("过去", "之前", "曾经") if locale == "zh-CN" else ("past", "before", "previously")
        )
    ):
        return "past", None
    if any(
        term in text
        for term in (
            ("现在", "目前", "当下") if locale == "zh-CN" else ("now", "present", "currently")
        )
    ):
        return "present", None
    if any(
        term in text
        for term in (
            ("未来", "近期", "接下来") if locale == "zh-CN" else ("future", "soon", "coming")
        )
    ):
        return "near_future", None
    return "unspecified", None


def analyze_question(question: str, locale: Locale) -> QuestionAnalysis:
    """Classify only explicit lexical signals and otherwise fail safely to GENERAL."""

    normalized = " ".join(question.strip().split())
    comparison_text = normalized if locale == "zh-CN" else f" {normalized.casefold()} "
    domain, domain_anchors = _classify_domain(comparison_text, locale)
    temporal_frame, temporal_anchor = _temporal(comparison_text, locale)
    intents: list[QuestionIntent] = []
    intent_anchors: list[str] = []
    for intent, localized in _INTENT_TERMS.items():
        found = [
            term for term in localized[locale] if _contains(comparison_text, term, locale=locale)
        ]
        if found:
            intents.append(intent)
            intent_anchors.extend(found)
    if temporal_frame != "unspecified" and "timing" not in intents:
        intents.append("timing")
    if not intents:
        intents.append("self_reflection")
    anchors: list[str] = []
    for anchor in (
        *domain_anchors,
        *intent_anchors,
        *((temporal_anchor,) if temporal_anchor else ()),
    ):
        cleaned = anchor.strip()
        if cleaned and cleaned not in anchors:
            anchors.append(cleaned)
    return QuestionAnalysis(
        question=normalized,
        locale=locale,
        domain=domain,
        intents=tuple(intents),
        temporal_frame=temporal_frame,
        temporal_anchor=temporal_anchor,
        anchors=tuple(anchors[:8]),
    )
