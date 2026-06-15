"""Unit tests for SillyTavern V2 import/export field mapping."""

import pytest
from app.domain.persona.service import PersonaService


class FakeRepo:
    """Minimal fake repository for unit testing import/export logic."""
    def __init__(self):
        self.personas = []
        self._next_id = 1
        self.session = self  # for delete_persona compat

    async def get_by_id(self, persona_id: int):
        for p in self.personas:
            if p.id == persona_id:
                return p
        return None

    async def create(self, persona):
        persona.id = self._next_id
        self._next_id += 1
        self.personas.append(persona)
        return persona

    async def update(self, persona):
        for i, p in enumerate(self.personas):
            if p.id == persona.id:
                self.personas[i] = persona
                break
        return persona

    async def hard_delete(self, persona_id: int) -> bool:
        for i, p in enumerate(self.personas):
            if p.id == persona_id:
                del self.personas[i]
                return True
        return False

    async def clear_default_for_scope(self, scope, user_id=None):
        pass

    async def execute(self, stmt):
        pass  # no-op for chat_session cleanup


class FakePersona:
    """Minimal persona-like object for testing."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.mark.asyncio
async def test_import_v2_maps_all_fields():
    """Import should map all 7 ST V2 core fields + tags."""
    svc = PersonaService(FakeRepo())

    st_json = {
        "data": {
            "name": "Test",
            "description": "Desc",
            "personality": "Happy",
            "scenario": "Park guide",
            "first_mes": "Hi!",
            "mes_example": "<START>",
            "system_prompt": "Be nice and helpful to everyone",
            "tags": ["tag1", "tag2"],
            "extra_field": "should be ignored",
        }
    }

    result = await svc.import_v2(st_json, user_id=1, scope="user")
    assert result.name == "Test"
    assert result.description == "Desc"
    assert result.personality == "Happy"
    assert result.scenario == "Park guide"
    assert result.first_mes == "Hi!"
    assert result.mes_example == "<START>"
    assert result.system_prompt == "Be nice and helpful to everyone"
    assert result.tags == ["tag1", "tag2"]
    assert result.scope == "user"


@pytest.mark.asyncio
async def test_import_v2_missing_fields_use_defaults():
    """Import with missing optional fields should use empty defaults."""
    svc = PersonaService(FakeRepo())

    st_json = {"data": {"name": "Minimal"}}

    result = await svc.import_v2(st_json, user_id=1, scope="user")
    assert result.name == "Minimal"
    assert result.description == ""
    assert result.personality == ""
    assert result.first_mes == ""


@pytest.mark.asyncio
async def test_import_v2_no_data_wrapper():
    """Import handles ST JSON without 'data' wrapper (legacy format)."""
    svc = PersonaService(FakeRepo())

    st_json = {"name": "No Wrapper", "description": "Legacy format"}

    result = await svc.import_v2(st_json, user_id=1, scope="user")
    assert result.name == "No Wrapper"
    assert result.description == "Legacy format"


def test_export_v2_includes_all_fields():
    """Export should include all non-empty ST V2 fields."""
    svc = PersonaService(FakeRepo())

    p = FakePersona(
        name="ExportTest",
        description="A test persona",
        personality="Witty",
        scenario="Coffee shop",
        first_mes="Welcome!",
        mes_example="...",
        system_prompt="You are a barista.",
        tags=["coffee", "friendly"],
    )

    result = svc.export_v2(p)
    assert "data" in result
    data = result["data"]
    assert data["name"] == "ExportTest"
    assert data["description"] == "A test persona"
    assert data["personality"] == "Witty"
    assert data["scenario"] == "Coffee shop"
    assert data["first_mes"] == "Welcome!"
    assert data["system_prompt"] == "You are a barista."
    assert data["tags"] == ["coffee", "friendly"]


def test_export_v2_empty_fields_omitted():
    """Export should omit fields with empty/None values."""
    svc = PersonaService(FakeRepo())
    p = FakePersona(name="Min", description=None, personality="", scenario=None,
                     first_mes="", mes_example=None, system_prompt="", tags=[])

    result = svc.export_v2(p)
    data = result["data"]
    assert data["name"] == "Min"
    assert "description" not in data
    assert "personality" not in data
