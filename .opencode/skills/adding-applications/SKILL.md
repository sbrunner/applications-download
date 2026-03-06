---
name: adding-applications
description: Adds or updates application entries in applications_download/applications.yaml and applications_download/versions.yaml. Use when adding a new downloadable app, changing release asset names, or aligning install steps with a GitHub release.
---

# Adding Applications

## Quick Start

- Read `applications_download/applications.yaml` and `applications_download/versions.yaml` to mirror existing patterns.
- Fetch the latest GitHub release assets with `gh release view --repo <org>/<repo> --json tagName,assets`.
- Pick the Linux amd64 asset name that matches the repo pattern and set `get-file-name` or `url-pattern`.
- Add or update the `description`, `to-file-name`, and any `finish-commands` or `version-command`.
- Update the version in `applications_download/versions.yaml` with the release tag and `# github-releases` comment.

## GitHub Release Assets

- Prefer `get-file-name` for GitHub releases; use `url-pattern` only when assets are hosted outside GitHub.
- Use `{version}`, `{short_version}`, or `{version_quote}` only when the asset name uses those placeholders.
- Use `type: tar` and `tar-file-name` only when the release asset is an archive containing the binary.

## Common Patterns

- **Linux binary**: `get-file-name: <name>` then `finish-commands` with `chmod +x` and a version check.
- **Debian package**: `get-file-name: <name>.deb`, `to-file-name: <name>.deb`, `remove-after-success: true`, then `sudo dpkg --install <name>.deb`.
- **Jar wrapper**: `url-pattern` or `get-file-name` to `to-file-name: <app>.jar`, add `additional-files` wrapper script, and `chmod +x` it.
- **AppImage**: the `*.AppImage` assets are not yet supported.

## Validation Checklist

- Ensure `applications_download/applications.yaml` keys match `versions.yaml` keys.
- Confirm the asset exists in the latest GitHub release.
- Match `finish-commands` and `version-command` to the installed binary name.
