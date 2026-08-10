"""Deterministic local Fixture Provider with no network-capable dependencies."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from creativedeploy_api.ai.constants import FIXTURE_CURRENCY, FIXTURE_PROVIDER_KEY
from creativedeploy_api.ai.encryption import SecretBytes


@dataclass(frozen=True, slots=True)
class FixtureValidation:
    valid: bool
    status: Literal["fixture_valid", "fixture_invalid"]
    message_code: str


@dataclass(frozen=True, slots=True)
class FixtureInvocationResult:
    output: dict[str, object]
    input_units: int
    output_units: int
    cost_minor_units: int
    currency: str = FIXTURE_CURRENCY


class FixtureProviderError(RuntimeError):
    def __init__(self, category: str) -> None:
        super().__init__("Fixture provider scenario failed.")
        self.category = category


class FixtureProviderAdapter:
    """Pure deterministic adapter; it never constructs HTTP/socket/proxy state."""

    provider_key = FIXTURE_PROVIDER_KEY
    adapter_version = "fixture-adapter-v1"

    def validate_credential(self, secret: SecretBytes) -> FixtureValidation:
        value = secret.value
        valid = value.startswith(b"fixture-sk-") and 20 <= len(value) <= 160
        return FixtureValidation(
            valid=valid,
            status="fixture_valid" if valid else "fixture_invalid",
            message_code="FIXTURE_CREDENTIAL_ACCEPTED" if valid else "FIXTURE_CREDENTIAL_REJECTED",
        )

    def invoke(
        self,
        payload: dict[str, object],
        secret: SecretBytes,
        *,
        scenario: str = "success",
    ) -> FixtureInvocationResult:
        if not self.validate_credential(secret).valid:
            raise FixtureProviderError("authentication_failed")
        if scenario != "success":
            allowed = {
                "authentication_failed",
                "invalid_request",
                "provider_unavailable",
                "rate_limited",
                "outcome_unknown",
            }
            raise FixtureProviderError(scenario if scenario in allowed else "invalid_request")
        encoded = repr(sorted(payload.items())).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        input_units = max(1, len(encoded) // 8)
        paint_plan_input = payload.get("paint_plan_input")
        if isinstance(paint_plan_input, dict):
            output = self._paint_plan_output(paint_plan_input, digest=digest)
            output_units = max(12, len(repr(output).encode("utf-8")) // 8)
        else:
            output = {
                "fixture": True,
                "local_only": True,
                "result_id": f"fixture-{digest[:16]}",
                "summary": "Deterministic local fixture response",
            }
            output_units = 12
        return FixtureInvocationResult(
            output=output,
            input_units=input_units,
            output_units=output_units,
            cost_minor_units=input_units + output_units,
        )

    @staticmethod
    def _paint_plan_output(source: dict[str, object], *, digest: str) -> dict[str, object]:
        """Build a deterministic multi-region document from governed metadata."""

        raw_generation_locale = source.get("generation_locale", "en-US")
        if not isinstance(raw_generation_locale, str) or raw_generation_locale not in {
            "zh-CN",
            "en-US",
        }:
            raise FixtureProviderError("invalid_request")
        generation_locale = raw_generation_locale
        region_set = source.get("region_set")
        if not isinstance(region_set, dict):
            raise FixtureProviderError("invalid_request")
        raw_regions = region_set.get("regions")
        if not isinstance(raw_regions, list):
            raise FixtureProviderError("invalid_request")
        palettes = {
            "en-US": (
                "warm neutral gray",
                "muted copper",
                "deep graphite",
                "soft teal accent",
                "desaturated ochre",
            ),
            "zh-CN": (
                "暖中性灰",
                "低饱和铜色",
                "深石墨色",
                "柔和青绿色点缀",
                "低饱和赭石色",
            ),
        }
        palette = palettes[generation_locale]
        instructions: list[dict[str, object]] = []
        for raw_region in raw_regions:
            if not isinstance(raw_region, dict) or raw_region.get("kind") != "paint":
                continue
            raw_id = raw_region.get("id")
            raw_key = raw_region.get("stable_region_key")
            label = raw_region.get("label")
            if (
                not isinstance(raw_id, str)
                or not isinstance(raw_key, str)
                or not isinstance(label, str)
            ):
                raise FixtureProviderError("invalid_request")
            try:
                UUID(raw_id)
                stable_key = UUID(raw_key)
            except ValueError as exc:
                raise FixtureProviderError("invalid_request") from exc
            color = palette[stable_key.int % len(palette)]
            if generation_locale == "zh-CN":
                preparation = "清洁表面，并均匀轻磨以提高附着力。"  # noqa: RUF001
                base_coat = f"在已批准边界内均匀涂覆一层遮盖力完整的{color}底色。"
                layer_strategy = "从大面积内部向边界逐步叠加两层薄涂；所有排除区域保持不变。"  # noqa: RUF001
                edge_treatment = "保持外轮廓清晰，仅柔化区域内部的过渡。"  # noqa: RUF001
                lighting_guidance = "保留左上方窄高光，并控制右下方阴影。"  # noqa: RUF001
                material_guidance = "使用哑光体系，并保留参考表面的材质特征。"  # noqa: RUF001
                warnings = ["不得越过已批准的区域边界。"]
            else:
                preparation = "Clean the surface and apply a light, even key."
                base_coat = f"Apply one opaque {color} base coat within the approved boundary."
                layer_strategy = (
                    "Build two thin layers from the broad interior toward the boundary; "
                    "keep every excluded region untouched."
                )
                edge_treatment = "Keep the silhouette crisp and feather only internal transitions."
                lighting_guidance = (
                    "Reserve a narrow upper-left highlight and a controlled lower-right shadow."
                )
                material_guidance = "Use a matte finish and preserve the source surface character."
                warnings = ["Do not cross an approved Region boundary."]
            instructions.append(
                {
                    "region_id": raw_id,
                    "stable_region_key": raw_key,
                    # Region labels belong to the approved RegionSet source. The
                    # Fixture localizes only content it owns.
                    "region_label": label,
                    "target_color": color,
                    "preparation": preparation,
                    "base_coat": base_coat,
                    "layer_strategy": layer_strategy,
                    "edge_treatment": edge_treatment,
                    "lighting_guidance": lighting_guidance,
                    "material_guidance": material_guidance,
                    "warnings": warnings,
                    "confidence_ppm": 900_000,
                }
            )
        if not instructions:
            raise FixtureProviderError("invalid_request")
        if generation_locale == "zh-CN":
            title = f"受管 Fixture 涂装方案 {digest[:8]}"
            overall_approach = (
                "从大面积底色逐步推进至受边界约束的边缘与光照细节，并保留所有排除区域。"  # noqa: RUF001
            )
            safety_notes = [
                "仅使用已批准的图像与 RegionSet 修订。",
                "若实际表面与参考资料存在明显差异，请停止操作。",  # noqa: RUF001
            ]
        else:
            title = f"Governed fixture paint plan {digest[:8]}"
            overall_approach = (
                "Work from broad base shapes toward bounded edge and lighting details, "
                "preserving every excluded area."
            )
            safety_notes = [
                "Use only the approved image and RegionSet revision.",
                "Stop if the physical surface differs materially from the references.",
            ]
        return {
            "schema_version": "paint-plan.v1",
            "title": title,
            "overall_approach": overall_approach,
            "instructions": instructions,
            "safety_notes": safety_notes,
        }
