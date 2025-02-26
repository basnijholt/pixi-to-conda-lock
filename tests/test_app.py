"""Tests for the pixi_to_conda_lock module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from rattler.lock import CondaLockedPackage, LockFile, PypiLockedPackage

from pixi_to_conda_lock import (
    _conda_lock_from_lock_file,
    _get_output_filename,
    _parse_args,
    _prepare_output_directory,
    create_conda_lock_metadata,
    create_conda_package_entry,
    create_pypi_package_entry,
    main,
    write_yaml_file,
)

TEST_DIR = Path(__file__).parent
PIXI_LOCK_PATH = TEST_DIR / "test_data" / "pixi.lock"
PIXI_LOCK_PYPI_PATH = TEST_DIR / "test_data" / "pixi-pypi.lock"


@pytest.fixture
def lock_file() -> LockFile:
    """Fixture for creating a LockFile instance."""
    return LockFile.from_path(PIXI_LOCK_PATH)


@pytest.fixture
def lock_file_pypi() -> LockFile:
    """Fixture for creating a LockFile instance."""
    return LockFile.from_path(PIXI_LOCK_PYPI_PATH)


def test_write_yaml_file(tmp_path: Path) -> None:
    """Test write_yaml_file."""
    file_path = tmp_path / "test.yaml"
    data = {"key": "value"}
    write_yaml_file(file_path, data)
    with open(file_path) as f:
        read_data = yaml.safe_load(f)
    assert read_data == data


def test_create_conda_lock_metadata() -> None:
    """Test create_conda_lock_metadata."""
    platforms = ["linux-64", "osx-64"]
    channels = [{"url": "conda-forge", "used_env_vars": []}]
    metadata = create_conda_lock_metadata(platforms, channels)
    assert metadata["platforms"] == ["linux-64", "osx-64"]
    assert metadata["channels"] == channels
    assert "content_hash" in metadata


def test_get_output_filename(tmp_path: Path) -> None:
    """Test _get_output_filename."""
    assert _get_output_filename(tmp_path, "default") == tmp_path / "conda-lock.yml"
    assert _get_output_filename(tmp_path, "dev") == tmp_path / "dev.conda-lock.yml"


def test_parse_args(tmp_path: Path) -> None:
    """Test _parse_args."""
    with patch(
        "sys.argv",
        [
            "pixi-to-conda-lock",
            str(PIXI_LOCK_PATH),
            "-o",
            str(tmp_path),
            "-e",
            "dev",
        ],
    ):
        args = _parse_args()
    assert args.pixi_lock == PIXI_LOCK_PATH
    assert args.output == tmp_path
    assert args.environment == "dev"


def test_prepare_output_directory(tmp_path: Path) -> None:
    """Test _prepare_output_directory."""
    output_dir = tmp_path / "new_output"
    result_dir = _prepare_output_directory(output_dir)
    assert result_dir == output_dir
    assert result_dir.exists()

    # Test with no output path (should use current directory)
    current_dir = _prepare_output_directory(None)
    assert current_dir == Path(".")


def test_conda_lock_from_lock_file_default(lock_file: LockFile) -> None:
    """Test _conda_lock_from_lock_file with default environment."""
    conda_lock_data = _conda_lock_from_lock_file(lock_file, "default")
    assert "package" in conda_lock_data
    assert len(conda_lock_data["package"]) == 5  # noqa: PLR2004
    assert conda_lock_data["metadata"]["platforms"] == ["osx-64", "osx-arm64"]


def test_main_integration(tmp_path: Path) -> None:
    """Integration test for main function."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Test conversion of all environments
    with patch(
        "sys.argv",
        ["pixi-to-conda-lock", str(PIXI_LOCK_PATH), "-o", str(output_dir)],
    ):
        result = main()
    assert result == 0
    assert (output_dir / "conda-lock.yml").exists()  # default env

    # Test conversion of a specific environment
    specific_output_dir = tmp_path / "specific_output"
    specific_output_dir.mkdir()
    with patch(
        "sys.argv",
        [
            "pixi-to-conda-lock",
            str(PIXI_LOCK_PATH),
            "-o",
            str(specific_output_dir),
            "-e",
            "default",
        ],
    ):
        result = main()
    assert result == 0
    assert (specific_output_dir / "conda-lock.yml").exists()


def test_main_file_not_found() -> None:
    """Test main function with non-existent pixi.lock file."""
    with patch(
        "sys.argv",
        ["pixi-to-conda-lock", str(TEST_DIR / "nonexistent.lock")],
    ):
        result = main()
    assert result == 1  # Expect failure


def test_main_exception(tmp_path: Path) -> None:
    """Test main function with an exception during conversion."""
    with (
        patch(
            "sys.argv",
            ["pixi-to-conda-lock", str(PIXI_LOCK_PATH), "-o", str(tmp_path)],
        ),
        patch(
            "pixi_to_conda_lock._conda_lock_from_lock_file",
            side_effect=Exception("Test exception"),
        ),
    ):
        result = main()
        assert result == 1


def test_create_conda_package_entry(lock_file: LockFile) -> None:
    """Test the creation of conda package entries."""
    env = lock_file.environment("default")
    platform = env.platforms()[0]
    conda_repodata = env.conda_repodata_records_for_platform(platform)
    assert conda_repodata is not None
    repo_mapping = {record.url: record for record in conda_repodata}
    package = env.packages(platform)[0]
    assert isinstance(package, CondaLockedPackage)
    result = create_conda_package_entry(
        package,
        platform,
        repo_mapping[package.location],
    )
    assert result["name"] == "bzip2"
    assert result["version"] == "1.0.8"
    assert result["manager"] == "conda"
    assert result["platform"] == str(platform)
    assert "dependencies" in result
    assert "url" in result
    assert "hash" in result
    assert "sha256" in result["hash"]


def test_create_pypi_package_entry(lock_file_pypi: LockFile) -> None:
    """Test the creation of pypi package entries."""
    env = lock_file_pypi.environment("default")
    platform = env.platforms()[0]

    for package in env.packages(platform):
        if isinstance(package, PypiLockedPackage):
            break
    else:
        pytest.fail("No pypi package found.")

    assert isinstance(package, PypiLockedPackage)
    result = create_pypi_package_entry(package, platform)
    assert result["name"] == "numthreads"
    assert result["version"] == "0.5.0"
    assert result["manager"] == "pip"
    assert result["platform"] == str(platform)
    assert result["dependencies"] == {
        "myst-parser ; extra": "== 'docs'",
        "sphinx ; extra": "== 'docs'",
        "furo ; extra": "== 'docs'",
        "emoji ; extra": "== 'docs'",
        "sphinx-autodoc-typehints ; extra": "== 'docs'",
        "pytest ; extra": "== 'test'",
        "pre-commit ; extra": "== 'test'",
        "coverage ; extra": "== 'test'",
        "pytest-cov ; extra": "== 'test'",
        "pytest-mock ; extra": "== 'test'",
    }
    assert "url" in result
    assert "hash" in result
    assert "sha256" in result["hash"]
