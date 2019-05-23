from abcmd import CommandFormatter

import pytest


@pytest.mark.parametrize(
    "template, config, expected",
    [
        ("cmd {option0}", {"option0": "test_option"}, "cmd test_option"),
        # list parameter must be separated with spaces
        (
            "command {option0}::{option1} {option2}",
            {
                "option0": "test_option",
                "option1": "test_option1",
                "option2": ["path0", "path1"],
            },
            "command test_option::test_option1 path0 path1",
        ),
        # boolean parameter must exist if true
        (
            "command {option0}::{option1} {option2} {verbose}",
            {
                "option0": "test_option",
                "option1": "test_option1",
                "option2": ["test_path"],
                "verbose": True,
            },
            "command test_option::test_option1 test_path --verbose",
        ),
        # boolean parameter has right name
        (
            "command {option0}::{option1} {option2} {bool_option}",
            {
                "option0": "test_option",
                "option1": "test_option1",
                "option2": ["test_path"],
                "bool_option": True,
            },
            "command test_option::test_option1 test_path --bool-option",
        ),
        # boolean parameter must not exist if false
        (
            "command {option0}::{option1} {option2} {verbose}",
            {
                "option0": "test_option",
                "option1": "test_option1",
                "option2": ["test_path"],
                "verbose": False,
            },
            "command test_option::test_option1 test_path",
        ),
        # optional non boolean parameter
        (
            "init {option0} {-e option1}",
            {"option0": "test_option", "option1": "keyfile"},
            "init test_option -e keyfile",
        ),
        # positional list parameter
        ("command {args}", {"args": [1, 2, 3, 4]}, "command 1 2 3 4"),
        # optional non boolean list parameter
        (
            "command {option0}::{option1} {option2} {-e list_option}",
            {
                "option0": "test_option",
                "option1": "test_option1",
                "option2": ["test_path"],
                "list_option": ["/list_option0", "/list_option1"],
            },
            "command test_option::test_option1 test_path -e /list_option0 -e /list_option1",
        ),
        # optional non boolean empty list parameter
        (
            "command {option0}::{option1} {option2} {-e list_option}",
            {
                "option0": "test_option",
                "option1": "test_option1",
                "option2": ["test_path"],
                "list_option": [],
            },
            "command test_option::test_option1 test_path",
        ),
        # optional non boolean empty string parameter
        (
            "command {option0}::{option1} {option2} {-c empty_option}",
            {
                "option0": "test_option",
                "option1": "test_option1",
                "option2": ["test_path"],
                "empty_option": "",
            },
            "command test_option::test_option1 test_path",
        ),
        # handle int parameters
        ("command {-h keep_hourly}", {"keep_hourly": 1}, "command -h 1"),
        # handle "0" as a non falsy value
        ("command {-o arg}", {"arg": 0}, "command -o 0"),
        # long parameters
        ("command {--long long_option}", {"long_option": 1}, "command --long 1"),
        # long parameters list
        (
            "command {--long long_option}",
            {"long_option": [1, 2, 3]},
            "command --long 1 --long 2 --long 3",
        ),
        # ingore extra args in format field
        ("command {-o option option2}", {"option": "opt"}, "command -o opt"),
        # positional argument
        ("command {ARG}", {"ARG": 10}, "command 10"),
    ],
)
def test_CommandFormatter_format(config, template, expected):
    formatter = CommandFormatter(config=config)
    assert formatter(template) == expected


def test_CommandFormatter_caches_commands():
    formatter = CommandFormatter({"OPTION": "option"})
    first_formatted = formatter("command {-o OPTION}")
    second_formatted = formatter("command {-o OPTION}")

    assert first_formatted is second_formatted


def test_CommandFormatter_on_config_change():
    formatter = CommandFormatter({"OPTION": "option"})
    assert formatter("command {OPTION}") == "command option"

    formatter.config["OPTION"] = "changed"
    assert formatter("command {OPTION}") == "command changed"
