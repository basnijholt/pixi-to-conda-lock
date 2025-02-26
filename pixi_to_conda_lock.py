#!/usr/bin/env python3
"""Convert a pixi.lock file to a conda-lock.yml file using repodata.

This script reads a pixi.lock file and generates a conda-lock.yml file with the same
package information, using repodata to extract accurate package metadata.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from rattler.lock import CondaLockedPackage, LockFile, PypiLockedPackage

if TYPE_CHECKING:
    from rattler.platform import Platform
    from rattler.repo_data import RepoDataRecord


# Keep setup_logging and write_yaml_file as they are.
# No changes needed for setup_logging()
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


def write_yaml_file(file_path: Path, data: dict[str, Any]) -> None:
    """Write data to a YAML file."""
    logging.debug("Writing YAML file: %s", file_path)
    with open(file_path, "w") as f:
        yaml.dump(data, f, sort_keys=False)
    logging.debug("Successfully wrote YAML file: %s", file_path)


def create_conda_package_entry(
    package: CondaLockedPackage,
    platform: Platform,
    repodata_record: RepoDataRecord,
) -> dict[str, Any]:
    """Create a conda package entry for conda-lock.yml from repodata."""
    logging.debug(
        "Creating conda package entry from repodata for: %s",
        package.location,
    )

    package_entry = {
        "name": repodata_record.name.source,
        "version": str(repodata_record.version),
        "manager": "conda",
        "platform": str(platform),
        "dependencies": _requires_dist_to_dependencies(package.package_record.depends),
        "url": package.location,
        "hash": {
            "md5": repodata_record.md5.hex(),
            "sha256": repodata_record.sha256.hex(),
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


def create_pypi_package_entry(
    package: PypiLockedPackage,
    platform: Platform,
) -> dict[str, Any]:
    """Create a conda-lock package entry from a PypiLockedPackage."""
    hashes = package.hashes
    if not hashes:
        msg = f"Package {package.name} has no hashes"
        raise ValueError(msg)
    return {
        "name": package.name,
        "version": str(package.version),
        "manager": "pip",
        "platform": str(platform),
        "dependencies": _requires_dist_to_dependencies(package.requires_dist),
        "url": package.location,
        "hash": {"sha256": hashes.sha256.hex()},
        "category": "main",
        "optional": False,
    }


def _requires_dist_to_dependencies(requires_dist: list[str]) -> dict[str, str]:
    """Convert package requirements from 'requires_dist' format to conda-lock format."""
    dependencies = {}
    for requirement in requires_dist:
        # Split by first occurrence of any version specifier
        match = re.match(r"([^<>=!~]+)(.+)?", requirement)
        if match:
            package_name = match.group(1).strip()
            version_constraint = match.group(2) or "*"
            dependencies[package_name] = version_constraint.strip()

    return dependencies


def create_conda_lock_metadata(
    platforms: list[Platform],
    channels: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create metadata section for conda-lock.yml."""
    logging.debug("Creating conda-lock metadata")
    metadata = {
        "content_hash": {
            str(platform): "generated-from-pixi-lock" for platform in platforms
        },
        "channels": channels,
        "platforms": [str(p) for p in platforms],
        "sources": ["pixi.lock"],
    }
    logging.debug("Created conda-lock metadata with %d platforms", len(platforms))
    return metadata


def convert_env_to_conda_lock(
    lock_file: LockFile,
    env_name: str,
) -> dict[str, Any]:
    """Convert a lock file to a conda-lock dict for a specific environment."""
    logging.info("Converting pixi lock file to conda-lock format for %s", env_name)
    conda_lock_data: dict[str, Any] = {
        "version": 1,
        "metadata": {},
        "package": [],
    }

    env = lock_file.environment(env_name)
    if env is None:
        msg = f"Environment '{env_name}' not found in pixi.lock file"
        raise ValueError(msg)
    platforms = env.platforms()
    channels = [
        {"url": str(c).replace("https://conda.anaconda.org/", ""), "used_env_vars": []}
        for c in env.channels()
    ]
    conda_lock_data["metadata"] = create_conda_lock_metadata(platforms, channels)
    has_pypi_packages: dict[str, bool] = {platform: False for platform in platforms}
    has_pip: dict[str, bool] = {platform: False for platform in platforms}
    for platform in platforms:
        conda_repodata = env.conda_repodata_records_for_platform(platform)
        repo_mapping = (
            {record.url: record for record in conda_repodata}
            if conda_repodata is not None
            else {}
        )
        for package in env.packages(platform):
            if isinstance(package, CondaLockedPackage):
                url = package.location
                repodata_record = repo_mapping[url]
                conda_package_entry = create_conda_package_entry(
                    package,
                    platform,
                    repodata_record,
                )
                conda_lock_data["package"].append(conda_package_entry)
                if repodata_record.name.source == "pip":
                    has_pip[platform] = True
                continue
            assert isinstance(package, PypiLockedPackage)
            has_pypi_packages[platform] = True
            pypi_package_entry = create_pypi_package_entry(package, platform)
            conda_lock_data["package"].append(pypi_package_entry)
    _validate_pip_in_conda_packages(has_pypi_packages, has_pip)
    return conda_lock_data


def _validate_pip_in_conda_packages(
    has_pypi_packages: dict[str, bool],
    has_pip: dict[str, bool],
) -> None:
    for platform, has_pypi in has_pypi_packages.items():
        if has_pypi and not has_pip[platform]:
            msg = (
                "❌ PyPI packages are present but no pip package found in conda packages."
                " Please ensure that pip is included in your pixi.lock file."
            )
            raise ValueError(msg)


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
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


def _get_output_filename(output_dir: Path, env_name: str) -> Path:
    """Get the output filename for a given environment."""
    return (
        output_dir / "conda-lock.yml"
        if env_name == "default"
        else output_dir / f"{env_name}.conda-lock.yml"
    )


def main() -> int:
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
        lock_file = LockFile.from_path(args.pixi_lock)
        env_names = (
            [args.environment]
            if args.environment
            else [name for name, _ in lock_file.environments()]
        )

        for env_name in env_names:
            conda_lock_data = convert_env_to_conda_lock(lock_file, env_name)
            output_file = _get_output_filename(output_dir, env_name)
            write_yaml_file(output_file, conda_lock_data)
            logging.info(
                "Successfully converted environment '%s' to %s",
                env_name,
                output_file,
            )

    except Exception:
        logging.exception("Error during conversion")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
