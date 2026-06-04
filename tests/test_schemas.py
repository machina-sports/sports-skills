"""Schema quality guards — the generated tool schemas are what agents see."""

from sports_skills.cli import _REGISTRY, _generate_schema


def _all_tools():
    for module in sorted(_REGISTRY):
        schema = _generate_schema(module)
        tools = schema if isinstance(schema, list) else schema.get("tools", [])
        yield from tools


def test_every_param_has_a_description():
    # Agents pick arguments from the schema alone; an undocumented param
    # means the model guesses its shape (see issue #69). New commands must
    # ship with Args: docstrings on their module wrappers.
    missing = []
    for tool in _all_tools():
        props = tool.get("parameters", {}).get("properties", {})
        for name, prop in props.items():
            if not prop.get("description"):
                missing.append(f"{tool['name']}.{name}")
    assert not missing, (
        "Schema params missing descriptions (add Args: entries to the "
        f"module wrapper docstrings): {', '.join(missing)}"
    )


def test_every_tool_has_a_real_description():
    # The fallback description ("X command for Y") means the wrapper has
    # no docstring at all.
    bad = [
        t["name"]
        for t in _all_tools()
        if t.get("description", "").endswith(f"command for {t['name'].split('_')[0]}")
    ]
    assert not bad, f"Tools with fallback descriptions: {', '.join(bad)}"
