"""Minimal original PaintPilot corpus proving shared local retrieval/citations."""

# ruff: noqa: RUF001

from __future__ import annotations

from typing import Final, Literal

from creativedeploy_api.ai.retrieval import RetrievedContextBundle, RetrievedContextUnit

Locale = Literal["zh-CN", "en-US"]
CORPUS_ID: Final = "paintpilot-studio-practice"
CORPUS_VERSION: Final = "paintpilot-studio-practice-v1"
SOURCE_ID: Final = "creativedeploy-paintpilot-studio-practice-v1"
SOURCE_TITLE: Final = "CreativeDeploy PaintPilot Studio Practice Notes"

_CONTENT: Final[dict[Locale, tuple[tuple[str, str, str], ...]]] = {
    "en-US": (
        (
            "surface-preparation",
            "Surface preparation",
            "Treat visual material classification as provisional. Clean, dry, and test a small "
            "inconspicuous area before committing to a primer or base coat.",
        ),
        (
            "layering-and-edges",
            "Layering and edge control",
            "Build color in thin, observable layers. Preserve planned hard edges deliberately and "
            "soften transitions only where the approved region geometry supports that choice.",
        ),
        (
            "safety-and-compatibility",
            "Safety and finish compatibility",
            "Do not infer chemical compatibility, ventilation, cure time, or protective equipment "
            "from an image. Follow the selected material manufacturer's current instructions.",
        ),
    ),
    "zh-CN": (
        (
            "surface-preparation",
            "表面准备",
            "把视觉上的材质判断视为暂定结论。正式选择底漆或底色前，应先清洁、干燥，并在不显眼的小区域测试。",
        ),
        (
            "layering-and-edges",
            "分层与边缘控制",
            "用薄而可观察的色层逐步建立颜色。需要硬边时应明确保留，只有在已批准的区域几何支持时才柔化过渡。",
        ),
        (
            "safety-and-compatibility",
            "安全与涂层兼容性",
            "不要仅凭图像推断化学兼容性、通风、固化时间或防护装备。应遵循所选材料制造商的现行说明。",
        ),
    ),
}


class LocalPaintPilotKnowledgeLayer:
    """Deterministic repository-local retrieval with no Provider dependency."""

    def retrieve(self, *, locale: Locale) -> RetrievedContextBundle:
        units = [
            RetrievedContextUnit(
                source_id=SOURCE_ID,
                source_title=SOURCE_TITLE,
                source_type="original repository product knowledge",
                repository_reference=(
                    f"repo://apps/api/src/creativedeploy_api/paintpilot/knowledge.py#{section}"
                ),
                chunk_id=f"paintpilot:{section}:{locale}:v1",
                section=title,
                content=content,
                retrieval_rationale=(
                    "Small governed practice note relevant to structured paint planning."
                ),
                retrieval_score_ppm=900_000,
                locale=locale,
                corpus_id=CORPUS_ID,
                corpus_version=CORPUS_VERSION,
            )
            for section, title, content in _CONTENT[locale]
        ]
        return RetrievedContextBundle(product_space="paintpilot", units=units)
