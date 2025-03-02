#!/usr/bin/env python3

import argparse
from pathlib import Path

import applications_download


def main() -> None:
    """Download applications from GitHub releases or any other URLs to the ~/.local/bin folder."""
    argparser = argparse.ArgumentParser(
        description="""Download applications from GitHub releases or any other URLs to the ~/.local/bin
            folder.
            Based on tow files, the first contains the information about from where to install the
            applications,
            how to extract the application from the archive, and the executable name.
            The second file contains the versions of the applications to install,
            this file is usually updated by Renovate.""",
    )
    argparser.add_argument(
        "--applications",
        type=Path,
        help="The file containing the applications to install",
    )
    argparser.add_argument(
        "--versions",
        type=Path,
        help="The file containing the versions of the applications to install",
    )
    subparsers = argparser.add_subparsers(dest="cmd")

    list_parser = subparsers.add_parser("list", help="List the available applications to install")
    list_parser.add_argument("--name", help="The name of the application to list")

    install_parser = subparsers.add_parser("install", help="Install applications")
    install_parser.add_argument("--name", help="The name of the application to install")
    install_parser.add_argument(
        "--version",
        help="The version of the application to download, to be used with --name",
    )
    install_parser.add_argument("--all", action="store_true", help="Install all the applications")

    installed_parser = subparsers.add_parser("installed", help="List the installed applications versions")
    installed_parser.add_argument("--name", help="The name of the application to list")

    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall the installed application")
    uninstall_parser.add_argument("name", help="The name of the application to uninstall")

    subparsers.add_parser("update", help="Update the installed applications")

    args = argparser.parse_args()

    applications = applications_download.Applications(args.applications, args.versions)

    match args.cmd:
        case "list":
            applications.list(args.name)
        case "install":
            if args.name is not None:
                applications.install(args.name, args.version)
            elif args.all:
                applications.install_all()
        case "installed":
            for application, version in applications.installed.items():
                if args.name is None or args.name == application:
                    print(f"{application}: {version}")
        case "update":
            applications.update_all()
        case "uninstall":
            applications.uninstall(args.name)
        case _:
            argparser.print_help()


if __name__ == "__main__":
    main()
