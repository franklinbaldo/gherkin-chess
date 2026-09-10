from __future__ import annotations

import re
from pathlib import Path
from typing import Tuple
import semver


def get_current_version(repo_root: Path) -> str:
    """Read current version from src/gherkin_chess/__init__.py."""
    init_py = repo_root / "src" / "gherkin_chess" / "__init__.py"
    if not init_py.exists():
        raise FileNotFoundError(f"Could not find {init_py}")
    
    match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", init_py.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("Could not find __version__ in __init__.py")
    return match.group(1)


def bump_version(repo_root: Path, part: str = "patch") -> Tuple[str, str]:
    """
    Bump project version following Semantic Versioning (semver).
    part: 'patch' | 'minor' | 'major'
    Updates both pyproject.toml and src/gherkin_chess/__init__.py.
    Returns (old_version, new_version).
    """
    old_version_str = get_current_version(repo_root)
    ver = semver.Version.parse(old_version_str)

    if part == "patch":
        new_ver = ver.bump_patch()
    elif part == "minor":
        new_ver = ver.bump_minor()
    elif part == "major":
        new_ver = ver.bump_major()
    else:
        raise ValueError(f"Unknown semver bump part: {part}. Choose 'patch', 'minor', or 'major'.")

    new_version_str = str(new_ver)

    # 1. Update src/gherkin_chess/__init__.py
    init_py = repo_root / "src" / "gherkin_chess" / "__init__.py"
    init_text = init_py.read_text(encoding="utf-8")
    init_text = re.sub(r'__version__\s*=\s*["\'][^"\']+["\']', f'__version__ = "{new_version_str}"', init_text)
    init_py.write_text(init_text, encoding="utf-8")

    # 2. Update pyproject.toml
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        p_text = pyproject.read_text(encoding="utf-8")
        p_text = re.sub(r'version\s*=\s*["\'][^"\']+["\']', f'version = "{new_version_str}"', p_text, count=1)
        pyproject.write_text(p_text, encoding="utf-8")

    return old_version_str, new_version_str


def verify_bump_since_head(repo_root: Path) -> Tuple[bool, str, str]:
    """
    Check if the version in the staging/working tree is greater than git HEAD (via semver).
    Returns (is_valid_bump, current_version, head_version).
    """
    import subprocess
    current_ver_str = get_current_version(repo_root)

    try:
        # Get __init__.py content from git HEAD
        cmd = ["git", "show", "HEAD:src/gherkin_chess/__init__.py"]
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=True)
        head_match = re.search(r"__version__\s*=\s*['\"]([^'\"]+)['\"]", res.stdout)
        if not head_match:
            return True, current_ver_str, "unknown"
        head_ver_str = head_match.group(1)
    except Exception:
        # Initial commit or untracked HEAD
        return True, current_ver_str, "0.0.0"

    current_v = semver.Version.parse(current_ver_str)
    head_v = semver.Version.parse(head_ver_str)

    is_bumped = current_v > head_v
    return is_bumped, current_ver_str, head_ver_str

