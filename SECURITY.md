# Security

## API keys

This project uses a bring-your-own-key approach. Never share your Anthropic API key or include it in screenshots, issues, sample reports, or source files.

Use one of these methods:

- a GitHub Codespaces secret named `ANTHROPIC_API_KEY`
- a local `.env` file copied from `.env.example`

The `.env` file, Streamlit secrets, generated reports, and local cache are excluded by `.gitignore`.

## Reporting a vulnerability

Don’t post public issues with credentials or sensitive info. Revoke any exposed API keys right away and get a new one.
