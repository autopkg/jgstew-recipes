#!/usr/local/autopkg/python
# Created 2022 by JGStew
"""See docstring for TextSubstitutionRegEx class"""

import re

from autopkglib import Processor, ProcessorError

__all__ = ["TextSubstitutionRegEx"]


class TextSubstitutionRegEx(Processor):
    """Performs regex-based substitution on an input string and stores the result in a named output variable."""

    input_variables = {
        "re_pattern": {
            "description": "Regular expression (Python) to match against text to substitute.",
            "required": True,
        },
        "re_substitution": {
            "description": "Text to substitute from the Regular Expression Match.",
            "required": True,
        },
        "input_string": {"description": "String to search", "required": True},
        "result_output_var_name": {
            "description": (
                "The name of the output variable that is returned "
                "by the match. If not specified then a default of "
                '"result_substitution" will be used.'
            ),
            "required": False,
            "default": "result_substitution",
        },
    }
    output_variables = {
        "result_output_var_name": {
            "description": (
                "Result of the regex substitution. Actual variable name depends on the result_output_var_name input, defaulting to 'result_substitution'."
            )
        }
    }

    description = __doc__

    def main(self):
        """Execution starts here."""
        re_pattern = self.env.get("re_pattern", None)
        re_substitution = self.env.get("re_substitution", None)
        input_string = self.env.get("input_string", None)
        result_output_var_name = self.env.get(
            "result_output_var_name", "result_substitution"
        )

        # re.sub(pattern, replace, string) is the equivalent of s/pattern/replace/ in SED
        result_substitution = re.sub(re_pattern, re_substitution, input_string)

        self.env[result_output_var_name] = result_substitution

        self.output_variables[result_output_var_name] = {
            "description": "the custom output variable"
        }


if __name__ == "__main__":
    PROCESSOR = TextSubstitutionRegEx()
    PROCESSOR.execute_shell()
