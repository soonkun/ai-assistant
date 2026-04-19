# tests/tool_router/test_schemas.py
"""N-5: tool_specs() 반환 구조 및 JSON Schema 유효성 검증."""

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from src.tool_router.router import ToolRouter


def test_tool_specs_length_and_names(router: ToolRouter) -> None:
    """N-5: 리스트 길이 4, 이름 집합 검증."""
    specs = router.tool_specs()
    assert len(specs) == 4
    names = {s["function"]["name"] for s in specs}
    assert names == {"add_event", "get_events", "search_docs", "take_screenshot"}


def test_tool_specs_function_key_exists(router: ToolRouter) -> None:
    """N-5: 각 항목에 'function' 키 존재."""
    for spec in router.tool_specs():
        assert "function" in spec
        assert "name" in spec["function"]
        assert "parameters" in spec["function"]


def test_tool_specs_schema_valid(router: ToolRouter) -> None:
    """N-5: 각 function.parameters가 Draft202012Validator.check_schema로 유효."""
    for spec in router.tool_specs():
        params = spec["function"]["parameters"]
        # check_schema raises SchemaError if invalid
        Draft202012Validator.check_schema(params)


def test_tool_specs_returns_new_list_each_call(router: ToolRouter) -> None:
    """N-5: 호출마다 새 리스트 인스턴스 반환."""
    specs1 = router.tool_specs()
    specs2 = router.tool_specs()
    assert specs1 is not specs2


def test_tool_specs_type_field(router: ToolRouter) -> None:
    """각 spec에 type='function' 존재."""
    for spec in router.tool_specs():
        assert spec.get("type") == "function"
