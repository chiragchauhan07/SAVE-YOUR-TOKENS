"""Unit tests for the Phase 1 repository scanner."""

from __future__ import annotations

import pytest

from analyzer import scan_repository
from analyzer.utils import extension_of, human_readable_size


def build_repo(root, files: dict[str, str]) -> None:
    """Materialise a fake repository from a ``{relative path: content}`` map."""
    for relative_path, content in files.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


@pytest.fixture
def sample_repo(tmp_path):
    """A small repository containing both signal and noise."""
    build_repo(
        tmp_path,
        {
            "README.md": "# demo\n",
            "main.py": "print('hi')\n",
            "src/app.py": "x = 1\n",
            "src/util.py": "y = 2\n",
            "src/styles.css": "body{}\n",
            "docs/guide.md": "guide\n",
            "Makefile": "all:\n",
            # Noise that must be excluded:
            ".git/config": "[core]\n",
            "node_modules/left-pad/index.js": "module.exports = 1\n",
            "src/__pycache__/app.cpython-312.pyc": "bytecode",
            "assets/logo.png": "notreallyapng",
            ".env": "SECRET=1\n",
        },
    )
    return tmp_path


def test_returns_only_relevant_files(sample_repo):
    project = scan_repository(sample_repo)
    assert {str(file.path) for file in project.files} == {
        "README.md",
        "main.py",
        "src/app.py",
        "src/util.py",
        "src/styles.css",
        "docs/guide.md",
        "Makefile",
    }


def test_prunes_ignored_directories(sample_repo):
    project = scan_repository(sample_repo)
    paths = [str(file.path) for file in project.files]
    assert not any(path.startswith(".git/") for path in paths)
    assert not any("node_modules" in path for path in paths)
    assert not any("__pycache__" in path for path in paths)


def test_ignores_binary_extensions_and_hidden_files(sample_repo):
    project = scan_repository(sample_repo)
    names = {file.name for file in project.files}
    assert "logo.png" not in names
    assert ".env" not in names


def test_include_hidden_keeps_dotfiles_but_not_ignored_dirs(sample_repo):
    project = scan_repository(sample_repo, include_hidden=True)
    paths = {str(file.path) for file in project.files}
    assert ".env" in paths
    # .git is explicitly ignored, so --include-hidden must not resurrect it.
    assert not any(path.startswith(".git/") for path in paths)


def test_extra_ignored_directories(sample_repo):
    project = scan_repository(sample_repo, extra_ignored_directories=["docs"])
    assert not any(str(file.path).startswith("docs/") for file in project.files)


def test_project_metadata(sample_repo):
    project = scan_repository(sample_repo)
    assert project.name == sample_repo.name
    assert project.root == sample_repo.resolve()


def test_stats_are_consistent(sample_repo):
    project = scan_repository(sample_repo)
    stats = project.stats
    assert stats.total_files == len(project.files)
    assert stats.total_size_bytes == sum(f.size_bytes for f in project.files)
    assert sum(stats.files_by_extension.values()) == stats.total_files
    # assets, docs, src are walked; .git, node_modules and __pycache__ are
    # pruned and never counted.
    assert stats.total_directories == 3


def test_files_by_extension_is_ordered_by_frequency(sample_repo):
    stats = scan_repository(sample_repo).stats
    counts = list(stats.files_by_extension.values())
    assert counts == sorted(counts, reverse=True)
    assert stats.files_by_extension[".py"] == 3
    # Makefile has no extension and is grouped under "".
    assert stats.files_by_extension[""] == 1


def test_largest_files_sorted_descending(tmp_path):
    build_repo(
        tmp_path,
        {"small.py": "a", "big.py": "a" * 500, "medium.py": "a" * 50},
    )
    largest = scan_repository(tmp_path).stats.largest_files
    assert [file.name for file in largest] == ["big.py", "medium.py", "small.py"]


def test_scan_is_deterministic(sample_repo):
    first = scan_repository(sample_repo)
    second = scan_repository(sample_repo)
    assert first == second
    assert [str(f.path) for f in first.files] == sorted(
        str(f.path) for f in first.files
    )


def test_paths_are_posix_style(sample_repo):
    project = scan_repository(sample_repo)
    assert all("\\" not in str(file.path) for file in project.files)


def test_empty_repository(tmp_path):
    project = scan_repository(tmp_path)
    assert project.files == ()
    assert project.stats.total_files == 0
    assert project.stats.total_size_bytes == 0


def test_lookup_helpers(sample_repo):
    project = scan_repository(sample_repo)
    assert len(project.files_with_extension(".py")) == 3
    assert [str(f.path) for f in project.find("README.md")] == ["README.md"]


def test_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        scan_repository(tmp_path / "nope")


def test_file_path_raises(tmp_path):
    target = tmp_path / "a_file.txt"
    target.write_text("hi", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        scan_repository(target)


def test_file_depth(sample_repo):
    project = scan_repository(sample_repo)
    depths = {str(f.path): f.depth for f in project.files}
    assert depths["README.md"] == 0
    assert depths["src/app.py"] == 1


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("app.py", ".py"),
        ("App.PY", ".py"),
        ("Makefile", ""),
        (".gitignore", ""),
        ("archive.tar.gz", ".gz"),
    ],
)
def test_extension_of(name, expected):
    assert extension_of(name) == expected


@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (0, "0 B"),
        (512, "512 B"),
        (1024, "1.0 KB"),
        (1536, "1.5 KB"),
        (1048576, "1.0 MB"),
    ],
)
def test_human_readable_size(size, expected):
    assert human_readable_size(size) == expected
