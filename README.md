# Canadian Health Monitor

This is a beginner-friendly Python project that reads Canadian health-related RSS and Atom feeds, filters for relevant digital health topics, and creates a simple weekly digest.

Right now, the project runs locally on your computer. It does not send email, post to Slack, summarize with AI, or impersonate anyone.

## What It Does

The script:

1. Reads feed sources from `sources.json`
2. Fetches RSS and Atom feeds
3. Filters items for relevant Canadian health monitor topics
4. Prints matched items in the terminal
5. Creates `digest.xml`
6. Creates a Markdown archive in `archives/`

## Files

### `sources.json`

This file is the project's feed list and keyword settings.

It contains:

- official Canadian health sources
- privacy and cybersecurity sources
- general news sources
- keywords used for filtering

### `generate_digest.py`

This is the main Python script.

It reads `sources.json`, fetches feeds, filters relevant items, creates `digest.xml`, and saves a weekly Markdown archive.

### `digest.xml`

This is the generated RSS file.

Later, Slack can subscribe to this RSS feed. Slack will need a public URL for this file, so `digest.xml` will eventually need to be hosted with GitHub Pages or another public host. Slack cannot read a file directly from your laptop.

### `archives/`

This folder stores Markdown copies of each generated digest.

Each archive file is named with the date, like:

```text
2026-06-18-digest.md
```

## Install The Dependency

This project uses one external Python package: `feedparser`.

Install it with:

```bash
python3 -m pip install feedparser
```

## Run Locally

From the project folder, run:

```bash
python3 generate_digest.py
```

The script will print matched items in the terminal and create or update:

- `digest.xml`
- a Markdown file in `archives/`

## Filtering Logic

The script only includes recent, relevant items.

An item must be published within the last 14 days.

Then it must match either:

- a strong digital health topic, such as `EMR`, `EHR`, `CIHI`, `Infoway`, `FHIR`, `interoperability`, `patient portal`, or `health data`

or:

- a regulatory, privacy, or cybersecurity keyword plus a health context keyword

For example, an item about a health-care cybersecurity issue may match because it includes both `cybersecurity` and `health`.

## What This Project Does Not Do Yet

This project does not:

- send emails
- use OpenAI
- summarize articles
- post directly to Slack
- assume Slack admin permissions
- impersonate any person, source, or organization

Slack integration can come later, after `digest.xml` is available at a public URL.
