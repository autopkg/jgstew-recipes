#!/usr/local/autopkg/python
# Created 2026 by JGStew
"""See docstring for FileHtmlSelect class"""

# Extracts values or sub-sections from HTML with CSS selectors or XPath, so pages
# can be scraped structurally instead of with RegEx alone.
# Related:
# - https://github.com/autopkg/jgstew-recipes/blob/main/SharedProcessors/FileXmlXpath.py
# - https://lxml.de/cssselect.html

import os

import lxml.html
from autopkglib import (  # pylint: disable=import-error,wrong-import-position,unused-import
    Processor,
    ProcessorError,
)

__all__ = ["FileHtmlSelect"]


class FileHtmlSelect(Processor):  # pylint: disable=invalid-name
    """Selects elements from an HTML file or string with a CSS selector or XPath,
    returning matched text, an attribute value, or the elements' HTML markup. Uses
    lxml.html, which tolerates real-world (imperfect) HTML.
    """

    description = __doc__
    input_variables = {
        "html_input": {
            "required": True,
            "description": "Path to an HTML file, or an HTML string, to parse.",
        },
        "css_selector": {
            "required": False,
            "default": "",
            "description": (
                "CSS selector to match elements (e.g. `a.download`, `#version`)."
                " Provide either this or xpath."
            ),
        },
        "xpath": {
            "required": False,
            "default": "",
            "description": (
                "XPath expression to match, as an alternative to css_selector (e.g."
                " `//a[@class='download']/@href`)."
            ),
        },
        "attribute": {
            "required": False,
            "default": "",
            "description": (
                "If set, return this attribute of matched elements (e.g. `href`);"
                " otherwise the element's text content is returned."
            ),
        },
        "return_html": {
            "required": False,
            "default": False,
            "description": (
                "If true, return the matched element(s) as HTML markup instead of"
                " text. Ignored when attribute is set."
            ),
        },
        "return_all": {
            "required": False,
            "default": False,
            "description": (
                "If true, return a list of all matches; otherwise the first match"
                " (an empty string when there are none)."
            ),
        },
        "html_output_variable": {
            "required": False,
            "default": "html_result",
            "description": "Name of the env variable to store the result in.",
        },
    }
    output_variables = {
        "html_result": {
            "description": (
                "The selected result: the first match, or a list when return_all is"
                " true. Written to the env variable named by html_output_variable."
            ),
        },
    }

    def extract(self, match, attribute, return_html):
        """Turn one match (an element, or a string from XPath) into its value."""
        # XPath can return strings directly (e.g. `.../@href` or `text()`)
        if isinstance(match, str):
            return match
        if attribute:
            return match.get(attribute)
        if return_html:
            return lxml.html.tostring(match, encoding="unicode").strip()
        return match.text_content().strip()

    def main(self):
        """Execution starts here."""
        # Reading input_variables
        html_input = self.env.get("html_input")
        css_selector = self.env.get("css_selector", "")
        xpath = self.env.get("xpath", "")
        attribute = self.env.get("attribute", "")
        return_html = bool(self.env.get("return_html", False))
        return_all = bool(self.env.get("return_all", False))
        html_output_variable = self.env.get("html_output_variable", "html_result")

        if not css_selector and not xpath:
            raise ProcessorError("provide either css_selector or xpath")

        # parse from a file if it exists, otherwise treat the input as HTML text
        if os.path.isfile(html_input):
            with open(html_input, encoding="utf-8") as handle:
                tree = lxml.html.fromstring(handle.read())
        else:
            tree = lxml.html.fromstring(html_input)

        if css_selector:
            try:
                matches = tree.cssselect(css_selector)
            except ImportError as err:  # cssselect package not installed
                raise ProcessorError(
                    "CSS selectors require the 'cssselect' package to be installed"
                ) from err
        else:
            matches = tree.xpath(xpath)

        # drop Nones (e.g. a requested attribute that is absent) for clean results
        values = [self.extract(m, attribute, return_html) for m in matches]
        values = [value for value in values if value is not None]

        result = values if return_all else (values[0] if values else "")

        self.output(result, 3)
        self.env[html_output_variable] = result


if __name__ == "__main__":
    PROCESSOR = FileHtmlSelect()
    PROCESSOR.execute_shell()
