import os
import re
import json
from pathlib import Path
from datetime import datetime
import logging

# Optional dependency for HTML stubs:
#   pip install beautifulsoup4
try:
    from bs4 import BeautifulSoup, Comment
except ImportError:
    BeautifulSoup = None
    Comment = None


# Dummy app with logger
class DummyApp:
    pass


logging.basicConfig(level=logging.INFO)
app = DummyApp()
app.logger = logging.getLogger("code_aggregator")

# Stub compaction constants
JSON_TRUNCATE_LENGTH = 400
HTML_TRUNCATE_ITEMS = 2


class CodeAggregator:
    def __init__(
        self,
        root_dir=".",
        output_filename="project_directory_full_code.txt",
        compaction_level="whitespace",  # 'none', 'whitespace', 'stubs'
        comments=False,
        include_dirtree=True,
        include_description=True,
        included_extensions=None,
        exclude_files=None,
        include_files=None,
        ignore_dirs=None,
        description_text="",
        print_only=None,
        split_at=8400,
        max_lines_per_file=None,
        truncate_lines=None,
    ):
        self.root_dir = Path(root_dir)
        self.output_filename = output_filename
        self.compaction_level = compaction_level
        self.comments = comments
        self.include_dirtree = include_dirtree
        self.include_description = include_description
        self.description_text = description_text

        # split_at: 0/None => no split
        if split_at is None:
            self.split_at = 0
        else:
            try:
                self.split_at = int(split_at)
            except Exception:
                self.split_at = 0
        if self.split_at < 0:
            self.split_at = 0

        self.max_lines_per_file = (
            int(max_lines_per_file) if max_lines_per_file else None
        )
        self.truncate_lines = int(truncate_lines) if truncate_lines else None

        # Normalize extensions (case-insensitive, starts with ".")
        self.included_extensions = set(
            (ext if ext.startswith(".") else f".{ext}").lower()
            for ext in (included_extensions or [])
        )

        # Warn if HTML stubs requested but bs4 missing
        if (
            self.compaction_level == "stubs"
            and ".html" in self.included_extensions
            and BeautifulSoup is None
        ):
            app.logger.warning(
                "HTML stubs enabled, but 'beautifulsoup4' not installed. "
                "HTML files won't be compacted."
            )

        # Normalize filename filters (case-insensitive)
        self.exclude_files = set()
        if exclude_files:
            for file_entry in exclude_files:
                filename, _ = self._parse_file_entry(file_entry)
                self.exclude_files.add(filename.lower())

        self.include_files = []
        self.include_files_lower = set()
        self.file_line_ranges = {}

        if include_files:
            for file_entry in include_files:
                filename, range_info = self._parse_file_entry(file_entry)
                self.include_files.append(filename)
                self.include_files_lower.add(filename.lower())
                if range_info:
                    self.file_line_ranges[filename.lower()] = range_info

        self.print_only = []
        self.print_only_lower = set()
        if print_only:
            for file_entry in print_only:
                filename, range_info = self._parse_file_entry(file_entry)
                self.print_only.append(filename)
                self.print_only_lower.add(filename.lower())
                if range_info:
                    self.file_line_ranges[filename.lower()] = range_info

        self.ignore_dirs = set(ignore_dirs) if ignore_dirs else set()

        app.logger.info(
            "Initialized CodeAggregator with: "
            f"compaction_level={self.compaction_level}, "
            f"include_dirtree={self.include_dirtree}, "
            f"include_description={self.include_description}, "
            f"included_extensions={self.included_extensions or '<ALL>'}, "
            f"split_at={self.split_at or 'OFF'}, "
            f"max_lines_per_file={self.max_lines_per_file or '∞'}, "
            f"truncate_lines={self.truncate_lines or '—'}"
        )

    def _parse_file_entry(self, file_entry):
        """Parse 'filename|start-end' or 'filename|N'."""
        if "|" not in file_entry:
            return file_entry, None

        filename, range_str = file_entry.split("|", 1)

        if "-" in range_str:
            try:
                start, end = map(int, range_str.split("-", 1))
                return filename, (start, end)
            except ValueError:
                app.logger.warning(f"Bad range in '{file_entry}'")
                return file_entry, None

        try:
            line_limit = int(range_str)
            return filename, (1, line_limit)
        except ValueError:
            app.logger.warning(f"Bad line limit in '{file_entry}'")
            return file_entry, None

    def should_ignore_directory(self, file_path: Path) -> bool:
        for d in self.ignore_dirs:
            d_path = (self.root_dir / d).resolve()
            try:
                if d_path in file_path.resolve().parents:
                    return True
            except Exception as e:
                app.logger.warning(f"Resolve failed: {file_path} due to {e}")
        return False

    def _truncate_by_lines(self, text: str, limit: int, note: str) -> str:
        """Truncate to 'limit' lines."""
        if limit is None or limit <= 0:
            return text
        lines = text.splitlines(keepends=True)
        if len(lines) <= limit:
            return text
        omitted = len(lines) - limit
        suffix = f"\n... (truncated, {omitted} more lines omitted; {note})"
        return "".join(lines[:limit]) + suffix

    def append_file_content(self, content_list, file_path: Path):
        """Read file, compact, and append."""
        line_range = self.file_line_ranges.get(file_path.name.lower())

        try:
            all_lines = file_path.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines(keepends=True)

            # Apply per-file slice
            if line_range:
                start, end = line_range
                snippet = all_lines[start - 1 : end]
                file_content = "".join(snippet)
                range_info = f" (lines {start}-{end})"
                if end < len(all_lines):
                    omitted = len(all_lines) - end
                    file_content += f"\n... (remaining {omitted} lines omitted)"
            else:
                file_content = "".join(all_lines)
                range_info = ""

            # Early hard cap
            if self.max_lines_per_file:
                file_content = self._truncate_by_lines(
                    file_content,
                    self.max_lines_per_file,
                    note="early cap: max_lines_per_file",
                )

            header = f"\n[-] This file: {file_path}{range_info} | Contents:\n"

        except Exception as e:
            header = f"\n[-] This file: {file_path} | Contents:\n"
            file_content = f"Error reading file: {e}\n"
            content_list.append(header + file_content + "\n" + "=" * 80 + "\n")
            return

        # Compaction / comment removal
        if self.compaction_level == "stubs":
            file_content = self._create_stubs(file_content, file_path.suffix.lower())

        if not self.comments:
            file_content = self.remove_comments(file_content, file_path.suffix.lower())

        if self.compaction_level == "whitespace":
            file_content = self._compact_whitespace(file_content)

        # Post-mode truncation
        if self.compaction_level in ("none", "whitespace") and self.truncate_lines:
            file_content = self._truncate_by_lines(
                file_content,
                self.truncate_lines,
                note=f"post cap: truncate_lines={self.truncate_lines}",
            )

        content_list.append(header + file_content + "\n" + "=" * 80 + "\n")

    def _compact_whitespace(self, content: str) -> str:
        return "\n".join(line.rstrip() for line in content.splitlines() if line.strip())

    def remove_comments(self, content: str, extension: str) -> str:
        if extension == ".py":
            return "\n".join(
                line
                for line in content.splitlines()
                if not line.lstrip().startswith("#")
            )

        if extension == ".js":
            no_block = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
            return "\n".join(line.split("//", 1)[0] for line in no_block.splitlines())

        if extension == ".html":
            return content  # keep as-is for now

        if extension == ".css":
            return re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)

        temp = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
        return "\n".join(
            line.split("#", 1)[0].split("//", 1)[0] for line in temp.splitlines()
        )

    def _create_stubs(self, content: str, extension: str) -> str:
        if extension == ".py":
            return self._create_stubs_py(content)
        if extension == ".js":
            return self._create_stubs_js(content)
        if extension == ".json":
            return self._create_stubs_json(content)
        if extension == ".html":
            return self._create_stubs_html(content)
        return content

    def _truncate_json_values(self, data):
        if isinstance(data, dict):
            return {k: self._truncate_json_values(v) for k, v in data.items()}
        if isinstance(data, list):
            return [self._truncate_json_values(item) for item in data]
        if isinstance(data, str) and len(data) > JSON_TRUNCATE_LENGTH:
            return data[:JSON_TRUNCATE_LENGTH] + "..."
        return data

    def _create_stubs_json(self, content: str) -> str:
        try:
            data = json.loads(content)

            if isinstance(data, list) and len(data) > 1:
                first_item = self._truncate_json_values(data[0])
                output_str = json.dumps([first_item], indent=2)
                output_str = (
                    output_str[:-2]
                    + f",\n  // ... and {len(data) - 1} more items\n]"
                )
                return output_str

            truncated_data = self._truncate_json_values(data)
            return json.dumps(truncated_data, indent=2)

        except json.JSONDecodeError:
            app.logger.warning("JSON parse failed, returning raw content.")
            return content

    def _create_stubs_html(self, content: str) -> str:
        if BeautifulSoup is None:
            return content

        try:
            soup = BeautifulSoup(content, "html.parser")

            for tag in soup.find_all(["script", "style"]):
                if tag.string:
                    tag.string = f"// ... Inline {tag.name} omitted ..."

            for parent_tag_name, child_tag_name in [
                ("ul", "li"),
                ("ol", "li"),
                ("tbody", "tr"),
                ("select", "option"),
            ]:
                for parent in soup.find_all(parent_tag_name):
                    children = parent.find_all(child_tag_name, recursive=False)
                    if len(children) > HTML_TRUNCATE_ITEMS:
                        for i in range(HTML_TRUNCATE_ITEMS, len(children)):
                            children[i].decompose()
                        parent.append(
                            Comment(
                                f" ... {len(children) - HTML_TRUNCATE_ITEMS} "
                                f"more '{child_tag_name}' omitted ... "
                            )
                        )

            for tag_name in ["nav", "header", "footer", "aside"]:
                for tag in soup.find_all(tag_name):
                    tag.clear()
                    tag.append(Comment(f" ... Full '{tag_name}' omitted ... "))

            return soup.prettify()

        except Exception as e:
            app.logger.warning(f"HTML parse failed ({e}), returning raw.")
            return content

    def _create_stubs_py(self, content: str) -> str:
        lines = content.splitlines()
        output, block_stack = [], []

        for line in lines:
            stripped = line.lstrip()

            if not stripped:
                if not block_stack:
                    output.append(line)
                continue

            indentation = len(line) - len(stripped)

            while block_stack and indentation <= block_stack[-1]:
                block_stack.pop()

            if not block_stack:
                output.append(line)
                if stripped.startswith(("def ", "class ", "async def ")):
                    block_stack.append(indentation)
                    output.append(
                        f"{' ' * (indentation + 4)}... # Body omitted"
                    )

        return "\n".join(output)

    def _create_stubs_js(self, content: str) -> str:
        lines = content.splitlines(keepends=True)
        output = []

        sig = re.compile(
            r"^(\s*)(?:class\s+\w+|function\s*\w*\s*\(.*\)\s*\{|"
            r"(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\(.*\)\s*=>\s*\{|"
            r"\w+\s*:\s*(?:async\s*)?function\s*\(.*\)\s*\{|"
            r"(?:get|set)\s+\w+\(.*\)\s*\{|"
            r"(?:async\s+)?\w+\s*\(.*\)\s*\{)"
        )

        in_block, brace_level, indent = False, 0, ""

        for line in lines:
            if not in_block:
                m = sig.match(line)
                if m:
                    output.append(line)
                    indent = m.group(1) or ""
                    brace_level = line.count("{") - line.count("}")
                    if brace_level > 0:
                        in_block = True
                        output.append(f"{indent}  // ... Body omitted\n")
                else:
                    output.append(line)
            else:
                brace_level += line.count("{")
                brace_level -= line.count("}")
                if brace_level <= 0:
                    in_block = False
                    output.append(f"{indent}}}\n")

        return "".join(output)

    def _generate_dirtree(self) -> str:
        """Generate directory tree text."""
        app.logger.info("Generating directory tree...")
        tree_lines = [f"{self.root_dir.name}/"]
        dir_count = 0
        file_count = 0

        def recurse_path(directory: Path, prefix: str = ""):
            nonlocal dir_count, file_count
            items = []

            try:
                for item in directory.iterdir():
                    if item.name in self.ignore_dirs:
                        continue
                    if item.is_file() and (
                        item.name.lower() in self.exclude_files
                        or item.stem.lower() in self.exclude_files
                    ):
                        continue
                    items.append(item)
            except PermissionError:
                tree_lines.append(f"{prefix}└── [Permission Denied]")
                return

            # dirs first, then files
            items.sort(key=lambda x: (x.is_file(), x.name.lower()))

            pointers = ["├── "] * (len(items) - 1) + ["└── "]
            for pointer, path in zip(pointers, items):
                tree_lines.append(f"{prefix}{pointer}{path.name}")
                if path.is_dir():
                    dir_count += 1
                    extension = "│   " if pointer == "├── " else "    "
                    recurse_path(path, prefix=prefix + extension)
                else:
                    file_count += 1

        recurse_path(self.root_dir)
        tree_lines.append(f"\n{dir_count} directories, {file_count} files")
        return "\n".join(tree_lines)

    def aggregate_files(self):
        contents = []
        current_file = Path(__file__).resolve()

        # print_only short-circuit
        if self.print_only:
            app.logger.info("print_only enabled.")
            for name in self.print_only:
                for fp in self.root_dir.rglob(name):
                    if fp.is_file() and not self.should_ignore_directory(fp.resolve()):
                        app.logger.info(f"Printing file: {fp}")
                        self.append_file_content(contents, fp)
            return contents

        processed_files = set()

        for file in sorted(self.root_dir.rglob("*")):
            if (
                not file.is_file()
                or file.resolve() == current_file
                or self.should_ignore_directory(file.resolve())
            ):
                continue

            name_lower = file.name.lower()
            stem_lower = file.stem.lower()
            ext_lower = file.suffix.lower()

            is_explicitly_included = name_lower in self.include_files_lower
            is_excluded = (
                name_lower in self.exclude_files or stem_lower in self.exclude_files
            )

            if self.included_extensions:
                should_include = (ext_lower in self.included_extensions) or is_explicitly_included
            else:
                should_include = True

            if should_include and not is_excluded:
                app.logger.info(f"Including file: {file}")
                self.append_file_content(contents, file)
                processed_files.add(name_lower)

        # Force-include any include_files not processed
        for name in self.include_files:
            name_lower = name.lower()
            if name_lower in processed_files:
                continue
            for fp in self.root_dir.rglob("*"):
                if (
                    fp.is_file()
                    and fp.name.lower() == name_lower
                    and not self.should_ignore_directory(fp.resolve())
                ):
                    app.logger.info(f"Force-including file: {fp}")
                    self.append_file_content(contents, fp)
                    processed_files.add(name_lower)

        return contents

    def aggregate(self):
        header_parts = []
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header_parts.append(f"Aggregated on: {ts}\n{'=' * 80}\n")

        if self.include_description and self.description_text:
            header_parts.append(
                f"Description:\n{self.description_text}\n{'=' * 80}\n"
            )

        if self.include_dirtree:
            tree_str = self._generate_dirtree()
            header_parts.append(
                f"Project Directory Tree:\n{tree_str}\n{'=' * 80}\n"
            )

        contents = self.aggregate_files()
        contents.insert(0, "".join(header_parts))

        base, ext = os.path.splitext(self.output_filename)
        if not ext:
            ext = ".txt"

        # No split
        if self.split_at <= 0:
            target = f"{base}{ext}"
            Path(target).write_text("".join(contents), encoding="utf-8")
            app.logger.info(f"Aggregation complete: {target}")
            return

        # Split into chunks
        idx, line_count, buf = 1, 0, []

        def flush():
            nonlocal idx, buf, line_count
            if not buf:
                return
            out = f"{base}_{idx}{ext}"
            Path(out).write_text("".join(buf), encoding="utf-8")
            app.logger.info(f"Wrote {line_count} lines to {out}")
            idx += 1
            buf.clear()
            line_count = 0

        for block in contents:
            count = block.count("\n") + 1
            if buf and line_count + count > self.split_at:
                flush()
            buf.append(block)
            line_count += count

        flush()


if __name__ == "__main__":
    ignore_list = [
        ".cache",
        ".config",
        ".git",
        ".ipython",
        ".local",
        ".ssh",
        ".virtualenvs",
        "__pycache__",
        "libs",
        "static/json/blog_data",
        "static/runtime_state",
        "static/libs",
        "static/png",
    ]

    aggregator = CodeAggregator(
        root_dir=".",
        output_filename="project_directory_full_code.txt",
        compaction_level="whitespace",  # none | whitespace | stubs
        comments=True,
        include_dirtree=True,
        include_description=False,
        split_at=22650,
        max_lines_per_file=700,
        truncate_lines=650,
        included_extensions=[".py",".js",  ".html",  ".css",".md"],
        print_only=[],
        exclude_files=[],
        include_files=[],
        ignore_dirs=ignore_list,
        description_text="",
    )

    app.logger.info("Starting aggregation process.")
    aggregator.aggregate()
    app.logger.info(
        f"Aggregated code written with base name '{aggregator.output_filename}'"
    )
    print(
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - "
        f"Aggregation complete for base name '{aggregator.output_filename}'"
    )