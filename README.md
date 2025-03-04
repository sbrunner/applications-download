# Applications Download

This tool can be used to maintain a version file (eventually also an application file) for a given application.

The version file is a YAML file that contains the version number of the application.
The version file respect the schema describe in application.md and provided in applications_download/application-schema.json.

The application file is also a YAML file that contains how to download and install the application.
This is a simple key value file with the application as key and the version as value.

## Install

```bash
pip install applications-download
```

## Usage

```bash
applications-download --help
```

## Applications configuration

In case some executables or applications from GitHub releases or any other URLs are required on the CI host
and are not handled by any dependency manager, we provide a set of tools to install them and manage upgrades
through Renovate.

Create an application file (e.-g. `applications.yaml`) with:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/sbrunner/applications-download/refs/heads/<version>/applications_download/applications-schema.json

# Application from GitHub release
<organization>/<project>:
  get-file-name: <file name present in the release>
  to-file-name: <The file name you want to create in ~/.local/bin>
  finish-command: # The command you want to run after the file is downloaded
    - - chmod # To be executable (usually required)
      - +x
      - <to-file-name>
    - - <to-file-name> # Print the version of the application
      - --version
# Application from GitHub release in a tar file (or tar.gz)
<organization>/<project>:
  get-file-name: <file name present in the release>
  type: tar
  tar-file-name: <The file name available in the tar file>
  to-file-name: <The file name you want to create in ~/.local/bin>
  finish-command: [...] # The command you want to run after the file is downloaded
# Application from an URL
<application reference name>:
  url-pattern: <The URL used to download the application>
  to-file-name: <The file name you want to create in ~/.local/bin>
  finish-command: [...] # The command you want to run after the file is downloaded
```

In the attributes `url-pattern`, `get-file-name` you can use the following variables:

- `{version}`: The version of the application present in the version file.
- `{version_quote}`: The URL encoded version.
- `{short_version}`: The version without the `v` prefix.

The `applications-versions.yaml` file is a map of applications and their versions.

Add in your Renovate configuration:

```json5
  regexManagers: [
    {
      fileMatch: ['^applications-versions.yaml$'],
      matchStrings: [
        '(?<depName>[^\\s]+): (?<currentValue>[^\\s]+) # (?<datasource>[^\\s]+)',
      ],
    },
  ],
```

Now you need to call `c2cciutils-download-applications --applications-file=applications.yaml --versions-file=applications-version.yaml`
to install required applications on CI host before using them (an already installed application is installed only if needed).

## Contributing

Install the pre-commit hooks:

```bash
pip install pre-commit
pre-commit install --allow-missing-config
```
