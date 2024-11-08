#!/usr/bin/env python3

import argparse
import sys

import applications_download


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

    applications = applications_download.load_applications(args.applications)

    if args.list:
        versions = applications_download.load_versions(args.versions)
        for key, app in applications.items():
            if args.name is None or args.name == key:
                version = f" ({versions[key]})" if key in versions else ""
                print(f"{key}{version}: {app['description']}")
        sys.exit(0)

    if args.installed:
        installed_applications = applications_download.get_installed_applications()
        for application, version in installed_applications.items():
            if args.name is None or args.name == application:
                print(f"{application}: {version}")
        sys.exit(0)

    if args.version is not None:
        assert args.name is not None
        applications_download.download_applications(applications, {args.name: args.version})
        sys.exit(0)

    versions = applications_download.load_versions(args.versions)

    if args.name is not None:
        applications_download.download_applications(applications, {args.name: versions[args.name]})
        sys.exit(0)

    applications_download.download_applications(applications, versions)


if __name__ == "__main__":
    main()
