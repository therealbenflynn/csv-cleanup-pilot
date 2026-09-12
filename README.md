# CSV Cleanup Pilot

A small offline Python tool for explicit CSV cleanup, with a record of every change. It keeps ambiguous dates and conflicting identifiers visible instead of silently guessing.

The tool is free to use. It was developed with AI assistance and tested against independently specified examples. It is an early, deliberately bounded release.

## Try the fictional example

Requires Python 3.10 or later. No third-party packages, API keys or accounts are needed.

```sh
python clean_csv.py examples/inventory-source.csv examples/rules.json sample-output
python -m unittest test_cleanup -v
```

Use a new destination folder each time. The command refuses to overwrite an existing folder. On Windows, `py` can replace `python` if that is how Python is installed.

Expected example result: **12 input records, 10 retained, 2 duplicate records removed and 4 unresolved exceptions**. All example records are fictional.

| Example | Result |
|---|---|
| Identifier `0007` | Leading zeros retained in the CSV |
| Category with surrounding spaces and mixed case | Trimmed and lowercased only because the rules request it |
| Date `2026/09/01` | Converted to `2026-09-01` |
| Ambiguous date `03/04/2026` | Retained and flagged |
| Impossible date `2026-02-30` | Retained and flagged |
| Same key with different row contents | Both retained and flagged |

## What it does

You choose columns for trimming, lowercasing, unambiguous year-first date normalization, required-value checks and key-conflict checks. Optional duplicate removal compares **all columns after the selected cleanup rules**. It does not merge rows that merely share a key.

The new output folder contains the untouched source, cleaned CSV, readable change report and JSON reports for changes, exceptions, removals, provenance and SHA-256 hashes. Review exceptions and the change report before using the result.

Example rules:

```json
{
  "trim": ["sku", "category"],
  "lowercase": ["category"],
  "required": ["sku"],
  "key": ["sku"],
  "remove_exact_duplicates": true
}
```

Rule names must match your actual headers. Do not trim or lowercase identifiers unless that is the intended business rule.

## Limits

- UTF-8 CSV only, up to 1,000 data records, 15 columns and 2,000,000 input bytes.
- Comma-separated files with unique, nonempty headers and consistent row widths.
- Formula-like cells are rejected. This is deliberately conservative and can reject otherwise legitimate values such as international phone numbers beginning with `+`.
- No fuzzy matching, missing-value invention, spreadsheet formulas or automatic marketplace imports.
- CSV values are preserved as text, but spreadsheet software can reinterpret them when opening the file. Import identifier columns as text in that software.
- This tool is not a Shopify importer. It has not been validated against a live merchant store.

## Feedback

If you already repair CSV exports or imports, what specific step still takes work after using your current tools? A reproducible issue with a **fictional or fully redacted small example** is especially useful. Public issues are visible to everyone: do not post credentials, customer data, personal information or confidential business files.

For people who prefer an assisted result, a limited [optional $25 cleanup pilot](SERVICE.md) is described separately. The free tool remains usable without contacting anyone or paying.

## Checks and license

The included tests cover the fictional example, identifier preservation, ambiguous and invalid dates, multiline fields, malformed input, conservative formula rejection, limits and refusing overwrite. They do not establish correctness for every possible business rule or input.

MIT license. Maintained under Ben Flynn's GitHub account with AI-assisted development and review. No claim of platform certification or guaranteed import success.
