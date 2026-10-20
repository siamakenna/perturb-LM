"""Local path policy for the bounded Batch8 tools; no scientific decisions.

The operator selects an existing work root. Reads stay inside that root, and
new results stay inside its Git-ignored ``repo/outputs`` tree. OS ancestor
aliases (for example macOS /var) are allowed; links inside protected trees are
not. Exclusive writes refuse pre-existing files and symbolic links.
"""
import json
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path


MAX_INPUT_BYTES = 32 * 1024 * 1024
POINTERS = {"latest-public-layouts", "latest-batch8-inspection",
            "latest-batch8-technical-qc", "latest-batch8-controls", "latest-batch8-pilot"}


def read_bytes(path, max_bytes=MAX_INPUT_BYTES):
    """Read one bounded regular nonsymlink file, never a FIFO or device."""
    path = Path(path)
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("A positive file byte bound is required")
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise ValueError("Input must be a bounded regular nonsymlink file")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (not stat.S_ISREG(opened.st_mode) or opened.st_size > max_bytes
                    or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
                raise ValueError("Input file changed while opening")
            chunks, total = [], 0
            while True:
                block = os.read(descriptor, min(1024 * 1024, max_bytes - total + 1))
                if not block:
                    break
                total += len(block)
                if total > max_bytes:
                    raise ValueError("Input exceeds its byte bound")
                chunks.append(block)
            after = os.fstat(descriptor)
            if (after.st_size != total or after.st_size != opened.st_size
                    or after.st_mtime_ns != opened.st_mtime_ns):
                raise ValueError("Input file changed while reading")
            return b"".join(chunks)
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise ValueError("Input is changed or is missing, unreadable, or unsafe") from exc


def exclusive_write_text(path, text):
    """Create a new private file; never truncate an existing path or link."""
    if not isinstance(text, str):
        raise TypeError("Text output must be a string")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(Path(path), flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            descriptor = None
            stream.write(text)
    finally:
        if descriptor is not None:
            os.close(descriptor)


def exclusive_write_bytes(path, content):
    if not isinstance(content, bytes):
        raise TypeError("Binary output must be bytes")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(Path(path), flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(content)
    finally:
        if descriptor is not None:
            os.close(descriptor)


def exclusive_write_json(path, value):
    exclusive_write_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


class PathContract:
    def __init__(self, work_root):
        try:
            self.work_root = Path(work_root).resolve(strict=True)
        except OSError as exc:
            raise ValueError("An existing trusted work root is required") from exc
        if not self.work_root.is_dir():
            raise ValueError("The trusted work root must be a directory")
        self.repo = self.work_root / "repo"
        self.outputs = self.repo / "outputs"

    def _reject_internal_links(self, requested):
        for component in (Path(requested).absolute(), *Path(requested).absolute().parents):
            if component.is_symlink():
                parent = component.parent.resolve(strict=True)
                if parent == self.work_root or parent.is_relative_to(self.work_root):
                    raise ValueError("Symlinks inside the trusted work root are not allowed")

    def _canonical(self, requested, *, within=None, must_exist=True):
        requested = Path(requested).absolute()
        self._reject_internal_links(requested)
        try:
            resolved = requested.resolve(strict=must_exist)
            bound = Path(within).resolve(strict=True) if within is not None else self.work_root
        except OSError as exc:
            raise ValueError("Input is changed or is missing, unreadable, or unsafe") from exc
        if (not bound.is_relative_to(self.work_root)
                or not resolved.is_relative_to(bound)):
            raise ValueError("Path escapes its trusted root")
        self._reject_internal_links(resolved)
        return resolved

    def input_directory(self, path, within=None):
        result = self._canonical(path, within=within)
        if not result.is_dir():
            raise ValueError("Expected an existing regular directory")
        return result

    def input_file(self, path, max_bytes=MAX_INPUT_BYTES, within=None):
        result = self._canonical(path, within=within)
        info = result.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
            raise ValueError("Input is changed or is missing, or is not a bounded regular file")
        return result

    def read_bytes(self, path, max_bytes=MAX_INPUT_BYTES, within=None):
        result = self.input_file(path, max_bytes=max_bytes, within=within)
        body = read_bytes(result, max_bytes=max_bytes)
        # Detect changed ancestors before interpreting the returned snapshot.
        if self._canonical(path, within=within) != result:
            raise ValueError("Input path changed while reading")
        return body

    def read_pointer(self, name):
        if name not in POINTERS:
            raise ValueError("Unknown location pointer")
        try:
            body = self.read_bytes(self.work_root / (name + ".txt"), max_bytes=4096)
            text = body.decode("utf-8").strip()
            if not text or "\n" in text or "\r" in text or not Path(text).is_absolute():
                raise ValueError("Invalid pointer text")
            return self.input_directory(text)
        except (OSError, ValueError, UnicodeError) as exc:
            raise ValueError("Invalid recorded location: " + name) from exc

    def _git(self, *arguments):
        result = subprocess.run(["git", "-C", str(self.repo), *arguments],
                                capture_output=True, text=True, check=False)
        if result.returncode:
            raise ValueError("Repository output policy could not be verified")
        return result.stdout.strip()

    def _output_root(self):
        self.input_directory(self.repo)
        self.input_directory(self.outputs, within=self.repo)
        if Path(self._git("rev-parse", "--show-toplevel")).resolve(strict=True) != self.repo:
            raise ValueError("Expected work_root/repo to be the Git repository root")
        result = subprocess.run(["git", "-C", str(self.repo), "check-ignore", "--quiet",
                                 "--no-index", "--", "outputs/"], capture_output=True, check=False)
        if result.returncode:
            raise ValueError("Repository outputs must be Git ignored")
        return self.outputs

    def validate_output_root(self):
        return self._output_root()

    def create_run_directory(self, prefix):
        if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", prefix):
            raise ValueError("A fixed safe run-directory prefix is required")
        root = self._output_root()
        result = Path(tempfile.mkdtemp(prefix=prefix, dir=root))
        try:
            self.input_directory(result, within=root)
            self._git_output_policy(result)
        except Exception:
            result.rmdir()  # Only the new empty directory, before any log/file write.
            raise
        return result

    def _git_output_policy(self, path):
        relative = path.relative_to(self.repo).as_posix()
        if self._git("--literal-pathspecs", "ls-files", "--cached", "-z", "--", relative):
            raise ValueError("Output prefix contains tracked files")
        ignored = subprocess.run(["git", "-C", str(self.repo), "check-ignore", "--quiet",
                                  "--no-index", "--", relative], capture_output=True, check=False)
        if ignored.returncode:
            raise ValueError("Output path must be Git ignored")

    def fresh_output(self, out, forbidden=()):
        requested = Path(out).absolute()
        self._reject_internal_links(requested)
        if requested.exists() or requested.is_symlink():
            raise FileExistsError("Output must be a new, nonexistent directory")
        root = self._output_root()
        parent = self.input_directory(requested.parent, within=root)
        result = parent / requested.name
        if result == root or not result.is_relative_to(root):
            raise ValueError("Output must be inside the repository outputs tree")
        for item in forbidden:
            blocked = self._canonical(item)
            if (result == blocked or result.is_relative_to(blocked)
                    or blocked.is_relative_to(result)):
                raise ValueError("Output overlaps an input directory")
        self._git_output_policy(result)
        return result

    def create_output(self, out, forbidden=()):
        result = self.fresh_output(out, forbidden=forbidden)
        result.mkdir(mode=0o700, parents=False, exist_ok=False)
        return result

    def write_text(self, path, text):
        root = self._output_root()
        requested = self._canonical(path, within=root, must_exist=False)
        self.input_directory(requested.parent, within=root)
        exclusive_write_text(requested, text)

    def open_output_file(self, path):
        """Return an exclusively created private binary stream for a fixed artifact."""
        root = self._output_root()
        requested = self._canonical(path, within=root, must_exist=False)
        self.input_directory(requested.parent, within=root)
        descriptor = os.open(requested, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | getattr(os, "O_NOFOLLOW", 0), 0o600)
        return os.fdopen(descriptor, "wb")

    def write_json(self, path, value):
        self.write_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")

    def write_bytes(self, path, content):
        root = self._output_root()
        requested = self._canonical(path, within=root, must_exist=False)
        self.input_directory(requested.parent, within=root)
        exclusive_write_bytes(requested, content)
