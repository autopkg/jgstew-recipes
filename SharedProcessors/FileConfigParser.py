#!/usr/local/autopkg/python
# Created 2026 by JGStew
"""See docstring for FileConfigParser class"""

# Related:
# - https://github.com/autopkg/jgstew-recipes/blob/main/SharedProcessors/FileYamlRead.py
# - https://docs.python.org/3/library/configparser.html

import configparser
import os
import re

from autopkglib import (  # pylint: disable=import-error,wrong-import-position,unused-import
    Processor,
    ProcessorError,
)

__all__ = ["FileConfigParser"]

# the section name used for keys with no explicit section, and in dotted lookups
DEFAULT_SECTION = "default"


class FileConfigParser(Processor):  # pylint: disable=invalid-name
    """Reads an INI-style config file with Python's configparser. With no
    config_key it loads the whole file into the environment as
    `<prefix>_<section>_<key>` variables; with a dotted `config_key`
    (`section.key`, where `default.key` reads the default section) it reads a
    single value into the env variable named by config_output_variable.
    """

    description = __doc__
    input_variables = {
        "config_file": {
            "required": True,
            "description": "Path to the INI-style config file to read.",
        },
        "config_key": {
            "required": False,
            "default": "",
            "description": (
                "Dotted `section.key` to read a single value (e.g. `server.host`;"
                " `default.key` reads the default section). If empty, the whole"
                " file is read into the environment."
            ),
        },
        "config_output_variable": {
            "required": False,
            "default": "config",
            "description": (
                "Name of the env variable to store the single value in (only used"
                " when config_key is set). Default: `config`."
            ),
        },
        "config_prefix": {
            "required": False,
            "default": "",
            "description": (
                "Prefix for the env keys when reading the whole file. If empty, the"
                " config file's base name (without extension) is used."
            ),
        },
    }
    output_variables = {
        "config": {
            "description": (
                "When config_key is set, the value is written to the env variable"
                " named by config_output_variable (default `config`). When reading"
                " the whole file, values are written as `<prefix>_<section>_<key>`."
            ),
        },
    }

    @staticmethod
    def env_safe(text):
        """Sanitize a name to word characters so it is safe as an env key."""
        return re.sub(r"\W+", "_", text)

    def load_config(self, config_file):
        """Parse config_file, tolerating a file with no section header."""
        config = configparser.ConfigParser(
            default_section=DEFAULT_SECTION, interpolation=None
        )
        with open(config_file, encoding="utf-8") as handle:
            text = handle.read()
        try:
            config.read_string(text, source=config_file)
        except configparser.MissingSectionHeaderError:
            # keys before any [section] -> treat them as the default section
            config = configparser.ConfigParser(
                default_section=DEFAULT_SECTION, interpolation=None
            )
            config.read_string(f"[{DEFAULT_SECTION}]\n{text}", source=config_file)
        return config

    def read_single(self, config, config_key):
        """Return the value at a dotted `section.key`, or raise ProcessorError."""
        section_name, separator, key_name = config_key.partition(".")
        if not separator or not key_name:
            raise ProcessorError(
                f"config_key '{config_key}' must be in 'section.key' form"
            )
        if section_name.lower() == DEFAULT_SECTION:
            section = config[config.default_section]
        elif config.has_section(section_name):
            section = config[section_name]
        else:
            raise ProcessorError(f"section '{section_name}' not found in config")
        if key_name not in section:
            raise ProcessorError(
                f"key '{key_name}' not found in section '{section_name}'"
            )
        return section[key_name]

    def read_all(self, config, prefix):
        """Write every section/key into the environment; return the keys written."""
        written = []
        defaults = config.defaults()

        def store(section, key, value):
            env_key = (
                f"{self.env_safe(prefix)}_{self.env_safe(section)}_{self.env_safe(key)}"
            )
            self.env[env_key] = value
            written.append(env_key)

        # the default section
        for key, value in defaults.items():
            store(DEFAULT_SECTION, key, value)

        # each real section's own keys (skip values purely inherited from default)
        for section_name in config.sections():
            for key in config[section_name]:
                value = config[section_name][key]
                if key in defaults and defaults[key] == value:
                    continue
                store(section_name, key, value)

        return written

    def main(self):
        """Execution starts here."""
        # Reading input_variables
        config_file = self.env.get("config_file")
        config_key = self.env.get("config_key", "")
        config_output_variable = self.env.get("config_output_variable", "config")
        config_prefix = self.env.get("config_prefix", "")

        if not config_file or not os.path.isfile(config_file):
            raise ProcessorError(f"config_file not found: {config_file}")

        config = self.load_config(config_file)

        if config_key:
            # single-value mode
            value = self.read_single(config, config_key)
            self.env[config_output_variable] = value
            self.output(f"{config_output_variable} = {value}", 2)
        else:
            # read-the-whole-file-into-env mode
            prefix = config_prefix or os.path.splitext(os.path.basename(config_file))[0]
            written = self.read_all(config, prefix)
            self.output(f"Loaded {len(written)} config value(s) into the environment")
            self.output(", ".join(written), 3)


if __name__ == "__main__":
    PROCESSOR = FileConfigParser()
    PROCESSOR.execute_shell()
