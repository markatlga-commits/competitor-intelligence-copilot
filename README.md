# Competitive Intelligence Copilot

The Competitive Intelligence Copilot is a Python and Streamlit app that analyzes a company’s details, identifies three key competitors, and generates an executive report based on reliable sources.

The report highlights key product updates, partnerships, leadership changes, customer segments, differentiators, threats, and strategic opportunities. Sections that lack supporting information are left out instead of replaced with generic language. Narrative sections are only included when the research response is complete, and the report text is kept to full sentences.

## What it delivers

- an executive summary and market overview supported by evidence
- three top competitors, either direct or emerging
- how competitors are positioned and their target customers
- key differences and current strategic indicators
- threats and opportunities validated by data
- common themes across competitors, gaps in the market, recommendations, and items to monitor
- source-supported JSON data and a downloadable executive PDF

## Technology

- Python 3.12
- Streamlit
- Anthropic Claude API
- Pydantic
- ReportLab

## GitHub Codespaces setup

### 1. Add the API key

In the repository:

1. Open **Settings**
2. Select **Secrets and variables**
3. Select **Codespaces**
4. Create a repository secret named `ANTHROPIC_API_KEY`
5. Paste your Anthropic API key as the value

Never commit an API key to the repository.

### 2. Create the Codespace

Create a Codespace from the repository's `main` branch. The included development-container configuration installs the required dependencies and forwards Streamlit on port `8501`.

### 3. Validate the environment

```bash
python scripts/check_setup.py
```

### 4. Launch the application

```bash
python -m streamlit run app.py
```

If the application does not open automatically, open port `8501` from the Codespaces **Ports** panel.

## Local setup

```bash
git clone https://github.com/markatlga-commits/competitor-intelligence-copilot.git
cd competitor-intelligence-copilot

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cp .env.example .env
```

Add your API key to `.env`, then run:

```bash
python scripts/check_setup.py
python -m streamlit run app.py
```

## Research depths

| Profile | Description |
|---|---|
| Quick | A straightforward assessment with two current signals for each competitor. |
| Balanced | Additional evidence and strategic detail |
| Deep | A broader review for complex strategic assessments |

## Responsible use

This application uses publicly available web information. As a result, the results can sometimes be incomplete or delayed, depending on the sources. Keep in mind that public signals don’t confirm private company plans.

## Security

Each person provides their own Anthropic API key. See [SECURITY.md](SECURITY.md) for key-handling guidance.
