# Security

## API keys

This project uses a bring-your-own-key model. Never commit an Anthropic API key
or include one in screenshots, issues, sample reports, or source files.

Use one of these methods:

- a GitHub Codespaces secret named `ANTHROPIC_API_KEY`
- a local `.env` file copied from `.env.example`

The `.env` file, Streamlit secrets, generated reports, and local cache are
excluded by `.gitignore`.

## Reporting a vulnerability

Do not open a public issue containing credentials or sensitive information.
Revoke any exposed API key immediately and create a replacement.
