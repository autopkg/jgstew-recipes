"""Unit tests for FileConfigParser methods (env_safe, load_config, read_*)."""

import textwrap

import pytest
from autopkglib import ProcessorError
from FileConfigParser import DEFAULT_SECTION, FileConfigParser

# ---- env_safe (static) ----------------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("simple", "simple"),
        ("a.b", "a_b"),
        ("a b c", "a_b_c"),
        ("weird!!name", "weird_name"),
        ("dash-dot.dot", "dash_dot_dot"),
    ],
)
def test_env_safe(text, expected):
    assert FileConfigParser.env_safe(text) == expected


# ---- load_config / read_single / read_all ---------------------------------


def _write_ini(tmp_path, text):
    path = tmp_path / "config.ini"
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return str(path)


def test_load_config_with_sections(tmp_path):
    path = _write_ini(
        tmp_path,
        """\
        [server]
        host = example.com
        port = 8080
        """,
    )
    proc = FileConfigParser({})
    config = proc.load_config(path)
    assert config.has_section("server")
    assert config["server"]["host"] == "example.com"


def test_load_config_without_section_header(tmp_path):
    """Keys before any [section] are tolerated and land in the default section."""
    path = _write_ini(
        tmp_path,
        """\
        key1 = value1
        key2 = value2
        """,
    )
    proc = FileConfigParser({})
    config = proc.load_config(path)
    assert config.defaults()["key1"] == "value1"


def test_read_single_dotted_key(tmp_path):
    path = _write_ini(
        tmp_path,
        """\
        [server]
        host = example.com
        """,
    )
    proc = FileConfigParser({})
    config = proc.load_config(path)
    assert proc.read_single(config, "server.host") == "example.com"


@pytest.mark.parametrize("bad_key", ["noseparator", "server."])
def test_read_single_rejects_malformed_key(tmp_path, bad_key):
    path = _write_ini(tmp_path, "[server]\nhost = example.com\n")
    proc = FileConfigParser({})
    config = proc.load_config(path)
    with pytest.raises(ProcessorError):
        proc.read_single(config, bad_key)


def test_read_single_missing_section_and_key(tmp_path):
    path = _write_ini(tmp_path, "[server]\nhost = example.com\n")
    proc = FileConfigParser({})
    config = proc.load_config(path)
    with pytest.raises(ProcessorError):
        proc.read_single(config, "missing.host")
    with pytest.raises(ProcessorError):
        proc.read_single(config, "server.missing")


def test_read_all_writes_prefixed_env_keys(tmp_path):
    path = _write_ini(
        tmp_path,
        """\
        [server]
        host = example.com
        port = 8080
        """,
    )
    proc = FileConfigParser({})
    config = proc.load_config(path)
    written = proc.read_all(config, "cfg")
    assert "cfg_server_host" in written
    assert proc.env["cfg_server_host"] == "example.com"
    assert proc.env["cfg_server_port"] == "8080"


def test_read_all_includes_default_section(tmp_path):
    path = _write_ini(
        tmp_path,
        """\
        globalkey = globalval
        [server]
        host = example.com
        """,
    )
    proc = FileConfigParser({})
    config = proc.load_config(path)
    proc.read_all(config, "cfg")
    assert proc.env[f"cfg_{DEFAULT_SECTION}_globalkey"] == "globalval"
