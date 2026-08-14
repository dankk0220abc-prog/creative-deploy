"""Focused contracts for the Phase 3B validation boundary."""

from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MAKEFILE = REPOSITORY_ROOT / "Makefile"


def _assignment_block(makefile: str, name: str) -> str:
    lines = makefile.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith(f"{name} :="))
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if not line.startswith("\t"):
            break
        block.append(line)
    return "\n".join(block)


def _target_block(makefile: str, name: str) -> str:
    lines = makefile.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith(f"{name}:"))
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if not line.startswith("\t"):
            break
        block.append(line)
    return "\n".join(block)


def test_phase3b_makefile_head_and_environment_denylists_are_fail_closed() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "ALEMBIC_HEAD := 6a01b2c3d4e6" in makefile

    for assignment in (
        "INTEGRATION_DATABASE_ENV",
        "WEB_COMMAND_ENV",
        "API_UNIT_COMMAND_ENV",
    ):
        block = _assignment_block(makefile, assignment)
        assert "-u PHASE3B_PAINT_PLAN_ENABLED" in block
        assert "-u VITE_PHASE3B_PAINT_PLAN_ENABLED" in block


def test_phase3b_focused_target_migrates_and_asserts_the_exact_head() -> None:
    makefile = MAKEFILE.read_text(encoding="utf-8")
    target = _target_block(makefile, "test-api-phase3b")
    assert target.startswith("test-api-phase3b: ensure-db")
    assert "$(INTEGRATION_DATABASE_ENV)" in target
    assert "$(API_UNIT_COMMAND_ENV)" in target
    assert "alembic -c $(ALEMBIC_CONFIG) upgrade head" in target
    assert 'test "$$current_revision" = "$(ALEMBIC_HEAD) (head)"' in target
    assert "$(PHASE3B_UNIT_TESTS)" in target
    assert 'pytest -q "$(PHASE3B_INTEGRATION_TEST)" -m integration' in target
    assert 'test -f "$(PHASE3B_INTEGRATION_TEST)"' not in target
    assert "PHASE3B_FOCUSED_INTEGRATION_NOT_PRESENT" not in target
