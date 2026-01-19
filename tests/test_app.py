"""Tests for the pixi_to_conda_lock module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from rattler import CondaLockedPackage, LockFile, Platform, PypiLockedPackage

from pixi_to_conda_lock import (
    _convert_env_to_conda_lock,
    _create_conda_lock_metadata,
    _create_conda_package_entry,
    _create_pypi_package_entry,
    _get_output_filename,
    _list_of_str_dependencies_to_dict,
    _parse_args,
    _prepare_output_directory,
    _write_yaml_file,
    convert,
    main,
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
    _write_yaml_file(file_path, data)
    with open(file_path) as f:
        read_data = yaml.safe_load(f)
    assert read_data == data


def test_create_conda_lock_metadata() -> None:
    """Test create_conda_lock_metadata."""
    platforms = ["linux-64", "osx-64"]
    channels = [{"url": "conda-forge", "used_env_vars": []}]
    metadata = _create_conda_lock_metadata(platforms, channels)
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


def test_convert_env_to_conda_lock_default(lock_file: LockFile) -> None:
    """Test _convert_env_to_conda_lock with default environment."""
    conda_lock_data = _convert_env_to_conda_lock(lock_file, "default")
    assert "package" in conda_lock_data
    assert len(conda_lock_data["package"]) == 5  # noqa: PLR2004
    assert sorted(conda_lock_data["metadata"]["platforms"]) == ["osx-64", "osx-arm64"]


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
            "pixi_to_conda_lock._convert_env_to_conda_lock",
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
    result = _create_conda_package_entry(
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
    result = _create_pypi_package_entry(package, platform)
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


def test_create_pypi_package_entry_missing_hash() -> None:
    """Test graceful handling of packages without hashes.

    Some PyPI indexes (like PyTorch's custom index) don't provide SHA256 hashes.
    The function should return an empty hash dict instead of crashing.
    See: https://github.com/basnijholt/pixi-to-conda-lock/pull/12
    """

    class BrokenHashes:
        """Simulates rattler's PackageHashes when internal _hashes is None."""

        @property
        def sha256(self) -> None:
            msg = "'NoneType' object has no attribute 'sha256'"
            raise AttributeError(msg)

    mock_package = Mock(spec=PypiLockedPackage)
    mock_package.name = "torch"
    mock_package.version = "2.0.0"
    mock_package.location = "https://download.pytorch.org/whl/torch-2.0.0.whl"
    mock_package.requires_dist = []
    mock_package.hashes = BrokenHashes()

    platform = Platform("linux-64")
    result = _create_pypi_package_entry(mock_package, platform)

    assert result["name"] == "torch"
    assert result["version"] == "2.0.0"
    assert result["manager"] == "pip"
    assert result["platform"] == "linux-64"
    assert result["hash"] == {}  # Gracefully empty, not crashing
    assert result["url"] == "https://download.pytorch.org/whl/torch-2.0.0.whl"


def test_create_pypi_package_entry_no_hashes_object() -> None:
    """Test handling when package.hashes is None/falsy."""
    mock_package = Mock(spec=PypiLockedPackage)
    mock_package.name = "example"
    mock_package.version = "1.0.0"
    mock_package.location = "https://example.com/example-1.0.0.whl"
    mock_package.requires_dist = []
    mock_package.hashes = None

    platform = Platform("linux-64")
    result = _create_pypi_package_entry(mock_package, platform)

    assert result["name"] == "example"
    assert result["hash"] == {}


def test_list_of_str_dependencies_to_dict() -> None:
    """Test the _list_of_str_dependencies_to_dict function with various inputs."""
    # Test with the provided example
    package_info = [
        "decorator>=5.1.0",
        "requests>=2.24.0",
        "importlib-metadata>=4.11.4",
        "python-dotenv>=1.0.1",
        "qiskit",
        "qiskit>=1.0.0 ; extra == 'test'",
        "pytest ; extra == 'test'",
        "requests-mock>=1.8.0 ; extra == 'test'",
        "pytest-cov==2.10.1 ; extra == 'test'",
    ]

    expected = {
        "decorator": ">=5.1.0",
        "requests": ">=2.24.0",
        "importlib-metadata": ">=4.11.4",
        "python-dotenv": ">=1.0.1",
        "qiskit": ">=1.0.0 ; extra == 'test'",
        "pytest ; extra": "== 'test'",
        "requests-mock": ">=1.8.0 ; extra == 'test'",
        "pytest-cov": "==2.10.1 ; extra == 'test'",
    }

    result = _list_of_str_dependencies_to_dict(package_info)
    assert result == expected

    # Test with empty requires_dist
    assert _list_of_str_dependencies_to_dict([]) == {}

    # Test with more complex version specifiers
    complex_package_info = [
        "numpy>=1.19.3,<2.0.0",
        "pandas>1.0.0,!=1.1.0,<2",
        "scipy~=1.7.0",
    ]

    expected_complex = {
        "numpy": ">=1.19.3,<2.0.0",
        "pandas": ">1.0.0,!=1.1.0,<2",
        "scipy": "~=1.7.0",
    }

    result_complex = _list_of_str_dependencies_to_dict(complex_package_info)
    assert result_complex == expected_complex


def test_convert(tmp_path: Path) -> None:
    """Test the convert function."""
    output = tmp_path / "conda-lock.yml"
    convert(
        PIXI_LOCK_PATH,
        conda_lock_path=output,
    )


def test_missing_env(tmp_path: Path) -> None:
    """Test the convert function with a missing environment."""
    with pytest.raises(ValueError, match="not found in pixi.lock file"):
        convert(
            PIXI_LOCK_PATH,
            conda_lock_path=tmp_path / "conda-lock.yml",
            environment="nonexistent",
        )


def test_no_pip_but_pypi_packages(tmp_path: Path) -> None:
    """Test the convert function with a lock file has pip packages but no pip."""
    with open(PIXI_LOCK_PYPI_PATH) as f:
        data = yaml.safe_load(f)

    # Remove e.g., https://conda.anaconda.org/conda-forge/noarch/pip-25.0.1-pyh145f28c_0.conda
    for env, env_data in data["environments"].items():
        for platform, package_data in env_data["packages"].items():
            remove = []
            for i, dct in enumerate(package_data):
                if "conda" in dct and "/pip-" in dct["conda"]:
                    remove.append(i)
            for i in reversed(remove):
                del data["environments"][env]["packages"][platform][i]

    new_lock_path = tmp_path / "pixi.lock"
    with open(new_lock_path, "w") as f:
        yaml.safe_dump(data, f)
    lock_file = LockFile.from_path(new_lock_path)
    with pytest.raises(
        ValueError,
        match="PyPI packages are present but no pip package found in conda packages.",
    ):
        _convert_env_to_conda_lock(lock_file, "default")


def test_convert_env_to_conda_lock_with_pypi(lock_file_pypi: LockFile) -> None:
    """Test _convert_env_to_conda_lock with a lock file containing pip packages."""
    _convert_env_to_conda_lock(lock_file_pypi, "default")
    _convert_env_to_conda_lock(lock_file_pypi, "project1")
    _convert_env_to_conda_lock(lock_file_pypi, "project2")
