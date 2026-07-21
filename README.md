# Competitive Intelligence Copilot

Competitive Intelligence Copilot is a Python and Streamlit application that
researches a company, identifies three strategically relevant competitors, and
produces a source-backed executive report.

The report emphasizes specific product moves, partnerships, leadership changes,
customer segments, differentiators, threats, and strategic openings. Unsupported sections are omitted rather than filled with generic language. Narrative fields are accepted only when the research response finishes without truncation, and report text is normalized to complete sentences.

## What it delivers

- an evidence-backed executive summary and market definition
- three ranked direct or emerging competitors
- competitor positioning and customer focus
- specific differentiators and current strategic signals
- evidence-backed threats and opportunities
- cross-competitor themes, whitespace, recommendations, and watch items
- source-backed JSON and a downloadable executive PDF

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

Create a Codespace from the repository's `main` branch. The included
development-container configuration installs the required dependencies and
forwards Streamlit on port `8501`.

### 3. Validate the environment

```bash
python scripts/check_setup.py
```

### 4. Launch the application

```bash
python -m streamlit run app.py
```

If the application does not open automatically, open port `8501` from the
Codespaces **Ports** panel.

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
| Quick | A concise assessment with two current signals per competitor |
| Balanced | Additional evidence and strategic detail |
| Deep | A broader review for complex strategic assessments |

## Responsible use

The application relies on public web information. Results may be incomplete,
delayed, or affected by source availability. Public signals do not confirm
private company roadmaps.

## Security

Each user provides their own Anthropic API key. See [SECURITY.md](SECURITY.md)
for key-handling guidance.
