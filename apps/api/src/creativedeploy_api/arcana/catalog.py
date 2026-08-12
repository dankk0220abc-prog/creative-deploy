"""Original, compact Arcana Tarot reference data.

The text in this module is CreativeDeploy-authored synthesis. It does not copy a
commercial deck or long-form interpretation source. The expansion functions are
also used by the migration so every installed database receives exactly 78 cards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class TarotCardSeed:
    card_id: str
    arcana: str
    suit: str | None
    rank: str
    number: int
    name_en: str
    name_zh: str
    upright_en: str
    upright_zh: str
    reversed_en: str
    reversed_zh: str
    theme: str


_MAJORS: Final[tuple[tuple[str, str, str, str, str, str, str], ...]] = (
    (
        "fool",
        "The Fool",
        "愚者",
        "beginnings, trust, open possibility",
        "启程、信任、开放的可能",
        "haste, naivety, a delayed step",
        "仓促、天真、迟疑的起步",
    ),
    (
        "magician",
        "The Magician",
        "魔术师",
        "agency, skill, focused action",
        "能动性、技艺、专注行动",
        "scattered effort, manipulation, unused skill",
        "精力分散、操控、能力未用",
    ),
    (
        "high-priestess",
        "The High Priestess",
        "女祭司",
        "intuition, privacy, inner knowledge",
        "直觉、内在空间、内在知识",
        "ignored intuition, secrecy, surface noise",
        "忽略直觉、封闭、表层噪音",
    ),
    (
        "empress",
        "The Empress",
        "皇后",
        "care, growth, embodied abundance",
        "照料、生长、具象的丰盛",
        "overgiving, stagnation, neglected needs",
        "过度付出、停滞、需求被忽略",
    ),
    (
        "emperor",
        "The Emperor",
        "皇帝",
        "structure, boundaries, steady authority",
        "结构、边界、稳定权威",
        "rigidity, control, weak foundations",
        "僵化、控制、基础不稳",
    ),
    (
        "hierophant",
        "The Hierophant",
        "教皇",
        "tradition, learning, shared values",
        "传统、学习、共同价值",
        "dogma, borrowed beliefs, unconventional path",
        "教条、借来的信念、非传统路径",
    ),
    (
        "lovers",
        "The Lovers",
        "恋人",
        "alignment, choice, honest connection",
        "一致、选择、坦诚连接",
        "misalignment, avoidance, divided values",
        "失衡、回避、价值分裂",
    ),
    (
        "chariot",
        "The Chariot",
        "战车",
        "direction, resolve, coordinated will",
        "方向、决心、协调意志",
        "drift, force, competing impulses",
        "漂移、强推、冲动相争",
    ),
    (
        "strength",
        "Strength",
        "力量",
        "courage, patience, gentle influence",
        "勇气、耐心、温和影响",
        "self-doubt, pressure, reactive force",
        "自我怀疑、压力、反应性用力",
    ),
    (
        "hermit",
        "The Hermit",
        "隐士",
        "reflection, discernment, purposeful solitude",
        "反思、辨别、有目的的独处",
        "isolation, avoidance, insight withheld",
        "孤立、逃避、洞见未分享",
    ),
    (
        "wheel-of-fortune",
        "Wheel of Fortune",
        "命运之轮",
        "cycles, timing, changing conditions",
        "周期、时机、条件变化",
        "resistance, repetition, poor timing",
        "抗拒、重复、时机不佳",
    ),
    (
        "justice",
        "Justice",
        "正义",
        "accountability, balance, clear consequence",
        "责任、平衡、清晰后果",
        "bias, evasion, unresolved imbalance",
        "偏见、逃避、失衡未解",
    ),
    (
        "hanged-man",
        "The Hanged Man",
        "倒吊人",
        "pause, reframing, willing surrender",
        "暂停、换角度、自愿放下",
        "stalling, martyrdom, refusal to release",
        "拖延、自我牺牲、拒绝放手",
    ),
    (
        "death",
        "Death",
        "死神",
        "ending, transition, necessary release",
        "结束、转变、必要的放下",
        "clinging, delayed change, unfinished closure",
        "执着、变化延迟、收尾未完",
    ),
    (
        "temperance",
        "Temperance",
        "节制",
        "integration, proportion, patient adjustment",
        "整合、分寸、耐心调整",
        "excess, friction, unstable mix",
        "过量、摩擦、组合不稳",
    ),
    (
        "devil",
        "The Devil",
        "恶魔",
        "attachment, appetite, visible constraint",
        "依附、欲望、可见束缚",
        "release, denial, a loosening bond",
        "松绑、否认、关系正在松动",
    ),
    (
        "tower",
        "The Tower",
        "高塔",
        "disruption, revelation, structures exposed",
        "扰动、揭示、结构暴露",
        "averted shock, private upheaval, slow collapse",
        "冲击暂缓、内在震荡、缓慢崩解",
    ),
    (
        "star",
        "The Star",
        "星星",
        "renewal, candor, quiet hope",
        "更新、坦诚、安静希望",
        "discouragement, depletion, hope obscured",
        "气馁、耗竭、希望被遮蔽",
    ),
    (
        "moon",
        "The Moon",
        "月亮",
        "ambiguity, imagination, hidden influence",
        "暧昧、想象、隐性影响",
        "clarification, fear receding, illusion tested",
        "澄清、恐惧退去、幻象受检验",
    ),
    (
        "sun",
        "The Sun",
        "太阳",
        "clarity, vitality, shared confidence",
        "清晰、活力、共同信心",
        "muted joy, overexposure, delayed clarity",
        "喜悦减弱、过度暴露、清晰延迟",
    ),
    (
        "judgement",
        "Judgement",
        "审判",
        "reckoning, renewal, answered calling",
        "复盘、更新、回应召唤",
        "self-judgment, avoidance, an unanswered call",
        "自我评判、回避、召唤未回应",
    ),
    (
        "world",
        "The World",
        "世界",
        "completion, integration, wider belonging",
        "完成、整合、更广的归属",
        "loose ends, partial closure, narrowed view",
        "遗留事项、部分收尾、视野收窄",
    ),
)

_SUITS: Final[tuple[tuple[str, str, str, str, str], ...]] = (
    ("wands", "Wands", "权杖", "initiative, creativity, momentum", "行动力、创造、推进"),
    ("cups", "Cups", "圣杯", "feeling, relationship, receptivity", "感受、关系、接纳"),
    ("swords", "Swords", "宝剑", "thought, truth, decision", "思考、真相、决断"),
    (
        "pentacles",
        "Pentacles",
        "星币",
        "resources, craft, material reality",
        "资源、技艺、现实基础",
    ),
)

_RANKS: Final[tuple[tuple[str, str, str, str, str], ...]] = (
    ("ace", "Ace", "首牌", "a concentrated opening", "集中开启"),
    ("two", "Two", "二", "choice and pairing", "选择与配对"),
    ("three", "Three", "三", "development through participation", "在参与中发展"),
    ("four", "Four", "四", "stability and containment", "稳定与容纳"),
    ("five", "Five", "五", "friction that reveals priorities", "揭示重点的摩擦"),
    ("six", "Six", "六", "adjustment and exchange", "调整与交换"),
    ("seven", "Seven", "七", "assessment under pressure", "压力下的评估"),
    ("eight", "Eight", "八", "movement through practice", "通过练习推进"),
    ("nine", "Nine", "九", "maturity near completion", "接近完成的成熟"),
    ("ten", "Ten", "十", "culmination and consequence", "汇聚与后果"),
    ("page", "Page", "侍从", "curiosity and a first message", "好奇与初次讯息"),
    ("knight", "Knight", "骑士", "committed pursuit", "投入追寻"),
    ("queen", "Queen", "王后", "inward mastery and stewardship", "内在掌握与照料"),
    ("king", "King", "国王", "outward mastery and responsibility", "外在掌握与责任"),
)


def card_seeds() -> tuple[TarotCardSeed, ...]:
    cards = [
        TarotCardSeed(
            card_id=f"major-{index:02d}-{slug}",
            arcana="major",
            suit=None,
            rank=str(index),
            number=index,
            name_en=name_en,
            name_zh=name_zh,
            upright_en=upright_en,
            upright_zh=upright_zh,
            reversed_en=reversed_en,
            reversed_zh=reversed_zh,
            theme=slug,
        )
        for index, (
            slug,
            name_en,
            name_zh,
            upright_en,
            upright_zh,
            reversed_en,
            reversed_zh,
        ) in enumerate(_MAJORS)
    ]
    for suit_slug, suit_en, suit_zh, suit_theme_en, suit_theme_zh in _SUITS:
        for number, (rank_slug, rank_en, rank_zh, rank_theme_en, rank_theme_zh) in enumerate(
            _RANKS, start=1
        ):
            cards.append(
                TarotCardSeed(
                    card_id=f"minor-{suit_slug}-{rank_slug}",
                    arcana="minor",
                    suit=suit_slug,
                    rank=rank_slug,
                    number=number,
                    name_en=f"{rank_en} of {suit_en}",
                    name_zh=f"{suit_zh}{rank_zh}",
                    upright_en=f"{rank_theme_en} expressed through {suit_theme_en}",
                    upright_zh=f"以{suit_theme_zh}呈现{rank_theme_zh}",
                    reversed_en=f"blocked or overextended {rank_theme_en} within {suit_theme_en}",
                    reversed_zh=f"{suit_theme_zh}中的{rank_theme_zh}受阻或过度延伸",
                    theme=f"{suit_slug}:{rank_slug}",
                )
            )
    return tuple(cards)


THREE_CARD_SPREAD: Final[dict[str, object]] = {
    "key": "past-present-future",
    "version": 1,
    "name_en": "Past / Present / Future",
    "name_zh": "过去 / 现在 / 未来",
    "positions": [
        {"key": "past", "name_en": "Past", "name_zh": "过去"},
        {"key": "present", "name_en": "Present", "name_zh": "现在"},
        {"key": "future", "name_en": "Future", "name_zh": "未来"},
    ],
}
