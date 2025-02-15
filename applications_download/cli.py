#!/usr/bin/env python3

import argparse
import sys

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
            this file is usually updated by Renovate."""
    )
    argparser.add_argument("--applications", help="The file containing the applications to install")
    argparser.add_argument(
        "--versions", help="The file containing the versions of the applications to install"
    )
    subparsers = argparser.add_subparsers(dest="cmd")

    subparsers.add_parser("list", help="List the available applications to install")

    install_parser = subparsers.add_parser("install", help="Install applications")
    install_parser.add_argument("--name", help="The name of the application to install")
    install_parser.add_argument(
        "--version", help="The version of the application to download, to be used with --name"
    )
    install_parser.add_argument("--all", action="store_true", help="Install all the applications")

    subparsers.add_parser("installed", help="List the installed applications versions")

    uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall the installed application")
    uninstall_parser.add_argument("name", help="The name of the application to uninstall")

    subparsers.add_parser("update", help="Update the installed applications")

    args = argparser.parse_args()

    applications = applications_download.load_applications(args.applications)
    versions = applications_download.load_versions(args.versions)

    match args.cmd:
        case "list":
            for key, app in applications.items():
                if args.name is None or args.name == key:
                    version = f" ({versions[key]})" if key in versions else ""
                    print(f"{key}{version}: {app['description']}")
        case "install":
            if args.version is not None:
                if args.name is None:
                    sys.stderr.write("The --version argument must be used with the --name argument\n")
                    sys.exit(1)
                applications_download.install_all_applications(applications, {args.name: args.version})
            elif args.name is not None:
                if args.name not in versions:
                    sys.stderr.write(f"The version of {args.name} is not defined in the versions file\n")
                    sys.exit(1)
                applications_download.install_all_applications(applications, {args.name: versions[args.name]})
            elif args.all:
                applications_download.install_all_applications(applications, versions)
        case "installed":
            installed_applications = applications_download.get_installed_applications()
            for application, version in installed_applications.items():
                if args.name is None or args.name == application:
                    print(f"{application}: {version}")
        case "update":
            applications_download.update_all_applications(applications, versions)
        case "uninstall":
            applications_download.uninstall_application(applications, args.name)
        case _:
            argparser.print_help()


if __name__ == "__main__":
    main()
