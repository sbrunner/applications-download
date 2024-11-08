"""
Application download main module.
"""

import json
import os
import pkgutil
import subprocess  # nosec
import sys
import tarfile
import urllib
import urllib.parse
from io import BytesIO
from typing import Optional, cast

import jsonschema_validator
import requests
import ruamel.yaml
import yaml

from applications_download import applications_definition

_CONFIG_FOLDER = os.path.join(
    os.getenv("XDG_CONFIG_HOME") or os.path.expanduser(os.path.join("~", ".config")), "applications_download"
)
_SCHEMA = None


def _validate_applications(
    applications_data: str, application_filename: str
) -> applications_definition.ApplicationsConfiguration:
    """Validate the applications configuration."""
    global _SCHEMA  # pylint: disable=global-statement

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

    return cast(applications_definition.ApplicationsConfiguration, applications)


def load_applications_data(
    applications_data: str, filename: str, applications: applications_definition.ApplicationsConfiguration
) -> None:
    """Load the applications from the file."""
    applications.update(_validate_applications(applications_data, filename))


def load_applications_file(
    applications_filename: str, applications: applications_definition.ApplicationsConfiguration
) -> None:
    """Load the applications from the file."""
    with open(applications_filename, encoding="utf-8") as config_file:
        applications_data = config_file.read()
    load_applications_data(applications_data, applications_filename, applications)


def load_applications(applications_file: Optional[str]) -> applications_definition.ApplicationsConfiguration:
    """Load the applications from the file."""
    applications: applications_definition.ApplicationsConfiguration = {}

    # Load the applications from the file provided by the package
    package_applications_data = pkgutil.get_data("applications_download", "applications.yaml")
    assert package_applications_data is not None
    load_applications_data(
        package_applications_data.decode(), "<applications_download>/applications.yaml", applications
    )

    # Load the applications from the file provided by the user
    user_applications_file = os.path.join(_CONFIG_FOLDER, "applications.yaml")
    if os.path.exists(user_applications_file):
        load_applications_file(user_applications_file, applications)

    if applications_file is None:
        if os.path.exists("applications.yaml"):
            load_applications_file("applications.yaml", applications)
    else:
        load_applications_file(applications_file, applications)

    return applications


def load_versions(versions_filename: Optional[str] = None) -> dict[str, str]:
    """Load the versions from the file."""
    if versions_filename is not None:
        with open(versions_filename, encoding="utf-8") as version_file:
            return cast(dict[str, str], yaml.load(version_file, Loader=yaml.SafeLoader))

    if os.path.exists("applications-versions.yaml"):
        with open("applications-versions.yaml", encoding="utf-8") as version_file:
            return cast(dict[str, str], yaml.load(version_file, Loader=yaml.SafeLoader))

    config_filename = os.path.join(_CONFIG_FOLDER, "applications-versions.yaml")
    if os.path.exists(config_filename):
        with open(config_filename, encoding="utf-8") as version_file:
            return cast(dict[str, str], yaml.load(version_file, Loader=yaml.SafeLoader))

    versions_data = pkgutil.get_data("applications_download", "versions.yaml")
    assert versions_data is not None
    return cast(dict[str, str], yaml.load(versions_data, Loader=yaml.SafeLoader))


def download_all_applications() -> None:
    """Download all the applications defined in the c2cciutils package."""
    applications = load_applications(None)
    versions = load_versions("applications-versions.yaml")
    download_applications(applications, versions)


def download_application(
    name: str, versions_filename: Optional[str] = None, application_filename: Optional[str] = None
) -> None:
    """Download the applications defined in the c2cciutils package."""
    applications = load_applications(application_filename)
    versions = load_versions(versions_filename)
    download_applications(applications, {name: versions[name]})


def download_applications(
    applications: applications_definition.ApplicationsConfiguration, versions: dict[str, str]
) -> None:
    """Download the versions of applications specified in the configuration."""
    bin_path = os.path.join(os.environ["HOME"], ".local", "bin")
    if not os.path.exists(bin_path):
        os.makedirs(bin_path)

    installed_applications = get_installed_applications()
    dirty = False

    for key, version in versions.items():
        if key not in applications:
            sys.stderr.write(f"Application {key} not found in the configuration\n")
            sys.exit(1)
        app = applications[key]

        # If the package is already at the right version don't re-download
        if key in installed_applications and installed_applications[key] == version:
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
                extracted_file = tar.extractfile(app["tar-file-name"])
                assert extracted_file is not None
                content = extracted_file.read()
        else:
            content = response.content

        with open(os.path.join(bin_path, app["to-file-name"]), "wb") as destination_file:
            destination_file.write(content)

        for additional_filename, additional_content in app.get("additional-files", {}).items():
            print(f"Create {additional_filename}")
            with open(os.path.join(bin_path, additional_filename), "w", encoding="utf-8") as additional_file:
                additional_file.write(additional_content)

        for command in app.get("finish-commands", []):
            subprocess.run(command, check=True, cwd=bin_path)  # nosec

        if "version-command" in app:
            subprocess.run(app["version-command"], check=True, cwd=bin_path)  # nosec

        if app.get("remove-after-success", False):
            os.remove(os.path.join(bin_path, app["to-file-name"]))

        installed_applications[key] = version
        dirty = True
    if dirty:
        if not os.path.exists(_CONFIG_FOLDER):
            os.makedirs(_CONFIG_FOLDER)
        with open(os.path.join(_CONFIG_FOLDER, "installed.yaml"), "w", encoding="utf-8") as installed_file:
            yaml.dump(installed_applications, installed_file)


def get_installed_applications() -> dict[str, str]:
    """List the installed applications."""
    installed_applications_filename = os.path.join(_CONFIG_FOLDER, "installed.yaml")
    if not os.path.exists(installed_applications_filename):
        return {}

    with open(installed_applications_filename, encoding="utf-8") as installed_file:
        return cast(dict[str, str], yaml.load(installed_file, Loader=yaml.SafeLoader))
