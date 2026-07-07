#!/usr/local/autopkg/python
# Created 2026 by JGStew
"""See docstring for RecipeParentsInfo class"""

import os.path

from autopkglib import (  # pylint: disable=import-error,wrong-import-position,unused-import
    Processor,
    ProcessorError,
    get_identifier,
    recipe_from_file,
)

__all__ = ["RecipeParentsInfo"]


class RecipeParentsInfo(Processor):
    """Reads the recipe identifier from each parent recipe of the running recipe.

    AutoPkg exposes the parent recipe chain as the `PARENT_RECIPES` env variable
    (a list of file paths). This processor loads each of those files, extracts
    its recipe identifier, derives that identifier's cache folder path, and
    determines each recipe's type -- in the same (parent-to-child) order. It also
    collects the union of processors used across the whole chain.
    """

    description = __doc__
    input_variables = {}
    output_variables = {
        "parent_recipe_identifiers": {
            "description": (
                "List of recipe identifiers, one per parent recipe, in the same "
                "order as PARENT_RECIPES (empty list if there are no parents)."
            )
        },
        "parent_recipes_info": {
            "description": (
                "List of dicts, one per parent recipe, each with 'path', "
                "'identifier', and 'cache_dir' keys."
            )
        },
        "parent_recipe_count": {
            "description": "Number of parent recipes found (integer).",
        },
        "parent_recipe_identifiers_string": {
            "description": (
                "The parent recipe identifiers joined with ', ' as a single "
                "string. Unlike the list output, this can be used in recipe "
                "'%variable%' substitution (empty string if there are no parents)."
            )
        },
        "parent_recipe_first_identifier": {
            "description": (
                "The identifier of the first (top-most) parent recipe, or an "
                "empty string if there are no parents."
            )
        },
        "parent_recipe_cache_dirs": {
            "description": (
                "List of cache folder paths (CACHE_DIR/<identifier>), one per "
                "parent recipe that has an identifier, in the same order."
            )
        },
        "parent_recipe_first_cache_dir": {
            "description": (
                "The cache folder path of the first (top-most) parent recipe, "
                "or an empty string if there are no parents."
            )
        },
        "parent_recipe_types": {
            "description": (
                "List of recipe types (the token before '.recipe' in the "
                "filename, e.g. 'download', 'pkg', 'munki'), one per parent "
                "recipe, in order. An empty string for a recipe with no type."
            )
        },
        "recipe_chain_terminal_type": {
            "description": (
                "The recipe type of the running (most-derived) recipe -- i.e. "
                "what the whole chain ultimately produces. Empty string if the "
                "running recipe has no type."
            )
        },
        "chain_processors": {
            "description": (
                "Sorted list of the unique processor names used across the "
                "entire chain (all parents plus the running recipe)."
            )
        },
        "chain_processors_string": {
            "description": (
                "chain_processors joined with ', ' as a single string, usable "
                "in recipe '%variable%' substitution."
            )
        },
        "chain_processor_count": {
            "description": "Number of unique processors used across the chain.",
        },
    }

    @staticmethod
    def recipe_type_from_path(recipe_path):
        """Return the recipe type token from a recipe filename.

        e.g. 'Foo.download.recipe.yaml' -> 'download', 'Foo.recipe' -> ''.
        This is a filename heuristic (the token immediately before '.recipe');
        a product name containing a '.' but no type could be misread.
        """
        name = os.path.basename(recipe_path)
        if name.endswith(".yaml"):
            name = name[: -len(".yaml")]
        if name.endswith(".recipe"):
            name = name[: -len(".recipe")]
        if "." in name:
            return name.rsplit(".", 1)[1]
        return ""

    @staticmethod
    def processors_in_recipe(recipe_dict):
        """Return the list of processor names in a recipe dict's Process."""
        processors = []
        if isinstance(recipe_dict, dict):
            for step in recipe_dict.get("Process", []) or []:
                if isinstance(step, dict) and step.get("Processor"):
                    processors.append(step["Processor"])
        return processors

    def main(self):
        """Execution starts here."""
        parent_recipes = self.env.get("PARENT_RECIPES", []) or []
        # example: ['Test-Recipes/AssertInputContainsString.test.recipe.yaml']
        self.output(parent_recipes, 3)

        # AutoPkg stores each recipe's cache under CACHE_DIR/<identifier>, using
        # the same default as autopkglib when CACHE_DIR is unset:
        cache_dir = self.env.get("CACHE_DIR") or os.path.expanduser(
            "~/Library/AutoPkg/Cache"
        )

        identifiers = []
        cache_dirs = []
        types = []
        info = []
        chain_processors = set()
        for recipe_path in parent_recipes:
            recipe_dict = recipe_from_file(recipe_path)
            if recipe_dict is None:
                self.output(f"WARNING: could not read parent recipe: {recipe_path}", 0)
                identifier = None
            else:
                identifier = get_identifier(recipe_dict)
                if not identifier:
                    self.output(
                        f"WARNING: no identifier in parent recipe: {recipe_path}", 0
                    )
                chain_processors.update(self.processors_in_recipe(recipe_dict))

            recipe_cache_dir = (
                os.path.join(cache_dir, identifier) if identifier else None
            )
            recipe_type = self.recipe_type_from_path(recipe_path)

            info.append(
                {
                    "path": recipe_path,
                    "identifier": identifier,
                    "cache_dir": recipe_cache_dir,
                    "type": recipe_type,
                }
            )
            types.append(recipe_type)
            if identifier:
                identifiers.append(identifier)
                cache_dirs.append(recipe_cache_dir)
            self.output(
                f"parent recipe: {identifier} ({recipe_type}) -> {recipe_cache_dir}"
            )

        # the running recipe is the terminal of the chain; include its processors
        # in the union and use its type as the chain's terminal type:
        current_recipe_path = self.env.get("RECIPE_PATH", "")
        if current_recipe_path:
            chain_processors.update(
                self.processors_in_recipe(recipe_from_file(current_recipe_path))
            )
        terminal_type = self.recipe_type_from_path(current_recipe_path)

        chain_processors = sorted(chain_processors)

        self.env["parent_recipe_identifiers"] = identifiers
        self.env["parent_recipes_info"] = info
        self.env["parent_recipe_count"] = len(parent_recipes)
        self.env["parent_recipe_cache_dirs"] = cache_dirs
        self.env["parent_recipe_types"] = types
        self.env["recipe_chain_terminal_type"] = terminal_type
        self.env["chain_processors"] = chain_processors
        self.env["chain_processor_count"] = len(chain_processors)
        # string outputs so the results are usable in recipe '%variable%'
        # substitution (AutoPkg can only substitute string values):
        self.env["parent_recipe_identifiers_string"] = ", ".join(identifiers)
        self.env["parent_recipe_first_identifier"] = (
            identifiers[0] if identifiers else ""
        )
        self.env["parent_recipe_first_cache_dir"] = cache_dirs[0] if cache_dirs else ""
        self.env["chain_processors_string"] = ", ".join(chain_processors)

        self.output(f"found {len(identifiers)} parent recipe identifier(s)")
        self.output(f"chain terminal type: {terminal_type}")
        self.output(f"chain processors: {chain_processors}")


if __name__ == "__main__":
    PROCESSOR = RecipeParentsInfo()
    PROCESSOR.execute_shell()
