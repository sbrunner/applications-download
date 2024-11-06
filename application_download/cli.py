#!/usr/bin/env python3

import argparse
import json
import os
import pkgutil
import subprocess  # nosec
import sys
import tarfile
import urllib
import urllib.parse
from glob import glob
from io import BytesIO
from typing import Any, Optional, cast

import jsonschema_validator
import requests
import ruamel.yaml
import yaml

from application_download import applications_definition


def main() -> None:
    """Download applications from GitHub releases or any other URLs to the ~/.local/bin folder."""
    argparser = argparse.ArgumentParser(
        description="""Download applications from GitHub releases or any other URLs to the ~/.local/bin
            folder.
            Based on tow files, the first contains the information about from where to download the
            applications,
            how to extract the application from the archive, and the executable name.
            The second file contains the versions of the applications to download,
            this file is usually updated by Renovate."""
    )
    argparser.add_argument("--applications", help="The file containing the applications to download")
    argparser.add_argument(
        "--versions", help="The file containing the versions of the applications to download"
    )
    argparser.add_argument("--name", help="The name of the application to download")
    argparser.add_argument(
        "--version", help="The version of the application to download, to be used with --name"
    )
    argparser.add_argument("--list", action="store_true", help="List the applications to download")
    argparser.add_argument(
        "--installed", action="store_true", help="List the installed applications versions"
    )

    args = argparser.parse_args()

    applications = _load_applications(args.applications)

    if args.list:
        versions = _load_versions(args.versions)
        for key, app in applications.items():
            if args.name is None or args.name == key:
                version = f" ({versions[key]})" if key in versions else ""
                print(f"{key}{version}: {app['description']}")
        sys.exit(0)

    if args.installed:
        reversed_applications = {v["to-file-name"]: k for k, v in applications.items()}
        for version_filename in glob(os.path.join(_CONFIG_FOLDER, "*-version-*")):
            name, version = os.path.basename(version_filename).split("-version-", 1)
            app_name = reversed_applications[name]
            if args.name is None or args.name == app_name:
                print(f"{app_name}: {version}")
        sys.exit(0)

    if args.version is not None:
        assert args.name is not None
        _download_applications(applications, {args.name: args.version})
        sys.exit(0)

    versions = _load_versions(args.versions)

    if args.name is not None:
        _download_applications(applications, {args.name: versions[args.name]})
        sys.exit(0)

    _download_applications(applications, versions)


def _validate_applications(
    applications_data: str, application_filename: str, schema: dict[str, Any]
) -> applications_definition.ApplicationsConfiguration:
    """Validate the applications configuration."""
    ru_yaml = ruamel.yaml.YAML()
    applications = ru_yaml.load(applications_data)  # nosec

    errors, _ = jsonschema_validator.validate(application_filename, applications, schema)
    if errors:
        sys.stderr.write("\n".join(errors))
        sys.stderr.write("\n")
        sys.exit(1)

    return cast(applications_definition.ApplicationsConfiguration, applications)


_CONFIG_FOLDER = os.path.join(
    os.getenv("XDG_CONFIG_HOME") or os.path.expanduser(os.path.join("~", ".config")), "application_download"
)


def _load_applications(applications_file: Optional[str]) -> applications_definition.ApplicationsConfiguration:
    """Load the applications from the file."""
    applications: applications_definition.ApplicationsConfiguration = {}
    schema_data = pkgutil.get_data("application_download", "applications-schema.json")
    assert schema_data is not None
    schema = json.loads(schema_data)

    # Load the applications from the file provided by the package
    package_applications_data = pkgutil.get_data("application_download", "applications.yaml")
    assert package_applications_data is not None
    package_applications = _validate_applications(
        package_applications_data.decode(), "<application_download>/applications.yaml", schema
    )
    applications.update(package_applications)

    # Load the applications from the file provided by the user
    user_applications_file = os.path.join(_CONFIG_FOLDER, "applications.yaml")
    if os.path.exists(user_applications_file):
        with open(user_applications_file, encoding="utf-8") as config_file:
            user_applications_data = config_file.read()
        user_applications = _validate_applications(user_applications_data, user_applications_file, schema)
        applications.update(user_applications)

    if applications_file is None:
        if os.path.exists("applications.yaml"):
            with open("applications.yaml", encoding="utf-8") as config_file:
                user_applications_data = config_file.read()
            user_applications = _validate_applications(user_applications_data, "applications.yaml", schema)
            applications.update(user_applications)
    else:
        with open(applications_file, encoding="utf-8") as config_file:
            user_applications_data = config_file.read()
        user_applications = _validate_applications(user_applications_data, applications_file, schema)
        applications.update(user_applications)

    return applications


def _load_versions(versions_filename: Optional[str] = None) -> dict[str, str]:
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

    versions_data = pkgutil.get_data("application_download", "versions.yaml")
    assert versions_data is not None
    return cast(dict[str, str], yaml.load(versions_data, Loader=yaml.SafeLoader))


def download_all_applications() -> None:
    """Download all the applications defined in the c2cciutils package."""
    applications = _load_applications(None)
    versions = _load_versions("applications-versions.yaml")
    _download_applications(applications, versions)


def download_application(
    name: str, versions_filename: Optional[str] = None, application_filename: Optional[str] = None
) -> None:
    """Download the applications defined in the c2cciutils package."""
    applications = _load_applications(application_filename)
    versions = _load_versions(versions_filename)
    _download_applications(applications, {name: versions[name]})


def _download_applications(
    applications: applications_definition.ApplicationsConfiguration, versions: dict[str, str]
) -> None:
    """Download the versions of applications specified in the configuration."""
    bin_path = os.path.join(os.environ["HOME"], ".local", "bin")
    if not os.path.exists(bin_path):
        os.makedirs(bin_path)

    for key, version in versions.items():
        if key not in applications:
            sys.stderr.write(f"Application {key} not found in the configuration\n")
            sys.exit(1)
        app = applications[key]

        # The versions file is used to don't re-download an already downloaded application
        version_file = os.path.join(_CONFIG_FOLDER, f"{app['to-file-name']}-version-{version}")
        if not os.path.exists(version_file):
            print(f"Download {app['to-file-name']} version {version}")
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
                with open(
                    os.path.join(bin_path, additional_filename), "w", encoding="utf-8"
                ) as additional_file:
                    additional_file.write(additional_content)

            for command in app.get("finish-commands", []):
                subprocess.run(command, check=True, cwd=bin_path)  # nosec

            if "version-command" in app:
                subprocess.run(app["version-command"], check=True, cwd=bin_path)  # nosec

            if app.get("remove-after-success", False):
                os.remove(os.path.join(bin_path, app["to-file-name"]))

            # Remove ald version files
            for filename in glob(os.path.join(_CONFIG_FOLDER, f"{app['to-file-name']}-version-*")):
                os.remove(filename)
            # Create new version file
            with open(version_file, "w", encoding="utf-8") as _:
                pass


if __name__ == "__main__":
    main()
