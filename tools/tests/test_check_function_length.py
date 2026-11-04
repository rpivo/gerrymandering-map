from textwrap import dedent

from check_function_length import find_long_functions, main


def make_function(name: str, total_lines: int, indent: str = "", prefix: str = "def") -> str:
    """Build a function whose def line through last line spans exactly total_lines."""
    body = [f"{indent}    x = {i}" for i in range(total_lines - 1)]
    return "\n".join([f"{indent}{prefix} {name}():", *body]) + "\n"


def test_function_at_limit_passes():
    assert find_long_functions(make_function("ok", 100), "a.py") == []


def test_function_over_limit_is_reported_with_its_length():
    found = find_long_functions(make_function("too_long", 101), "a.py")
    assert [(f.name, f.lineno, f.length) for f in found] == [("too_long", 1, 101)]


def test_async_functions_are_checked():
    found = find_long_functions(make_function("slow", 101, prefix="async def"), "a.py")
    assert [f.name for f in found] == ["slow"]


def test_methods_are_checked_and_named_by_class():
    source = "class Shape:\n" + make_function("area", 101, indent="    ")
    found = find_long_functions(source, "a.py")
    assert [(f.name, f.lineno) for f in found] == [("Shape.area", 2)]


def test_short_function_after_long_one_is_not_reported():
    source = make_function("long_one", 101) + make_function("short_one", 3)
    assert [f.name for f in find_long_functions(source, "a.py")] == ["long_one"]


def test_custom_limit():
    assert [f.name for f in find_long_functions(make_function("f", 11), "a.py", max_lines=10)] == [
        "f"
    ]


def test_main_fails_on_a_long_function_and_skips_virtualenvs(tmp_path, capsys):
    (tmp_path / "good.py").write_text(make_function("fine", 5))
    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "vendored.py").write_text(make_function("ignored", 500))
    assert main([str(tmp_path)]) == 0

    (tmp_path / "bad.py").write_text(make_function("huge", 150))
    assert main([str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "bad.py:1 huge is 150 lines" in out
    assert "ignored" not in out


def test_main_reports_syntax_errors_as_failures(tmp_path, capsys):
    (tmp_path / "broken.py").write_text(
        dedent("""\
        def oops(:
            pass
    """)
    )
    assert main([str(tmp_path)]) == 1
    assert "broken.py" in capsys.readouterr().out
