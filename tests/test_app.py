"""Tests for the pixi_to_conda_lock package."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, mock_open, patch

import pytest

import pixi_to_conda_lock as ptcl


@pytest.fixture
def sample_pixi_lock() -> dict[str, Any]:
    """Sample pixi.lock data for testing."""
    return {
        "version": 6,
        "environments": {
            "default": {
                "channels": [{"url": "https://conda.anaconda.org/conda-forge/"}],
                "indexes": ["https://pypi.org/simple"],
                "packages": {
                    "osx-arm64": [
                        {
                            "conda": "https://conda.anaconda.org/conda-forge/osx-arm64/python-3.13.2-hfd29fff_1_cp313t.conda",
                        },
                        {
                            "conda": "https://conda.anaconda.org/conda-forge/noarch/pip-25.0.1-pyh8b19718_0.conda",
                        },
                        {
                            "pypi": "https://files.pythonhosted.org/packages/04/27/8739697a1d77f972feee90b844786b893217a133941477570d161de2750f/numthreads-0.5.0-py3-none-any.whl",
                        },
                    ],
                },
            },
            "dev": {
                "channels": [{"url": "https://conda.anaconda.org/conda-forge/"}],
                "indexes": ["https://pypi.org/simple"],
                "packages": {
                    "linux-64": [
                        {
                            "pypi": "https://files.pythonhosted.org/packages/04/27/8739697a1d77f972feee90b844786b893217a133941477570d161de2750f/numthreads-0.5.0-py3-none-any.whl",
                        },
                        {
                            "conda": "https://conda.anaconda.org/conda-forge/linux-64/python-3.11.11-h9e4cc4f_1_cpython.conda",
                        },
                        {
                            "conda": "https://conda.anaconda.org/conda-forge/noarch/pip-25.0.1-pyh8b19718_0.conda",
                        },
                    ],
                },
            },
        },
        "packages": [
            {
                "conda": "https://conda.anaconda.org/conda-forge/osx-arm64/python-3.13.2-hfd29fff_1_cp313t.conda",
                "sha256": "a64466b8f65b77604c3c87092c65d9e51e7db44b11eaa6c469894f0b88b1af5a",
                "md5": "9d0ae3f3e43c192a992827c0abffe284",
                "depends": {"bzip2": ">=1.0.8,<2.0a0", "libexpat": ">=2.6.4,<3.0a0"},
            },
            {
                "conda": "https://conda.anaconda.org/conda-forge/linux-64/python-3.11.11-h9e4cc4f_1_cpython.conda",
                "sha256": "b29ce0836fce55bdff8d5c5b71c4921a23f87d3b950aea89a9e75784120b06b0",
                "md5": "8387070aa413ce9a8cc35a509fae938b",
                "depends": {"bzip2": ">=1.0.8,<2.0a0", "libexpat": ">=2.6.4,<3.0a0"},
            },
            {
                "pypi": "https://files.pythonhosted.org/packages/04/27/8739697a1d77f972feee90b844786b893217a133941477570d161de2750f/numthreads-0.5.0-py3-none-any.whl",
                "name": "numthreads",
                "version": "0.5.0",
                "sha256": "e56e83cbccef103901e678aa014d64b203cdb1b3a3be7cdedb2516ef62ec8fa1",
                "  requires_dist": [
                    "myst-parser ; extra == 'docs'",
                    "sphinx ; extra == 'docs'",
                    "furo ; extra == 'docs'",
                    "emoji ; extra == 'docs'",
                    "sphinx-autodoc-typehints ; extra == 'docs'",
                    "pytest ; extra == 'test'",
                    "pre-commit ; extra == 'test'",
                    "coverage ; extra == 'test'",
                    "pytest-cov ; extra == 'test'",
                    "pytest-mock ; extra == 'test'",
                ],
                "requires_python": ">=3.7",
            },
            {
                "conda": "https://conda.anaconda.org/conda-forge/noarch/pip-25.0.1-pyh8b19718_0.conda",
                "sha256": "585940f09d87787f79f73ff5dff8eb2af8a67e5bec5eebf2f553cd26c840ba69",
                "md5": "79b5c1440aedc5010f687048d9103628",
                "depends": {"python": ">=3.9"},
            },
        ],
    }


@pytest.fixture
def sample_repodata() -> dict[str, Any]:
    """Sample repodata for testing."""
    return {
        "repo1": {
            "info": {"subdir": "osx-arm64"},
            "packages.conda": {
                "python-3.13.2-hfd29fff_1_cp313t.conda": {
                    "name": "python",
                    "version": "3.13.2",
                    "build": "hfd29fff_1_cp313t",
                    "build_number": 1,
                    "depends": ["bzip2 >=1.0.8,<2.0a0", "libexpat >=2.6.4,<3.0a0"],
                    "md5": "9d0ae3f3e43c192a992827c0abffe284",
                    "sha256": "a64466b8f65b77604c3c87092c65d9e51e7db44b11eaa6c469894f0b88b1af5a",
                },
            },
        },
    }


def test_read_yaml_file() -> None:
    """Test reading a YAML file."""
    mock_yaml_content = """
    key1: value1
    key2: value2
    """
    with patch("builtins.open", mock_open(read_data=mock_yaml_content)):
        result = ptcl.read_yaml_file(Path("test.yaml"))
        assert result == {"key1": "value1", "key2": "value2"}


def test_write_yaml_file() -> None:
    """Test writing a YAML file."""
    data = {"key1": "value1", "key2": "value2"}
    mock_file = mock_open()
    with patch("builtins.open", mock_file):
        ptcl.write_yaml_file(Path("test.yaml"), data)
        mock_file.assert_called_once_with(Path("test.yaml"), "w")
        mock_file().write.assert_called()


def test_find_repodata_cache_dir() -> None:
    """Test finding the repodata cache directory."""
    # Simulate a valid repodata directory exists
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.is_dir", return_value=True),
        patch("subprocess.check_output", return_value='{"cache_dir": "/dummy/path"}'),
        patch("json.loads", return_value={"cache_dir": "/dummy/path"}),
        # Create a dummy Path object that behaves like it exists
        patch("pixi_to_conda_lock.Path", wraps=Path),
    ):
        result = ptcl.find_repodata_cache_dir()
        assert result is not None

    # Simulate the repodata directory does not exist, and expect a ValueError
    with (
        patch("pathlib.Path.exists", return_value=False),
        patch("subprocess.check_output", return_value='{"cache_dir": "/dummy/path"}'),
        patch("json.loads", return_value={"cache_dir": "/dummy/path"}),
        pytest.raises(ValueError, match="Could not find repodata cache directory"),
    ):
        ptcl.find_repodata_cache_dir()


def test_load_json_file() -> None:
    """Test loading a JSON file."""
    mock_json_content = '{"key1": "value1", "key2": "value2"}'
    with patch("builtins.open", mock_open(read_data=mock_json_content)):
        result = ptcl.load_json_file(Path("test.json"))
        assert result == {"key1": "value1", "key2": "value2"}


def test_load_repodata_files() -> None:
    """Test loading repodata files."""
    mock_dir = MagicMock()
    mock_file1 = MagicMock()
    mock_file1.name = "file1.json"
    mock_file1.stem = "file1"
    mock_file2 = MagicMock()
    mock_file2.name = "file2.info.json"

    mock_dir.glob.return_value = [mock_file1, mock_file2]

    with patch("pixi_to_conda_lock.load_json_file") as mock_load:
        mock_load.return_value = {"key": "value"}
        result = ptcl.load_repodata_files(mock_dir)

        assert "file1" in result
        assert "file2" not in result
        assert result["file1"] == {"key": "value"}


def test_extract_filename_from_url() -> None:
    """Test extracting filename from URL."""
    url = "https://conda.anaconda.org/conda-forge/osx-arm64/python-3.13.2-hfd29fff_1_cp313t.conda"
    result = ptcl.extract_filename_from_url(url)
    assert result == "python-3.13.2-hfd29fff_1_cp313t.conda"


def test_find_package_in_repodata(sample_repodata: dict[str, Any]) -> None:
    """Test finding a package in repodata."""
    url = "https://conda.anaconda.org/conda-forge/osx-arm64/python-3.13.2-hfd29fff_1_cp313t.conda"
    result = ptcl.find_package_in_repodata(sample_repodata, url)
    assert result is not None
    assert result["name"] == "python"
    assert result["version"] == "3.13.2"

    # Test package not found
    url_not_found = "https://conda.anaconda.org/conda-forge/osx-arm64/nonexistent-1.0.0-abc123.conda"
    result_not_found = ptcl.find_package_in_repodata(sample_repodata, url_not_found)
    assert result_not_found is None


def test_extract_platform_from_url() -> None:
    """Test extracting platform from URL."""
    # Test different platforms
    assert (
        ptcl.extract_platform_from_url(
            "https://conda.anaconda.org/conda-forge/noarch/pkg-1.0.0.conda",
        )
        == "noarch"
    )
    assert (
        ptcl.extract_platform_from_url(
            "https://conda.anaconda.org/conda-forge/osx-arm64/pkg-1.0.0.conda",
        )
        == "osx-arm64"
    )
    assert (
        ptcl.extract_platform_from_url(
            "https://conda.anaconda.org/conda-forge/osx-64/pkg-1.0.0.conda",
        )
        == "osx-64"
    )
    assert (
        ptcl.extract_platform_from_url(
            "https://conda.anaconda.org/conda-forge/linux-64/pkg-1.0.0.conda",
        )
        == "linux-64"
    )
    assert (
        ptcl.extract_platform_from_url(
            "https://conda.anaconda.org/conda-forge/linux-aarch64/pkg-1.0.0.conda",
        )
        == "linux-aarch64"
    )
    assert (
        ptcl.extract_platform_from_url(
            "https://conda.anaconda.org/conda-forge/win-64/pkg-1.0.0.conda",
        )
        == "win-64"
    )
    with pytest.raises(ValueError, match="Unknown platform"):
        ptcl.extract_platform_from_url(
            "https://conda.anaconda.org/conda-forge/unknown/pkg-1.0.0.conda",
        )


def test_extract_name_version_from_url() -> None:
    """Test extracting name and version from URL."""
    # Test standard package
    url = "https://conda.anaconda.org/conda-forge/osx-arm64/python-3.13.2-hfd29fff_1_cp313t.conda"
    name, version = ptcl.extract_name_version_from_url(url)
    assert name == "python"
    assert version == "3.13.2"

    # Test package with tar.bz2 extension
    url_tar = "https://conda.anaconda.org/conda-forge/osx-arm64/python-3.13.2-hfd29fff_1_cp313t.tar.bz2"
    name_tar, version_tar = ptcl.extract_name_version_from_url(url_tar)
    assert name_tar == "python"
    assert version_tar == "3.13.2"

    # Test with dash
    url_with_dash = "https://conda.anaconda.org/conda-forge/osx-arm64/ca-certificates-2025.1.31-hf0a4a13_0.conda"
    name_with_dash, version_with_dash = ptcl.extract_name_version_from_url(
        url_with_dash,
    )
    assert name_with_dash == "ca-certificates"
    assert version_with_dash == "2025.1.31"


def test_parse_dependencies_from_repodata() -> None:
    """Test parsing dependencies from repodata."""
    depends_list = ["python >=3.8", "numpy", "pandas >=1.0.0,<2.0.0"]
    result = ptcl.parse_dependencies_from_repodata(depends_list)
    assert result == {"python": ">=3.8", "numpy": "", "pandas": ">=1.0.0,<2.0.0"}


def test_create_conda_package_entry() -> None:
    """Test creating a conda package entry."""
    url = "https://conda.anaconda.org/conda-forge/osx-arm64/python-3.13.2-hfd29fff_1_cp313t.conda"
    repodata_info = {
        "name": "python",
        "version": "3.13.2",
        "build": "hfd29fff_1_cp313t",
        "build_number": 1,
        "depends": ["bzip2 >=1.0.8,<2.0a0", "libexpat >=2.6.4,<3.0a0"],
        "md5": "9d0ae3f3e43c192a992827c0abffe284",
        "sha256": "a64466b8f65b77604c3c87092c65d9e51e7db44b11eaa6c469894f0b88b1af5a",
    }

    result = ptcl.create_conda_package_entry(url, repodata_info)

    assert result["name"] == "python"
    assert result["version"] == "3.13.2"
    assert result["manager"] == "conda"
    assert result["platform"] == "osx-arm64"
    assert result["dependencies"] == {
        "bzip2": ">=1.0.8,<2.0a0",
        "libexpat": ">=2.6.4,<3.0a0",
    }
    assert result["url"] == url
    assert result["hash"]["md5"] == "9d0ae3f3e43c192a992827c0abffe284"
    assert (
        result["hash"]["sha256"]
        == "a64466b8f65b77604c3c87092c65d9e51e7db44b11eaa6c469894f0b88b1af5a"
    )


def test_create_conda_package_entry_fallback() -> None:
    """Test creating a conda package entry using fallback."""
    url = "https://conda.anaconda.org/conda-forge/osx-arm64/python-3.13.2-hfd29fff_1_cp313t.conda"
    package_info = {
        "depends": ["bzip2 >=1.0.8,<2.0a0", "libexpat >=2.6.4,<3.0a0"],
        "md5": "9d0ae3f3e43c192a992827c0abffe284",
        "sha256": "a64466b8f65b77604c3c87092c65d9e51e7db44b11eaa6c469894f0b88b1af5a",
    }

    result = ptcl.create_conda_package_entry_fallback(url, package_info)

    assert result["name"] == "python"
    assert result["version"] == "3.13.2"
    assert result["manager"] == "conda"
    assert result["platform"] == "osx-arm64"
    assert result["dependencies"] == {
        "bzip2": ">=1.0.8,<2.0a0",
        "libexpat": ">=2.6.4,<3.0a0",
    }
    assert result["url"] == url
    assert result["hash"]["md5"] == "9d0ae3f3e43c192a992827c0abffe284"
    assert (
        result["hash"]["sha256"]
        == "a64466b8f65b77604c3c87092c65d9e51e7db44b11eaa6c469894f0b88b1af5a"
    )


def test_noarch_package_expansion(sample_pixi_lock: dict[str, Any]) -> None:
    """Test that a noarch package is expanded into entries for each platform."""
    # Modify sample_pixi_lock to include a noarch package and specific platforms
    sample_pixi_lock["packages"] = [
        {
            "conda": "https://conda.anaconda.org/conda-forge/noarch/cached-property-1.5.2-hd8ed1ab_1.tar.bz2",
        },
    ]
    sample_pixi_lock["environments"] = {
        "default": {
            "channels": [{"url": "https://conda.anaconda.org/conda-forge/"}],
            "indexes": ["https://pypi.org/simple"],
            # Define two platforms for testing
            "packages": {
                "linux-64": [
                    {
                        "conda": "https://conda.anaconda.org/conda-forge/noarch/cached-property-1.5.2-hd8ed1ab_1.tar.bz2",
                    },
                ],
                "osx-arm64": [
                    {
                        "conda": "https://conda.anaconda.org/conda-forge/noarch/cached-property-1.5.2-hd8ed1ab_1.tar.bz2",
                    },
                ],
            },
        },
    }

    # Create a sample repodata that contains info for the noarch package.
    repodata = {
        "repo1": {
            "info": {"subdir": "noarch"},
            "packages": {
                "cached-property-1.5.2-hd8ed1ab_1.tar.bz2": {
                    "name": "cached-property",
                    "version": "1.5.2",
                    "build": "hd8ed1ab_1",
                    "build_number": 1,
                    "depends": ["cached_property >=1.5.2,<1.5.3.0a0"],
                    "md5": "9b347a7ec10940d3f7941ff6c460b551",
                    "sha256": "561e6660f26c35d137ee150187d89767c988413c978e1b712d53f27ddf70ea17",
                },
            },
        },
    }

    # Process the conda packages.
    result = ptcl.process_conda_packages(sample_pixi_lock, repodata, "default")

    # Expect an entry per platform (linux-64 and osx-arm64)
    assert (
        len(result) == 2  # noqa: PLR2004
    ), "Expected two package entries, one per platform"

    # Check that each entry has the expected properties.
    for entry in result:
        assert entry["name"] == "cached-property"
        assert entry["version"] == "1.5.2"
        assert entry["manager"] == "conda"
        # Even though the URL is noarch, the entry should have the platform set to the target environment.
        assert (
            entry["url"]
            == "https://conda.anaconda.org/conda-forge/noarch/cached-property-1.5.2-hd8ed1ab_1.tar.bz2"
        )
        assert entry["hash"]["md5"] == "9b347a7ec10940d3f7941ff6c460b551"
        assert (
            entry["hash"]["sha256"]
            == "561e6660f26c35d137ee150187d89767c988413c978e1b712d53f27ddf70ea17"
        )

    # Verify that the packages were duplicated for each of the two platforms.
    platforms = {entry["platform"] for entry in result}
    assert platforms == {
        "linux-64",
        "osx-arm64",
    }, "Expected platforms to be linux-64 and osx-arm64"


def test_missing_pip_exception() -> None:
    """Test that convert_env_to_conda_lock raises a ValueError
    when there are PyPI packages but no pip package in conda packages.
    """  # noqa: D205
    # Create a pixi_data sample with a PyPI package and no pip package.
    pixi_data = {
        "environments": {
            "default": {
                "channels": [{"url": "https://conda.anaconda.org/conda-forge/"}],
                # Define two target platforms.
                "packages": {
                    "linux-64": [
                        {
                            "pypi": "https://files.pythonhosted.org/packages/example/somepypi-1.0.0-py3-none-any.whl",
                        },
                    ],
                    "osx-arm64": [],
                },
            },
        },
        "packages": [
            {
                # Only a PyPI package entry, no conda package for pip.
                "pypi": "https://files.pythonhosted.org/packages/example/somepypi-1.0.0-py3-none-any.whl",
                "name": "somepypi",
                "version": "1.0.0",
            },
        ],
    }
    # For this test, repodata can be empty since it's only used for conda packages.
    repodata: dict[str, dict[str, Any]] = {}

    with pytest.raises(
        ValueError,
        match="PyPI packages are present but no pip package found in conda packages",
    ):
        ptcl.convert_env_to_conda_lock(pixi_data, repodata, "default")


def test_get_environment_names() -> None:
    """Test getting environment names from pixi.lock data."""
    pixi_data: dict[str, dict[str, dict]] = {
        "environments": {
            "default": {},
            "dev": {},
            "test": {},
        },
    }
    result = ptcl.get_environment_names(pixi_data)
    assert set(result) == {"default", "dev", "test"}


def test_extract_platforms_from_env() -> None:
    """Test extracting platforms from a specific environment."""
    env_data: dict[str, dict[str, Any]] = {
        "packages": {
            "linux-64": [],
            "osx-arm64": [],
        },
    }
    result = ptcl.extract_platforms_from_env(env_data)
    assert set(result) == {"linux-64", "osx-arm64"}


def test_extract_channels_from_env() -> None:
    """Test extracting channels from a specific environment."""
    env_data = {
        "channels": [
            {"url": "https://conda.anaconda.org/conda-forge/"},
            {"url": "https://conda.anaconda.org/bioconda/"},
        ],
    }
    result = ptcl.extract_channels_from_env(env_data)
    assert len(result) == 2  # noqa: PLR2004
    assert result[0]["url"] == "conda-forge"
    assert result[1]["url"] == "bioconda"


def test_convert_env_to_conda_lock(
    sample_pixi_lock: dict[str, Any],
    sample_repodata: dict[str, Any],
) -> None:
    """Test converting a specific environment to conda-lock format."""
    # Add a second environment to the sample pixi lock
    sample_pixi_lock["environments"]["dev"] = {
        "channels": [{"url": "https://conda.anaconda.org/conda-forge/"}],
        "indexes": ["https://pypi.org/simple"],
        "packages": {
            "linux-64": [
                {
                    "conda": "https://conda.anaconda.org/conda-forge/osx-arm64/python-3.13.2-hfd29fff_1_cp313t.conda",
                },
            ],
        },
    }

    # Test converting the dev environment
    result = ptcl.convert_env_to_conda_lock(sample_pixi_lock, sample_repodata, "dev")

    assert result["version"] == 1
    assert "metadata" in result
    assert "package" in result
    assert len(result["package"]) > 0
    assert result["metadata"]["platforms"] == ["linux-64"]


def test_convert_env_not_found() -> None:
    """Test that converting a non-existent environment raises an error."""
    pixi_data: dict[str, dict[str, Any]] = {
        "environments": {
            "default": {},
        },
    }
    repodata: dict[str, dict[str, Any]] = {}

    with pytest.raises(
        ValueError,
        match="Environment 'nonexistent' not found in pixi.lock file",
    ):
        ptcl.convert_env_to_conda_lock(pixi_data, repodata, "nonexistent")


def test_process_conda_packages_for_environment(
    sample_pixi_lock: dict[str, Any],
    sample_repodata: dict[str, Any],
) -> None:
    """Test processing conda packages for a specific environment."""
    # Process packages for the default environment
    default_packages = ptcl.process_conda_packages(
        sample_pixi_lock,
        sample_repodata,
        "default",
    )
    assert len(default_packages) > 0

    # Process packages for the dev environment
    dev_packages = ptcl.process_conda_packages(sample_pixi_lock, sample_repodata, "dev")
    assert len(dev_packages) > 0

    # The platform should match the environment's platform, not the URL's platform
    assert any(pkg["platform"] == "osx-arm64" for pkg in default_packages)
    assert any(pkg["platform"] == "linux-64" for pkg in dev_packages)


def test_requires_dist_to_dependencies() -> None:
    """Test the _requires_dist_to_dependencies function with various inputs."""
    # Test with the provided example
    package_info = {
        "requires_dist": [
            "decorator>=5.1.0",
            "requests>=2.24.0",
            "importlib-metadata>=4.11.4",
            "python-dotenv>=1.0.1",
            "qiskit",
            "qiskit>=1.0.0 ; extra == 'test'",
            "pytest ; extra == 'test'",
            "requests-mock>=1.8.0 ; extra == 'test'",
            "pytest-cov==2.10.1 ; extra == 'test'",
        ],
    }

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

    result = ptcl._requires_dist_to_dependencies(package_info)
    assert result == expected

    # Test with empty requires_dist
    assert ptcl._requires_dist_to_dependencies({}) == {}

    # Test with more complex version specifiers
    complex_package_info = {
        "requires_dist": [
            "numpy>=1.19.3,<2.0.0",
            "pandas>1.0.0,!=1.1.0,<2",
            "scipy~=1.7.0",
        ],
    }

    expected_complex = {
        "numpy": ">=1.19.3,<2.0.0",
        "pandas": ">1.0.0,!=1.1.0,<2",
        "scipy": "~=1.7.0",
    }

    result_complex = ptcl._requires_dist_to_dependencies(complex_package_info)
    assert result_complex == expected_complex
