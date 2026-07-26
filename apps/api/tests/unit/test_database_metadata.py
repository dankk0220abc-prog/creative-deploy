"""Tests for the database metadata and Alembic foundation."""

import ast
import importlib.util
import operator
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.exc import InvalidRequestError

from creativedeploy_api.db import Base as PublicBase
from creativedeploy_api.db.base import NAMING_CONVENTION, Base

API_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = API_ROOT / "src"
ALEMBIC_ENV_PATH = API_ROOT / "migrations" / "env.py"
APPROVED_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
APPROVED_BUSINESS_TABLES = {
    "command_idempotency_records",
    "paint_projects",
    "state_transition_events",
}
SourceDeclaration = tuple[Path, int, str, str]


def _qualified_name(node: ast.expr, symbol_origins: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return symbol_origins.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value, symbol_origins)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


def _symbol_origins(module: ast.Module) -> dict[str, str]:
    origins: dict[str, str] = {}
    for node in module.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".", maxsplit=1)[0]
                origins[local_name] = alias.name if alias.asname else local_name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "*":
                    continue
                origins[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return origins


def _assigned_names(node: ast.Assign | ast.AnnAssign) -> list[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return [target.id for target in targets if isinstance(target, ast.Name)]


def _assignment_label(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    current = node
    assigned_name = "<unassigned call>"
    enclosing_class: str | None = None
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.Assign, ast.AnnAssign)):
            names = _assigned_names(current)
            if names:
                assigned_name = ",".join(names)
        elif isinstance(current, ast.ClassDef):
            enclosing_class = current.name
            break
    return f"{enclosing_class}.{assigned_name}" if enclosing_class else assigned_name


def _find_orm_infrastructure_declarations_in_source(
    relative_path: Path,
    source: str,
) -> list[SourceDeclaration]:
    declarations: list[SourceDeclaration] = []
    module = ast.parse(source)
    symbol_origins = _symbol_origins(module)
    parents = {
        child: parent for parent in ast.walk(module) for child in ast.iter_child_nodes(parent)
    }
    registry_names: set[str] = set()

    for node in ast.walk(module):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if (
            isinstance(value, ast.Call)
            and _qualified_name(value.func, symbol_origins) == "sqlalchemy.orm.registry"
        ):
            registry_names.update(_assigned_names(node))

    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef) and any(
            _qualified_name(base, symbol_origins) == "sqlalchemy.orm.DeclarativeBase"
            for base in node.bases
        ):
            declarations.append((relative_path, node.lineno, "DeclarativeBase class", node.name))
            continue

        if not isinstance(node, ast.Call):
            continue
        call_name = _qualified_name(node.func, symbol_origins)
        assignment = _assignment_label(node, parents)
        if call_name == "sqlalchemy.orm.declarative_base":
            declarations.append(
                (relative_path, node.lineno, "declarative_base factory", assignment)
            )
        elif (
            call_name is not None
            and call_name.startswith("sqlalchemy.")
            and call_name.endswith(".MetaData")
        ):
            declarations.append((relative_path, node.lineno, "MetaData declaration", assignment))
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "generate_base":
            registry_owner = node.func.value
            direct_registry_call = (
                isinstance(registry_owner, ast.Call)
                and _qualified_name(registry_owner.func, symbol_origins)
                == "sqlalchemy.orm.registry"
            )
            assigned_registry = (
                isinstance(registry_owner, ast.Name) and registry_owner.id in registry_names
            )
            if direct_registry_call or assigned_registry:
                declarations.append(
                    (relative_path, node.lineno, "registry generate_base factory", assignment)
                )

    return declarations


def _find_orm_infrastructure_declarations() -> list[SourceDeclaration]:
    declarations = [
        declaration
        for source_path in SOURCE_ROOT.rglob("*.py")
        for declaration in _find_orm_infrastructure_declarations_in_source(
            source_path.relative_to(SOURCE_ROOT),
            source_path.read_text(encoding="utf-8"),
        )
    ]
    return sorted(declarations, key=lambda item: (str(item[0]), item[1], item[2], item[3]))


def _format_declarations(declarations: list[SourceDeclaration]) -> str:
    return "\n".join(f"{path}:{line}: {kind}: {name}" for path, line, kind, name in declarations)


def _load_alembic_env(module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, ALEMBIC_ENV_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_naming_convention_matches_approved_values() -> None:
    assert isinstance(NAMING_CONVENTION, Mapping)
    assert dict(Base.metadata.naming_convention or {}) == APPROVED_NAMING_CONVENTION
    assert NAMING_CONVENTION == APPROVED_NAMING_CONVENTION


def test_naming_convention_is_runtime_immutable_through_both_public_references() -> None:
    assert Base.metadata.naming_convention is NAMING_CONVENTION

    with pytest.raises(TypeError):
        operator.setitem(NAMING_CONVENTION, "pk", "changed_%(table_name)s")
    with pytest.raises(TypeError):
        operator.setitem(
            Base.metadata.naming_convention,
            "pk",
            "changed_%(table_name)s",
        )


def test_naming_convention_contains_every_constraint_category() -> None:
    assert set(NAMING_CONVENTION) == {"ix", "uq", "ck", "fk", "pk"}


def test_official_metadata_has_exactly_the_approved_business_tables() -> None:
    assert set(Base.metadata.tables) == APPROVED_BUSINESS_TABLES


def test_source_declares_only_one_declarative_base() -> None:
    declarations = _find_orm_infrastructure_declarations()
    declaration_shapes = [(path, kind, name) for path, _line, kind, name in declarations]

    assert declaration_shapes == [
        (
            Path("creativedeploy_api/db/base.py"),
            "DeclarativeBase class",
            "Base",
        ),
        (
            Path("creativedeploy_api/db/base.py"),
            "MetaData declaration",
            "Base.metadata",
        ),
    ], _format_declarations(declarations)


@pytest.mark.parametrize(
    ("source", "expected_kind"),
    [
        (
            "from sqlalchemy.orm import DeclarativeBase as SADeclarativeBase\n"
            "class AlternateBase(SADeclarativeBase):\n"
            "    pass\n",
            "DeclarativeBase class",
        ),
        (
            "from sqlalchemy.orm import declarative_base as make_base\n"
            "AlternateBase = make_base()\n",
            "declarative_base factory",
        ),
        (
            "from sqlalchemy.orm import registry as registry_factory\n"
            "AlternateBase = registry_factory().generate_base()\n",
            "registry generate_base factory",
        ),
        (
            "import sqlalchemy.orm as orm\n"
            "mapper_registry = orm.registry()\n"
            "AlternateBase = mapper_registry.generate_base()\n",
            "registry generate_base factory",
        ),
        (
            "from sqlalchemy import MetaData as SAMetaData\nalternate_metadata = SAMetaData()\n",
            "MetaData declaration",
        ),
    ],
)
def test_source_scan_detects_alternative_orm_infrastructure_declarations(
    source: str,
    expected_kind: str,
) -> None:
    declarations = _find_orm_infrastructure_declarations_in_source(
        Path("synthetic_module.py"),
        source,
    )

    assert len(declarations) == 1, _format_declarations(declarations)
    path, line, kind, _name = declarations[0]
    assert path == Path("synthetic_module.py")
    assert line > 0
    assert kind == expected_kind
    assert "synthetic_module.py:" in _format_declarations(declarations)


def test_source_scan_does_not_treat_business_models_as_new_base_declarations() -> None:
    source = "from creativedeploy_api.db import Base\nclass PaintProject(Base):\n    pass\n"

    assert (
        _find_orm_infrastructure_declarations_in_source(
            Path("paint_project.py"),
            source,
        )
        == []
    )


def test_public_database_base_export_is_the_official_base() -> None:
    assert PublicBase is Base


def test_check_constraints_require_an_explicit_name() -> None:
    temporary_metadata = MetaData(naming_convention=NAMING_CONVENTION)

    with pytest.raises(InvalidRequestError):
        Table(
            "unnamed_check_example",
            temporary_metadata,
            Column("value", Integer, nullable=False),
            CheckConstraint("value > 0"),
        )


def test_named_check_constraint_uses_the_stable_convention() -> None:
    temporary_metadata = MetaData(naming_convention=NAMING_CONVENTION)
    table = Table(
        "named_check_example",
        temporary_metadata,
        Column("value", Integer, nullable=False),
        CheckConstraint("value > 0", name="value_positive"),
    )

    check = next(
        constraint for constraint in table.constraints if isinstance(constraint, CheckConstraint)
    )
    assert str(check.name) == "ck_named_check_example_value_positive"
    assert set(Base.metadata.tables) == APPROVED_BUSINESS_TABLES


def test_all_constraint_categories_use_stable_names_with_immutable_convention() -> None:
    temporary_metadata = MetaData(naming_convention=NAMING_CONVENTION)
    parent = Table(
        "naming_parent",
        temporary_metadata,
        Column("id", Integer, primary_key=True),
    )
    child = Table(
        "naming_child",
        temporary_metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", Integer, ForeignKey("naming_parent.id"), nullable=False),
        Column("slug", String, nullable=False),
        UniqueConstraint("slug"),
        CheckConstraint("id > 0", name="id_positive"),
    )
    index = Index(None, child.c.slug)

    unique = next(
        constraint for constraint in child.constraints if isinstance(constraint, UniqueConstraint)
    )
    foreign_key = next(
        constraint
        for constraint in child.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    )
    check = next(
        constraint for constraint in child.constraints if isinstance(constraint, CheckConstraint)
    )

    assert str(parent.primary_key.name) == "pk_naming_parent"
    assert str(child.primary_key.name) == "pk_naming_child"
    assert str(unique.name) == "uq_naming_child_slug"
    assert str(foreign_key.name) == "fk_naming_child_parent_id_naming_parent"
    assert str(index.name) == "ix_naming_child_slug"
    assert str(check.name) == "ck_naming_child_id_positive"
    assert set(Base.metadata.tables) == APPROVED_BUSINESS_TABLES


def test_importing_base_does_not_construct_an_engine() -> None:
    source = """
import sqlalchemy.ext.asyncio

def fail(*args, **kwargs):
    raise AssertionError("Base import attempted to create an engine")

sqlalchemy.ext.asyncio.create_async_engine = fail
from creativedeploy_api.db.base import Base
assert set(Base.metadata.tables) == {
    "paint_projects",
    "state_transition_events",
    "command_idempotency_records",
}
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


def test_importing_alembic_environment_has_no_settings_or_engine_side_effect(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("Alembic environment import triggered runtime configuration")

    monkeypatch.setattr("creativedeploy_api.core.config.get_settings", fail)
    monkeypatch.setattr("creativedeploy_api.db.engine.create_database_engine", fail)

    module = _load_alembic_env("creativedeploy_test_alembic_env_no_side_effect")
    captured = capsys.readouterr()

    assert module.target_metadata is Base.metadata
    assert captured.out == ""
    assert captured.err == ""


def test_alembic_target_metadata_is_the_official_metadata() -> None:
    module = _load_alembic_env("creativedeploy_test_alembic_env_metadata")

    assert module.target_metadata is Base.metadata
    assert set(module.target_metadata.tables) == APPROVED_BUSINESS_TABLES
    assert set(module.REGISTERED_MODEL_TABLES) == APPROVED_BUSINESS_TABLES


def test_offline_error_message_contains_no_connection_information() -> None:
    module = _load_alembic_env("creativedeploy_test_alembic_env_offline")
    message = module.OFFLINE_MIGRATIONS_ERROR

    assert message == "Offline migrations are not supported in the current database foundation."
    assert "://" not in message
    assert "password" not in message.lower()
