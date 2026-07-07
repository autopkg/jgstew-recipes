"""Unit tests for RecipeParentsInfo (static methods + main() behavior)."""

import os
import textwrap

import pytest
from RecipeParentsInfo import RecipeParentsInfo

# ---- recipe_type_from_path ------------------------------------------------


@pytest.mark.parametrize(
    "path, expected",
    [
        ("Foo.download.recipe.yaml", "download"),
        ("Foo.pkg.recipe.yaml", "pkg"),
        ("Foo.munki.recipe", "munki"),
        ("Vendor.Name.jss.recipe.yaml", "jss"),
        ("dir/sub/App.install.recipe.yaml", "install"),
        ("Foo.recipe", ""),  # untyped plist
        ("Foo.recipe.yaml", ""),  # untyped yaml
        ("Foo", ""),  # not a recipe filename at all
    ],
)
def test_recipe_type_from_path(path, expected):
    assert RecipeParentsInfo.recipe_type_from_path(path) == expected


# ---- processors_in_recipe -------------------------------------------------


def test_processors_in_recipe_collects_names():
    recipe = {
        "Process": [
            {"Processor": "URLDownloader"},
            {"Processor": "PkgCreator", "Arguments": {"x": 1}},
        ]
    }
    assert RecipeParentsInfo.processors_in_recipe(recipe) == [
        "URLDownloader",
        "PkgCreator",
    ]


@pytest.mark.parametrize(
    "recipe",
    [
        None,
        {},
        {"Process": None},
        {"Process": []},
        {"Process": ["not-a-dict", {"NoProcessorKey": 1}]},
    ],
)
def test_processors_in_recipe_handles_empty_and_malformed(recipe):
    assert RecipeParentsInfo.processors_in_recipe(recipe) == []


# ---- main(): a controlled 3-level chain -----------------------------------


def _write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(textwrap.dedent(text))


@pytest.fixture
def three_level_chain(tmp_path):
    """Create root <- mid <- leaf recipes and return (env, ids) for main().

    PARENT_RECIPES is nearest-first (immediate parent first), matching AutoPkg.
    """
    root = tmp_path / "Root.download.recipe.yaml"
    mid = tmp_path / "Mid.download.recipe.yaml"
    leaf = tmp_path / "Leaf.pkg.recipe.yaml"
    _write(
        root,
        """\
        Description: root
        Identifier: com.test.root
        Input:
          NAME: Root
          SHARED_KEY: root_val
          ROOT_ONLY: r
        Process: []
        """,
    )
    _write(
        mid,
        """\
        Description: mid
        Identifier: com.test.mid
        ParentRecipe: com.test.root
        Input:
          NAME: Mid
          SHARED_KEY: mid_val
          MID_ONLY: m
        Process: []
        """,
    )
    _write(
        leaf,
        """\
        Description: leaf
        Identifier: com.test.leaf
        ParentRecipe: com.test.mid
        Input:
          NAME: Leaf
          LEAF_ONLY: l
        Process:
          - Processor: com.github.jgstew.SharedProcessors/RecipeParentsInfo
        """,
    )
    cache = tmp_path / "cache"
    env = {
        "RECIPE_PATH": str(leaf),
        "PARENT_RECIPES": [str(mid), str(root)],  # nearest-first
        "CACHE_DIR": str(cache),
    }
    return env, str(cache)


def test_main_identifiers_and_types_and_cache(three_level_chain, make_processor):
    env, cache = three_level_chain
    proc = make_processor(RecipeParentsInfo, env)
    proc.main()

    assert proc.env["parent_recipe_identifiers"] == ["com.test.mid", "com.test.root"]
    assert proc.env["parent_recipe_count"] == 2
    assert proc.env["parent_recipe_first_identifier"] == "com.test.mid"
    assert proc.env["parent_recipe_types"] == ["download", "download"]
    assert proc.env["recipe_chain_terminal_type"] == "pkg"
    assert proc.env["parent_recipe_cache_dirs"] == [
        os.path.join(cache, "com.test.mid"),
        os.path.join(cache, "com.test.root"),
    ]
    assert proc.env["parent_recipe_first_cache_dir"] == os.path.join(
        cache, "com.test.mid"
    )


def test_main_chain_processors_union(three_level_chain, make_processor):
    env, _cache = three_level_chain
    proc = make_processor(RecipeParentsInfo, env)
    proc.main()
    # parents have empty Process; the leaf contributes the one processor
    assert proc.env["chain_processors"] == [
        "com.github.jgstew.SharedProcessors/RecipeParentsInfo"
    ]
    assert proc.env["chain_processor_count"] == 1


def test_main_no_parents(make_processor):
    proc = make_processor(RecipeParentsInfo, {})
    proc.main()
    assert proc.env["parent_recipe_identifiers"] == []
    assert proc.env["parent_recipe_count"] == 0
    assert proc.env["parent_recipe_cache_dirs"] == []
    assert proc.env["parent_recipe_first_identifier"] == ""
    assert proc.env["parent_recipe_first_cache_dir"] == ""
    assert proc.env["chain_processors"] == []
