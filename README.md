# Application Download

This tool can be used to maintain a version file (eventually also an application file) for a given application.

The version file is a YAML file that contains the version number of the application.
The version file respect the schema describe in application.md and provided in application_download/application-schema.json.

The application file is also a YAML file that contains how to download and install the application.
This is a simple key value file with the application as key and the version as value.

## Install

```bash
pip install application-download
```

## Usage

```bash
application-download --help
```

## Contributing

Install the pre-commit hooks:

```bash
pip install pre-commit
pre-commit install --allow-missing-config
```
