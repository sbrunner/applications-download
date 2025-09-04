"""Application download main module."""

import json
import os
import pkgutil
import subprocess  # nosec
import sys
import tarfile
import urllib
import urllib.parse
from io import BytesIO
from pathlib import Path
from typing import cast

import jsonschema_validator
import requests
import ruamel.yaml
import yaml

from applications_download import applications_definition

_XDG_CONFIG_HOME = os.getenv("XDG_CONFIG_HOME")
_CONFIG_FOLDER = (
    Path(_XDG_CONFIG_HOME) if _XDG_CONFIG_HOME else Path("~").expanduser() / ".config"
) / "applications_download"

_SCHEMA = None


def _validate_applications(
    applications_data: str,
    application_filename: str,
) -> applications_definition.ApplicationsConfiguration:
    """Validate the applications configuration."""
    global _SCHEMA  # pylint: disable=global-statement # noqa: PLW0603

    if _SCHEMA is None:
        schema_data = pkgutil.get_data("applications_download", "applications-schema.json")
        assert schema_data is not None
        _SCHEMA = json.loads(schema_data)

    ru_yaml = ruamel.yaml.YAML()
    applications = ru_yaml.load(applications_data)  # nosec

    errors, _ = jsonschema_validator.validate(application_filename, applications, _SCHEMA)
    if errors:
        sys.stderr.write("\n".join(errors))
        sys.stderr.write("\n")
        sys.exit(1)

    return cast("applications_definition.ApplicationsConfiguration", applications)


def _load_applications_data(
    applications_data: str,
    filename: str,
    applications: applications_definition.ApplicationsConfiguration,
) -> None:
    """Load the applications from the file."""
    applications.update(_validate_applications(applications_data, filename))


def _load_applications_file(
    applications_filename: Path,
    applications: applications_definition.ApplicationsConfiguration,
) -> None:
    """Load the applications from the file."""
    with applications_filename.open(encoding="utf-8") as config_file:
        applications_data = config_file.read()
    _load_applications_data(applications_data, str(applications_filename), applications)


def _load_applications(
    applications_file: Path | None = None,
    applications_url: str | None = None,
) -> applications_definition.ApplicationsConfiguration:
    """Load the applications from the file."""
    applications: applications_definition.ApplicationsConfiguration = {}

    # Load the applications from the file provided by the package
    package_applications_data = pkgutil.get_data("applications_download", "applications.yaml")
    assert package_applications_data is not None
    _load_applications_data(
        package_applications_data.decode(),
        "<applications_download>/applications.yaml",
        applications,
    )

    # Load the applications from the file provided by the user
    user_applications_file = _CONFIG_FOLDER / "applications.yaml"
    if user_applications_file.exists():
        _load_applications_file(user_applications_file, applications)

    if applications_file is None:
        applications_file = Path("applications.yaml")
    if applications_file.exists():
        _load_applications_file(applications_file, applications)

    if applications_url is not None:
        response = requests.get(  # nosec
            applications_url,
            timeout=int(os.environ.get("REQUESTS_TIMEOUT", "30")),
        )
        response.raise_for_status()
        _load_applications_data(response.text, applications_url, applications)

    return applications


def _load_versions(versions_filename: Path | None = None, versions_url: str | None = None) -> dict[str, str]:
    """Load the versions from the file."""
    if versions_filename is not None:
        with versions_filename.open(encoding="utf-8") as version_file:
            return cast("dict[str, str]", yaml.load(version_file, Loader=yaml.SafeLoader))

    if versions_url is not None:
        response = requests.get(  # nosec
            versions_url,
            timeout=int(os.environ.get("REQUESTS_TIMEOUT", "30")),
        )
        response.raise_for_status()
        return cast("dict[str, str]", yaml.load(response.text, Loader=yaml.SafeLoader))

    if Path("applications-versions.yaml").exists():
        with Path("applications-versions.yaml").open(encoding="utf-8") as version_file:
            return cast("dict[str, str]", yaml.load(version_file, Loader=yaml.SafeLoader))

    config_filename = _CONFIG_FOLDER / "applications-versions.yaml"
    if config_filename.exists():
        with config_filename.open(encoding="utf-8") as version_file:
            return cast("dict[str, str]", yaml.load(version_file, Loader=yaml.SafeLoader))

    versions_data = pkgutil.get_data("applications_download", "versions.yaml")
    assert versions_data is not None
    return cast("dict[str, str]", yaml.load(versions_data, Loader=yaml.SafeLoader))


class Applications:
    """Applications class."""

    def __init__(
        self,
        applications_path: Path | None = None,
        versions_path: Path | None = None,
        applications_url: str | None = None,
        versions_url: str | None = None,
    ) -> None:
        self.applications = _load_applications(applications_path, applications_url)
        self.versions = _load_versions(versions_path, versions_url)
        self.installed_path = _CONFIG_FOLDER / "installed.yaml"
        self.installed: dict[str, str] = {}
        if self.installed_path.exists():
            with self.installed_path.open(encoding="utf-8") as installed_file:
                self.installed = cast("dict[str, str]", yaml.load(installed_file, Loader=yaml.SafeLoader))

    def _save_status(self) -> None:
        if not _CONFIG_FOLDER.exists():
            _CONFIG_FOLDER.mkdir(parents=True)

        with self.installed_path.open("w", encoding="utf-8") as installed_file:
            yaml.dump(self.installed, installed_file)

    def list(self, name: str | None) -> None:
        """List the available applications."""
        for key, app in self.applications.items():
            if name is None or name == key:
                version = f" ({self.versions[key]})" if key in self.versions else ""
                print(f"{key}{version}: {app['description']}")

    def install_all(self) -> None:
        """Install all the applications."""
        self._install(self.versions)

    def install(self, name: str | None, version: str | None = None) -> None:
        """Install the application."""
        if name not in self.applications:
            sys.stderr.write(f"Application {name} not found in the configuration\n")
            sys.exit(1)
        if version is not None:
            self._install({name: version})
        else:
            if name not in self.versions:
                sys.stderr.write(f"The version of {name} is not defined in the versions file\n")
                sys.exit(1)
            self._install({name: self.versions[name]})

    def update_all(self) -> None:
        """Update all the applications."""
        versions = {key: version for key, version in self.versions.items() if key in self.installed}
        self._install(versions)

    def uninstall(self, name: str) -> None:
        """Uninstall the application."""
        if name not in self.applications:
            sys.stderr.write(f"Application {name} not found in the configuration\n")
            sys.exit(1)

        if name not in self.installed:
            sys.stderr.write(f"Application {name} not installed\n")
            sys.exit(1)

        app = self.applications[name]
        bin_path = Path(os.environ["HOME"]) / ".local" / "bin"
        application_file = bin_path / app["to-file-name"]
        if application_file.exists():
            application_file.unlink()
        del self.installed[name]
        self._save_status()

    def _install(self, versions: dict[str, str]) -> None:  # pylint: disable=too-many-locals
        """Download the versions of applications specified in the configuration."""
        bin_path = Path(os.environ["HOME"]) / ".local" / "bin"
        if not bin_path.exists():
            bin_path.mkdir(parents=True)

        for key, version in versions.items():
            if key not in self.applications:
                sys.stderr.write(f"Application {key} not found in the configuration\n")
                sys.exit(1)
            app = self.applications[key]

            # If the package is already at the right version don't re-download
            if key in self.installed and self.installed[key] == version:
                continue

            print(f"Download {key} version {version}")
            version_quote = urllib.parse.quote_plus(version)
            params = {
                "version": version,
                "version_quote": version_quote,
                "short_version": version.lstrip("v"),
            }
            response = requests.get(  # nosec
                app.get(
                    "url-pattern",
                    f"https://github.com/{key}/releases/download/{version_quote}/"
                    f"{app.get('get-file-name', '')}",
                ).format(**params),
                timeout=int(os.environ.get("REQUESTS_TIMEOUT", "30")),
            )
            response.raise_for_status()

            if app.get("type") == "tar":
                with tarfile.open(fileobj=BytesIO(response.content)) as tar:
                    extracted_file = tar.extractfile(app["tar-file-name"].format(**params))
                    assert extracted_file is not None
                    content = extracted_file.read()
            else:
                content = response.content

            with (bin_path / app["to-file-name"]).open("wb") as destination_file:
                destination_file.write(content)

            for additional_filename, additional_content in app.get("additional-files", {}).items():
                print(f"Create {additional_filename}")
                with (bin_path / additional_filename).open("w", encoding="utf-8") as additional_file:
                    additional_file.write(additional_content)

            for command in app.get("finish-commands", []):
                subprocess.run(command, check=True, cwd=bin_path)  # noqa: S603

            if "version-command" in app:
                subprocess.run(app["version-command"], check=True, cwd=bin_path)  # noqa: S603

            if app.get("remove-after-success", False):
                (bin_path / app["to-file-name"]).unlink()

            self.installed[key] = version

            self._save_status()
