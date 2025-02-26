#!/usr/bin/env python3
"""Convert a pixi.lock file to a conda-lock.yml file using repodata.

This script reads a pixi.lock file and generates a conda-lock.yml file with the same
package information, using repodata to extract accurate package metadata.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


def setup_logging(verbose: bool = False) -> None:  # noqa: FBT001, FBT002
    """Set up logging configuration.

    Args:
        verbose: Whether to enable debug logging

    """
    try:
        from rich.logging import RichHandler

        handlers = [RichHandler(rich_tracebacks=True)]
    except ImportError:
        handlers = [logging.StreamHandler()]

    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def read_yaml_file(file_path: Path) -> dict[str, Any]:
    """Read a YAML file and return its contents as a dictionary."""
    logging.debug("Reading YAML file: %s", file_path)
    with open(file_path) as f:
        data = yaml.safe_load(f)
    logging.debug("Successfully read YAML file: %s", file_path)
    return data


def write_yaml_file(file_path: Path, data: dict[str, Any]) -> None:
    """Write data to a YAML file."""
    logging.debug("Writing YAML file: %s", file_path)
    with open(file_path, "w") as f:
        yaml.dump(data, f, sort_keys=False)
    logging.debug("Successfully wrote YAML file: %s", file_path)


def find_repodata_cache_dir() -> Path | None:
    """Find the repodata cache directory using 'pixi info --json' output.

    This function runs 'pixi info --json' and extract the 'cache_dir'
    field, appending 'repodata' to it.
    """
    cmd = ["pixi", "info", "--json"]
    result = subprocess.check_output(cmd, text=True)  # noqa: S603
    info = json.loads(result)
    cache_dir = info.get("cache_dir")
    if cache_dir:
        repodata_path = Path(cache_dir) / "repodata"
        logging.debug("Using cache_dir from pixi info: %s", repodata_path)
        if repodata_path.exists() and repodata_path.is_dir():
            return repodata_path
    msg = "Could not find repodata cache directory"
    raise ValueError(msg)


def load_json_file(file_path: Path) -> dict[str, Any]:
    """Load a JSON file and return its contents as a dictionary."""
    logging.debug("Loading JSON file: %s", file_path)
    with open(file_path) as f:
        data = json.load(f)
    logging.debug("Successfully loaded JSON file: %s", file_path)
    return data


def load_repodata_files(repodata_dir: Path) -> dict[str, dict[str, Any]]:
    """Load all repodata files from the cache directory."""
    logging.info("Loading repodata files from: %s", repodata_dir)
    repodata = {}

    # Load all .json files (not .info.json)
    json_files = list(repodata_dir.glob("*.json"))
    logging.debug("Found %d JSON files in repodata directory", len(json_files))

    for file_path in json_files:
        if not file_path.name.endswith(".info.json"):
            try:
                logging.debug("Loading repodata file: %s", file_path.name)
                data = load_json_file(file_path)
                repodata[file_path.stem] = data
                logging.debug("Successfully loaded repodata file: %s", file_path.name)
            except Exception as e:  # noqa: BLE001
                logging.warning("Failed to load %s: %s", file_path, e)

    logging.info("Loaded %d repodata files", len(repodata))
    return repodata


def find_and_load_repodata_files(
    repodata_dir: Path | None,
) -> dict[str, dict[str, Any]]:
    """Find and load repodata files from the cache directory."""
    if repodata_dir is None:
        found_repodata_dir = find_repodata_cache_dir()
        if found_repodata_dir is None:
            msg = "Could not find repodata cache directory"
            raise ValueError(msg)
        logging.info("Using repodata from: %s", found_repodata_dir)
        return load_repodata_files(found_repodata_dir)
    if not repodata_dir.exists():
        msg = f"❌ Repodata directory not found: {repodata_dir}"
        raise FileNotFoundError(msg)
    logging.info("Using specified repodata directory: %s", repodata_dir)
    return load_repodata_files(repodata_dir)


def extract_filename_from_url(url: str) -> str:
    """Extract the filename from a URL."""
    filename = url.split("/")[-1]
    logging.debug("Extracted filename '%s' from URL: %s", filename, url)
    return filename


def find_package_in_repodata(
    repodata: dict[str, dict[str, Any]],
    package_url: str,
) -> dict[str, Any] | None:
    """Find a package in repodata based on its URL."""
    logging.debug("Searching for package in repodata: %s", package_url)
    filename = extract_filename_from_url(package_url)

    # Check all repodata files
    for repo_name, repo_data in repodata.items():
        # Check in packages (.tar.bz2)
        if "packages" in repo_data and filename in repo_data["packages"]:
            logging.debug(
                "🔍 Found package '%s' in repository '%s'",
                filename,
                repo_name,
            )
            return repo_data["packages"][filename]

        # Check in packages.conda (.conda)
        if "packages.conda" in repo_data and filename in repo_data["packages.conda"]:
            logging.debug(
                "🔍 Found package '%s' in repository '%s' (packages.conda)",
                filename,
                repo_name,
            )
            return repo_data["packages.conda"][filename]

    logging.debug("Package not found in repo")
    return None


def extract_platform_from_url(url: str) -> str:
    """Extract platform information from a conda package URL."""
    logging.debug("Extracting platform from URL: %s", url)
    platforms = {
        "/noarch/": "noarch",
        "/osx-arm64/": "osx-arm64",
        "/osx-64/": "osx-64",
        "/linux-64/": "linux-64",
        "/linux-aarch64/": "linux-aarch64",
        "/win-64/": "win-64",
    }
    for key, platform in platforms.items():
        if key in url:
            logging.debug("Extracted platform: %s", platform)
            return platform
    msg = f"Unknown platform in URL: {url}"
    raise ValueError(msg)


def extract_name_version_from_url(url: str) -> tuple[str, str]:
    """Extract package name and version from a conda package URL as a fallback."""
    logging.debug("Extracting name and version from URL: %s", url)
    filename = extract_filename_from_url(url)

    # Remove file extension
    filename_no_ext = _remove_file_extension(filename)

    # Split by hyphens to separate name, version, and build
    try:
        parts = filename_no_ext.rsplit("-", 2)
        if len(parts) < 3:  # noqa: PLR2004
            msg = f"Cannot parse package name and version from filename: {filename}"
            raise ValueError(msg)  # noqa: TRY301

        name, version, _build_string = parts
        logging.debug("Extracted name: %s, version: %s", name, version)
        return name, version  # noqa: TRY300
    except Exception as e:
        msg = f"Failed to extract name and version from URL {url}: {e}"
        raise ValueError(msg) from e


def _remove_file_extension(filename: str) -> str:
    """Remove conda package file extension (.conda or .tar.bz2)."""
    if filename.endswith(".conda"):
        return filename[:-6]
    if filename.endswith(".tar.bz2"):
        return filename[:-8]
    return filename


def parse_dependencies_from_repodata(depends_list: list[str]) -> dict[str, str]:
    """Parse dependencies from repodata format to conda-lock format."""
    logging.debug("Parsing dependencies from repolist")
    dependencies = {}
    for dep in depends_list:
        parts = dep.split()
        if len(parts) > 1:
            dependencies[parts[0]] = " ".join(parts[1:])
        else:
            dependencies[dep] = ""
    logging.debug("Parsed dependencies: %s", dependencies)
    return dependencies


def create_conda_package_entry(
    url: str,
    repodata_info: dict[str, Any],
) -> dict[str, Any]:
    """Create a conda package entry for conda-lock.yml from repodata."""
    logging.debug("Creating conda package entry from repodata for: %s", url)
    platform = extract_platform_from_url(url)

    package_entry = {
        "name": repodata_info["name"],
        "version": repodata_info["version"],
        "manager": "conda",
        "platform": platform,
        "dependencies": parse_dependencies_from_repodata(
            repodata_info.get("depends", []),
        ),
        "url": url,
        "hash": {
            "md5": repodata_info["md5"],
            "sha256": repodata_info["sha256"],
        },
        "category": "main",
        "optional": False,
    }

    logging.debug(
        "Created conda package entry: %s v%s",
        package_entry["name"],
        package_entry["version"],
    )
    return package_entry


def create_conda_package_entry_fallback(
    url: str,
    package_info: dict[str, Any],
) -> dict[str, Any]:
    """Create a conda package entry for conda-lock.yml using URL parsing as fallback."""
    logging.debug("Creating conda package entry using fallback for: %s", url)
    platform = extract_platform_from_url(url)
    name, version = extract_name_version_from_url(url)
    package_entry = {
        "name": name,
        "version": version,
        "manager": "conda",
        "platform": platform,
        "dependencies": parse_dependencies_from_repodata(
            package_info.get("depends", []),
        ),
        "url": url,
        "hash": {
            "md5": package_info.get("md5", ""),
            "sha256": package_info.get("sha256", ""),
        },
        "category": "main",
        "optional": False,
    }

    logging.debug("Created conda package entry (fallback): %s v%s", name, version)
    return package_entry


def create_pypi_package_entry(
    platform: str,
    package_info: dict[str, Any],
) -> dict[str, Any]:
    """Create a PyPI package entry for conda-lock.yml."""
    url = package_info["pypi"]
    logging.debug("Creating PyPI package entry for: %s (platform: %s)", url, platform)
    package_entry = {
        "name": package_info.get("name", ""),
        "version": package_info.get("version", ""),
        "manager": "pip",
        "platform": platform,
        "dependencies": _requires_dist_to_dependencies(
            package_info,
        ),  # PyPI dependencies are handled differently
        "url": url,
        "hash": {
            "sha256": package_info.get("sha256", ""),
        },
        "category": "main",
        "optional": False,
    }

    logging.debug(
        "Created PyPI package entry: %s v%s",
        package_entry["name"],
        package_entry["version"],
    )
    return package_entry


def _requires_dist_to_dependencies(package_info: dict[str, Any]) -> dict[str, str]:
    """Convert package requirements from 'requires_dist' format to conda-lock format."""
    requires_dist = package_info.get("requires_dist", [])
    dependencies = {}
    for requirement in requires_dist:
        # Split by first occurrence of any version specifier
        match = re.match(r"([^<>=!~]+)(.+)?", requirement)
        if match:
            package_name = match.group(1).strip()
            version_constraint = match.group(2) or "*"
            dependencies[package_name] = version_constraint.strip()

    return dependencies


def extract_platforms_from_env(env_data: dict[str, Any]) -> list[str]:
    """Extract platform information from a specific environment in pixi.lock data."""
    logging.debug("Extracting platforms from environment data")
    platforms = []
    for platform in env_data.get("packages", {}):
        if platform not in platforms and platform != "noarch":
            platforms.append(platform)
            logging.debug("Added platform: %s", platform)

    logging.info("Extracted platforms: %s", platforms)
    return platforms


def _channel_url_to_name(url: str) -> str:
    """Convert a channel URL to a channel name."""
    return url.replace("https://conda.anaconda.org/", "").rstrip("/")


def extract_channels_from_env(env_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract channel information from a specific environment in pixi.lock data."""
    logging.debug("Extracting channels from environment data")
    channels_data = env_data.get("channels", [])
    channels = [
        {"url": _channel_url_to_name(channel["url"]), "used_env_vars": []}
        for channel in channels_data
    ]

    logging.info(
        "Extracted %d channels: %s",
        len(channels),
        [c["url"] for c in channels],
    )
    return channels


def create_conda_lock_metadata(
    platforms: list[str],
    channels: list[dict[str, str]],
) -> dict[str, Any]:
    """Create metadata section for conda-lock.yml."""
    logging.debug("Creating conda-lock metadata")
    metadata = {
        "content_hash": {
            platform: "generated-from-pixi-lock" for platform in platforms
        },
        "channels": channels,
        "platforms": platforms,
        "sources": ["converted-from-pixi.lock"],
    }
    logging.debug("Created conda-lock metadata with %d platforms", len(platforms))
    return metadata


def process_conda_packages(
    pixi_data: dict[str, Any],
    repodata: dict[str, dict[str, Any]],
    env_name: str,
) -> list[dict[str, Any]]:
    """Process conda packages from pixi.lock and convert to conda-lock format for a specific environment."""
    logging.info(
        "Processing conda packages from pixi.lock for environment '%s'",
        env_name,
    )
    package_entries = []
    conda_packages = [p for p in pixi_data.get("packages", []) if "conda" in p]

    # Get environment-specific data
    env_data = pixi_data.get("environments", {}).get(env_name, {})
    platforms = extract_platforms_from_env(env_data)

    logging.debug("Found %d conda packages to process", len(conda_packages))

    # Get package URLs specific to this environment
    env_package_urls = _get_env_package_urls(env_data, "conda")

    logging.debug(
        "Environment '%s' has %d conda package URLs",
        env_name,
        len(env_package_urls),
    )

    for package_info in conda_packages:
        url = package_info["conda"]

        # Skip packages not used in this environment
        if url not in env_package_urls:
            logging.debug(
                "Skipping package not used in environment '%s': %s",
                env_name,
                url,
            )
            continue

        logging.debug("Processing conda package: %s", url)

        # Try to find package in repodata
        repodata_info = find_package_in_repodata(repodata, url)

        # Create a base package entry, either using repodata or fallback.
        if repodata_info:
            # Use the information from repodata
            logging.debug("✅ Using repodata information for package")
            base_entry = create_conda_package_entry(url, repodata_info)
        else:
            # Fallback to parsing the URL if repodata doesn't have the package
            logging.warning("❌ Repodata not found, using fallback method")
            base_entry = create_conda_package_entry_fallback(url, package_info)

        # If the package is noarch, replicate it for each platform.
        if "noarch" in url:
            for plat in platforms:
                entry = base_entry.copy()
                entry["platform"] = plat
                package_entries.append(entry)
        else:
            package_entries.append(base_entry)

    logging.info(
        "Processed %d conda packages for environment '%s'",
        len(package_entries),
        env_name,
    )
    return package_entries


def _get_env_package_urls(env_data: dict[str, Any], package_type: str) -> list[str]:
    return [
        package[package_type]
        for platform, packages in env_data.get("packages", {}).items()
        for package in packages
        if package_type in package
    ]


def process_pypi_packages(
    pixi_data: dict[str, Any],
    platforms: list[str],
    env_name: str,
) -> tuple[list[dict[str, Any]], bool]:
    """Process PyPI packages from pixi.lock and convert to conda-lock format for a specific environment."""
    logging.info(
        "Processing PyPI packages from pixi.lock for environment '%s'",
        env_name,
    )
    package_entries: list[dict[str, Any]] = []

    # Get environment-specific data
    env_data = pixi_data.get("environments", {}).get(env_name, {})

    # Get PyPI packages and environment-specific URLs
    pypi_packages = [p for p in pixi_data.get("packages", []) if "pypi" in p]
    env_package_urls = _get_env_package_urls(env_data, "pypi")

    logging.debug(
        "Found %d PyPI packages to process for environment '%s'",
        len(pypi_packages),
        env_name,
    )
    logging.debug(
        "Environment '%s' has %d PyPI package URLs",
        env_name,
        len(env_package_urls),
    )

    has_pypi_packages = False
    for package_info in pypi_packages:
        url = package_info["pypi"]

        # Skip packages not used in this environment
        if url not in env_package_urls:
            logging.debug(
                "Skipping package not used in environment '%s': %s",
                env_name,
                url,
            )
            continue

        has_pypi_packages = True
        _process_and_add_pypi_package(package_entries, package_info, platforms)

    logging.info(
        "Processed %d PyPI package entries for environment '%s' (across all platforms)",
        len(package_entries),
        env_name,
    )
    return package_entries, has_pypi_packages


def _process_and_add_pypi_package(
    package_entries: list[dict[str, Any]],
    package_info: dict[str, Any],
    platforms: list[str],
) -> None:
    """Process a PyPI package and add entries for each platform."""
    logging.debug(
        "Processing PyPI package: %s v%s",
        package_info.get("name", "unknown"),
        package_info.get("version", "unknown"),
    )

    for platform in platforms:
        logging.debug("Creating entry for platform: %s", platform)
        package_entry = create_pypi_package_entry(platform, package_info)
        package_entries.append(package_entry)


def convert_env_to_conda_lock(
    pixi_data: dict[str, Any],
    repodata: dict[str, dict[str, Any]],
    env_name: str,
) -> dict[str, Any]:
    """Convert pixi.lock data structure to conda-lock.yml format for a specific environment."""
    logging.info(
        "Converting pixi.lock to conda-lock.yml format for environment '%s'",
        env_name,
    )

    # Get environment-specific data
    env_data = _get_environment_data(pixi_data, env_name)

    # Extract platforms and channels
    platforms = extract_platforms_from_env(env_data)
    channels = extract_channels_from_env(env_data)

    # Create basic conda-lock structure
    conda_lock_data = _create_conda_lock_structure(platforms, channels)

    # Process packages
    _process_and_add_packages(conda_lock_data, pixi_data, repodata, env_name, platforms)

    logging.info(
        "Conversion complete for environment '%s' - conda-lock data contains %d package entries",
        env_name,
        len(conda_lock_data["package"]),  # type: ignore[arg-type]
    )
    return conda_lock_data


def _get_environment_data(pixi_data: dict[str, Any], env_name: str) -> dict[str, Any]:
    """Get environment-specific data from pixi.lock."""
    env_data = pixi_data.get("environments", {}).get(env_name, {})
    if not env_data:
        msg = f"Environment '{env_name}' not found in pixi.lock file"
        raise ValueError(msg)
    return env_data


def _create_conda_lock_structure(
    platforms: list[str],
    channels: list[dict[str, str]],
) -> dict[str, Any]:
    """Create the basic structure for a conda-lock file."""
    return {
        "version": 1,
        "metadata": create_conda_lock_metadata(platforms, channels),
        "package": [],
    }


def _process_and_add_packages(
    conda_lock_data: dict[str, Any],
    pixi_data: dict[str, dict[str, Any]],
    repodata: dict[str, dict[str, Any]],
    env_name: str,
    platforms: list[str],
) -> None:
    """Process and add both conda and PyPI packages to the conda-lock data."""
    # Process conda packages
    logging.info("Processing conda packages for environment '%s'", env_name)
    conda_packages = process_conda_packages(pixi_data, repodata, env_name)
    conda_lock_data["package"].extend(conda_packages)
    logging.info("Added %d conda packages to conda-lock data", len(conda_packages))

    # Process PyPI packages
    logging.info("Processing PyPI packages for environment '%s'", env_name)
    pypi_packages, has_pypi_packages = process_pypi_packages(
        pixi_data,
        platforms,
        env_name,
    )

    # Check if we have PyPI packages but no pip
    if has_pypi_packages:
        _validate_pip_in_conda_packages(conda_packages)

    conda_lock_data["package"].extend(pypi_packages)
    logging.info("Added %d PyPI package entries to conda-lock data", len(pypi_packages))


def _validate_pip_in_conda_packages(conda_packages: list[dict[str, Any]]) -> None:
    pip_included = any(
        pkg.get("name") == "pip" and pkg.get("manager") == "conda"
        for pkg in conda_packages
    )
    if not pip_included:
        msg = "❌ PyPI packages are present but no pip package found in conda packages. Please ensure that pip is included in your pixi.lock file."
        raise ValueError(msg)


def get_environment_names(pixi_data: dict[str, Any]) -> list[str]:
    """Get all environment names from pixi.lock data."""
    return list(pixi_data.get("environments", {}).keys())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert pixi.lock to conda-lock.yml")
    parser.add_argument("pixi_lock", type=Path, help="Path to pixi.lock file")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output directory for conda-lock files (default: current directory)",
    )
    parser.add_argument(
        "--environment",
        "-e",
        help="Specific environment to convert (default: convert all environments)",
    )
    parser.add_argument(
        "--repodata-dir",
        type=Path,
        help="Path to repodata cache directory",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def _prepare_output_directory(output_path: Path | None) -> Path:
    """Prepare the output directory."""
    output_dir = output_path if output_path else Path(".")
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
    logging.info("Output directory: %s", output_dir)
    return output_dir


def _determine_environments_to_process(
    pixi_data: dict[str, Any],
    specified_env: str | None,
) -> list[str]:
    """Determine which environments to process."""
    env_names = get_environment_names(pixi_data)
    logging.info("Found environments in pixi.lock: %s", env_names)

    if specified_env:
        if specified_env not in env_names:
            msg = f"Environment '{specified_env}' not found in pixi.lock"
            raise ValueError(msg)
        env_names = [specified_env]
        logging.info("Converting only environment: %s", specified_env)
    else:
        logging.info("Converting all environments: %s", env_names)

    return env_names


def _process_environments(
    env_names: list[str],
    pixi_data: dict[str, Any],
    repodata: dict[str, dict[str, Any]],
    output_dir: Path,
) -> None:
    """Process each environment and generate conda-lock files."""
    for env_name in env_names:
        logging.info("Processing environment: %s", env_name)
        conda_lock_data = convert_env_to_conda_lock(pixi_data, repodata, env_name)

        # Determine output filename
        output_file = _get_output_filename(output_dir, env_name)

        logging.info(
            "Writing conda-lock file for environment '%s' to: %s",
            env_name,
            output_file,
        )
        write_yaml_file(output_file, conda_lock_data)
        logging.info(
            "Successfully converted environment '%s' to %s",
            env_name,
            output_file,
        )

    logging.info("Conversion complete for all requested environments")


def _get_output_filename(output_dir: Path, env_name: str) -> Path:
    """Get the output filename for a given environment."""
    return (
        output_dir / "conda-lock.yml"
        if env_name == "default"
        else output_dir / f"{env_name}.conda-lock.yml"
    )


def main() -> int:  # pragma: no cover
    """Main function to convert pixi.lock to conda-lock.yml."""
    args = _parse_args()
    setup_logging(args.verbose)

    logging.info("Starting pixi.lock to conda-lock.yml conversion")
    logging.info("Input file: %s", args.pixi_lock)

    if not args.pixi_lock.exists():
        logging.error("Error: %s does not exist", args.pixi_lock)
        return 1

    # Determine output directory
    output_dir = _prepare_output_directory(args.output)

    try:
        # Load repodata and pixi.lock file
        repodata = find_and_load_repodata_files(args.repodata_dir)
        pixi_data = read_yaml_file(args.pixi_lock)

        # Process environments
        env_names = _determine_environments_to_process(pixi_data, args.environment)
        _process_environments(
            env_names,
            pixi_data,
            repodata,
            output_dir,
        )
        return 0  # noqa: TRY300
    except Exception:
        logging.exception("Error during conversion: %s")
        return 1


if __name__ == "__main__":
    sys.exit(main())
