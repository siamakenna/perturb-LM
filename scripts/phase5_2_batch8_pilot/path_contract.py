"""Local path policy for the bounded Batch8 tools; no scientific decisions.

The operator selects an existing work root. Reads stay inside that root, and
new results stay inside its Git-ignored ``repo/outputs`` tree. OS ancestor
aliases (for example macOS /var) are allowed; links inside protected trees are
not. Exclusive writes refuse pre-existing files and symbolic links.
"""
import json
import os
import re
import secrets
import stat
import subprocess
from contextlib import contextmanager
from pathlib import Path

MAX_INPUT_BYTES = 32 * 1024 * 1024
POINTERS = {"latest-public-layouts", "latest-batch8-inspection",
            "latest-batch8-technical-qc", "latest-batch8-controls", "latest-batch8-pilot"}


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def parent_descriptor(path, *, root=Path("/")):
    """Open each directory without following links; yield a parent fd and one name.

    The root is selected by the local operator, not by metadata or pointer text.
    Root/OS aliases are canonicalized once. Descendants never follow symlinks.
    A held parent descriptor prevents a later pathname swap redirecting the IO.
    """
    required = ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
    if not all(hasattr(os, flag) for flag in required):
        raise ValueError("Descriptor-relative no-follow IO is required")
    if ".." in Path(path).parts:
        raise ValueError("Parent traversal is not allowed")
    root_real = os.path.realpath(root)
    absolute = Path(path).absolute()
    # Preserve lexical descendants, allowing aliases only at/above the root.
    parts = None
    for ancestor in reversed((absolute, *absolute.parents)):
        if os.path.realpath(ancestor) == root_real:
            parts = absolute.relative_to(ancestor).parts
            break
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Path must name a descendant of its trusted root")
    descriptor = None
    try:
        descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for part in (*Path(root_real).parts[1:], *parts[:-1]):
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor, parts[-1]
    except OSError as exc:
        # Preserve exclusive-creation semantics for callers.
        if isinstance(exc, FileExistsError):
            raise
        raise ValueError(
            "Path is missing, unreadable, or unsafe (Symlinks are not allowed)"
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def read_bytes(path, max_bytes=MAX_INPUT_BYTES, *, root=Path("/")):
    """Read and identify one bounded regular-file snapshot via a held parent fd."""
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("A positive file byte bound is required")
    with parent_descriptor(path, root=root) as (parent, name):
        before = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise ValueError("Input must be a bounded regular nonsymlink file")
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=parent)
        try:
            opened = os.fstat(descriptor)
            if _identity(opened) != _identity(before):
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
            named = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (total != after.st_size or _identity(after) != _identity(opened)
                    or _identity(named) != _identity(after)):
                raise ValueError("Input file changed while reading")
            return b"".join(chunks)
        finally:
            os.close(descriptor)


def exclusive_write_bytes(path, content, *, root=Path("/")):
    if not isinstance(content, bytes):
        raise TypeError("Binary output must be bytes")
    with parent_descriptor(path, root=root) as (parent, name):
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=parent)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)


def exclusive_write_text(path, text, *, root=Path("/")):
    """Create a new private file; never truncate an existing path or link."""
    if not isinstance(text, str):
        raise TypeError("Text output must be a string")
    exclusive_write_bytes(path, text.encode("utf-8"), root=root)


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

    def _canonical(self, requested, *, within=None, must_exist=True):
        requested = Path(requested).absolute()
        bound = self.work_root if within is None else Path(within)
        bound_real = os.path.realpath(bound)
        candidate = os.path.realpath(requested)
        root_real = str(self.work_root)
        if (bound_real != root_real
                and not bound_real.startswith(root_real.rstrip(os.sep) + os.sep)):
            raise ValueError("Path escapes its trusted root")
        if candidate != bound_real and not candidate.startswith(bound_real.rstrip(os.sep) + os.sep):
            raise ValueError("Path escapes its trusted root")
        if requested == self.work_root:
            return self.work_root
        with parent_descriptor(requested, root=self.work_root) as (parent, name):
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                if must_exist:
                    raise ValueError(
                        "Input is changed or is missing, unreadable, or unsafe"
                    ) from None
            else:
                if stat.S_ISLNK(info.st_mode):
                    raise ValueError("Symlinks inside the trusted work root are not allowed")
        return Path(candidate)

    def input_directory(self, path, within=None):
        result = self._canonical(path, within=within)
        if result == self.work_root:
            return result
        with parent_descriptor(result, root=self.work_root) as (parent, name):
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError("Expected an existing regular directory")
        return result

    def input_file(self, path, max_bytes=MAX_INPUT_BYTES, within=None):
        result = self._canonical(path, within=within)
        with parent_descriptor(result, root=self.work_root) as (parent, name):
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
                raise ValueError("Input is changed or is missing, or is not a bounded regular file")
        return result

    def read_bytes(self, path, max_bytes=MAX_INPUT_BYTES, within=None):
        result = self.input_file(path, max_bytes=max_bytes, within=within)
        body = read_bytes(result, max_bytes=max_bytes, root=self.work_root)
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
        result = root / (prefix + secrets.token_hex(16))
        self._git_output_policy(result)
        with parent_descriptor(result, root=self.work_root) as (parent, name):
            os.mkdir(name, mode=0o700, dir_fd=parent)
        try:
            self.input_directory(result, within=root)
            self._git_output_policy(result)
        except Exception:
            # Preserve the empty directory for inspection; never clean by a stale path.
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
        # Preserve an existing target even before output-policy checks.
        with parent_descriptor(requested, root=self.work_root) as (parent, name):
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                if stat.S_ISLNK(info.st_mode):
                    raise ValueError("Symlinks inside the trusted work root are not allowed")
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
        with parent_descriptor(result, root=self.work_root) as (parent, name):
            os.mkdir(name, mode=0o700, dir_fd=parent)
        return result

    def write_text(self, path, text):
        root = self._output_root()
        requested = self._canonical(path, within=root, must_exist=False)
        self.input_directory(requested.parent, within=root)
        exclusive_write_text(requested, text, root=self.work_root)

    def open_output_file(self, path):
        """Return an exclusively created private binary stream for a fixed artifact."""
        root = self._output_root()
        requested = self._canonical(path, within=root, must_exist=False)
        self.input_directory(requested.parent, within=root)
        with parent_descriptor(requested, root=self.work_root) as (parent, name):
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                                 | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        return os.fdopen(descriptor, "wb")

    def write_json(self, path, value):
        self.write_text(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")

    def write_bytes(self, path, content):
        root = self._output_root()
        requested = self._canonical(path, within=root, must_exist=False)
        self.input_directory(requested.parent, within=root)
        exclusive_write_bytes(requested, content, root=self.work_root)

    def unlink_file(self, path):
        """Remove only a regular scratch file under the verified output root."""
        requested = self._canonical(path, within=self._output_root())
        with parent_descriptor(requested, root=self.work_root) as (parent, name):
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Scratch file must be regular")
            os.unlink(name, dir_fd=parent)
