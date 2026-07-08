#!/usr/local/autopkg/python
# Created 2026 by JGStew
"""See docstring for FolderListFiles class"""

import fnmatch
import os

from autopkglib import (  # pylint: disable=import-error,wrong-import-position,unused-import
    Processor,
    ProcessorError,
)

__all__ = ["FolderListFiles"]


class FolderListFiles(Processor):  # pylint: disable=invalid-name
    """Lists the files within a folder.

    Returns the entries of `folder_path` as both full paths and bare filenames.
    By default it lists only files in the immediate folder; set `recursive` to
    walk subfolders, `include_dirs` to also include directories, and `pattern`
    to keep only names matching a glob (e.g. `*.pkg`). Results are sorted unless
    `sort_results` is disabled.
    """

    description = __doc__
    input_variables = {
        "folder_path": {
            "required": True,
            "description": "Path to the folder whose files should be listed.",
        },
        "recursive": {
            "required": False,
            "default": False,
            "description": "If True, walk subfolders too. Default: False.",
        },
        "include_dirs": {
            "required": False,
            "default": False,
            "description": (
                "If True, include directories in the listing as well as files. "
                "Default: False (files only)."
            ),
        },
        "pattern": {
            "required": False,
            "default": "",
            "description": (
                "Optional glob pattern (fnmatch) applied to each filename, e.g. "
                "'*.pkg'. Empty string (default) keeps every entry."
            ),
        },
        "sort_results": {
            "required": False,
            "default": True,
            "description": "If True, sort the results by path. Default: True.",
        },
    }
    output_variables = {
        "folder_file_list": {
            "description": "List of full paths to the matching entries.",
        },
        "folder_file_names": {
            "description": "List of bare filenames (basenames) of the entries.",
        },
        "folder_file_count": {
            "description": "Number of entries found (integer).",
        },
        "folder_file_list_string": {
            "description": (
                "The full paths joined with newlines as a single string, usable "
                "in recipe '%variable%' substitution."
            ),
        },
    }

    def main(self):
        """Execution starts here."""
        folder_path = self.env.get("folder_path")
        recursive = bool(self.env.get("recursive", False))
        include_dirs = bool(self.env.get("include_dirs", False))
        pattern = self.env.get("pattern", "")
        sort_results = bool(self.env.get("sort_results", True))

        if not folder_path or not os.path.isdir(folder_path):
            raise ProcessorError(f"folder_path is not a directory: {folder_path}")

        paths = []
        if recursive:
            for root, dirs, files in os.walk(folder_path):
                if include_dirs:
                    paths.extend(os.path.join(root, name) for name in dirs)
                paths.extend(os.path.join(root, name) for name in files)
        else:
            for entry in os.scandir(folder_path):
                if entry.is_dir() and not include_dirs:
                    continue
                paths.append(entry.path)

        if pattern:
            paths = [p for p in paths if fnmatch.fnmatch(os.path.basename(p), pattern)]

        if sort_results:
            paths.sort()

        names = [os.path.basename(p) for p in paths]

        self.env["folder_file_list"] = paths
        self.env["folder_file_names"] = names
        self.env["folder_file_count"] = len(paths)
        self.env["folder_file_list_string"] = "\n".join(paths)

        self.output(f"found {len(paths)} item(s) in {folder_path}")
        self.output(f"items: {names}", 2)


if __name__ == "__main__":
    PROCESSOR = FolderListFiles()
    PROCESSOR.execute_shell()
