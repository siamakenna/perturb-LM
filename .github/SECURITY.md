# Security Policy

## Supported Version

Security fixes are applied to the current `main` branch.

## Reporting a Vulnerability

Do not open a public issue containing credentials, exploitable details, private paths, restricted data, or sensitive metadata. Use **Security → Report a vulnerability** in GitHub.

Include the affected file, route, command, or dependency; impact; minimal reproduction; whether private data may have been exposed; and suggested remediation when known.

## Secrets and Data

Never commit tokens, passwords, `.env` files, cloud credentials, raw datasets, row-level results, embeddings, model caches, or private filesystem locations. Revoke and rotate an exposed credential immediately; deleting it in a later commit is not sufficient.
