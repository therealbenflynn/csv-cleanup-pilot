"""Bounded, offline CSV cleanup. Never guess missing or ambiguous values."""
import argparse
import csv
import hashlib
import io
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path


def clean(source, rules, destination):
    started = time.perf_counter()
    source, destination = Path(source), Path(destination)
    raw = source.read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError('Pilot limit: 2 MB input')
    text = raw.decode('utf-8-sig')
    if '\x00' in text:
        raise ValueError('NUL bytes are not supported')
    table = list(csv.reader(io.StringIO(text, newline=''), strict=True))
    if not table or not table[0]:
        raise ValueError('A nonempty header is required')
    header, records = table[0], table[1:]
    normalized_headers = [h.strip().casefold() for h in header]
    if any(not h for h in normalized_headers) or len(set(normalized_headers)) != len(header):
        raise ValueError('Headers must be nonempty and unique ignoring case/edge spaces')
    if len(header) > 15 or len(records) > 1000:
        raise ValueError('Pilot limit: 1000 records and 15 columns')
    if any(len(row) != len(header) for row in records):
        raise ValueError('Every record must have the header column count')
    allowed = {'trim', 'lowercase', 'iso_dates', 'required', 'key', 'remove_exact_duplicates'}
    if not isinstance(rules, dict) or set(rules) - allowed:
        raise ValueError('Unknown cleanup rule')
    for name in allowed - {'remove_exact_duplicates'}:
        columns = rules.get(name, [])
        if not isinstance(columns, list) or any(not isinstance(c, str) or c not in header for c in columns):
            raise ValueError('Rule columns must name existing headers')
    if type(rules.get('remove_exact_duplicates', False)) is not bool:
        raise ValueError('remove_exact_duplicates must be boolean')
    # Reject active spreadsheet payloads, including headers, rather than alter them silently.
    for row in table:
        for value in row:
            v = value.lstrip()
            if v[:1] in ('=', '+', '@') or (v.startswith('-') and not re.fullmatch(r'-\d+(?:\.\d+)?', v)):
                raise ValueError('Formula-like cells are outside this CSV pilot')
    clean_rows, edits, exceptions, removed, provenance = [], [], [], [], []
    seen, keys = {}, {}
    for record_number, row in enumerate(records, 1):
        result = dict(zip(header, row))
        for column in header:
            before = result[column]
            value = before.strip() if column in rules.get('trim', []) else before
            if column in rules.get('lowercase', []):
                value = value.lower()
            if column in rules.get('iso_dates', []) and value:
                if re.fullmatch(r'\d{4}[-/]\d{2}[-/]\d{2}', value):
                    try:
                        value = datetime.strptime(value.replace('/', '-'), '%Y-%m-%d').date().isoformat()
                    except ValueError:
                        exceptions.append({'record': record_number, 'column': column, 'reason': 'Invalid calendar date; retained'})
                else:
                    exceptions.append({'record': record_number, 'column': column, 'reason': 'Ambiguous or unsupported date; retained'})
            result[column] = value
            if value != before:
                edits.append({'record': record_number, 'column': column, 'before': before, 'after': value})
            if column in rules.get('required', []) and not value.strip():
                exceptions.append({'record': record_number, 'column': column, 'reason': 'Required value missing; retained'})
        values = tuple(result[c] for c in header)
        if rules.get('remove_exact_duplicates') and values in seen:
            removed.append({'record': record_number, 'duplicate_of_record': seen[values], 'reason': 'All cleaned columns match'})
            continue
        seen.setdefault(values, record_number)
        if rules.get('key'):
            key = tuple(result[c] for c in rules['key'])
            if all(v.strip() for v in key):
                if key in keys:
                    exceptions.append({'record': record_number, 'column': ','.join(rules['key']), 'reason': f'Key also occurs in record {keys[key]}; both retained'})
                else:
                    keys[key] = record_number
        clean_rows.append(list(values))
        provenance.append(record_number)
    # Validate completely before creating the output directory; never overwrite delivery files.
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'source.csv').write_bytes(raw)
    with (destination / 'cleaned.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(clean_rows)
    summary = {
        'input_records': len(records), 'output_records': len(clean_rows),
        'duplicate_records_removed': len(removed), 'cell_edits_evaluated': len(edits),
        'exceptions': len(exceptions), 'output_source_records': provenance,
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'cleaned_sha256': hashlib.sha256((destination / 'cleaned.csv').read_bytes()).hexdigest(),
        'rules': rules, 'measured_processing_seconds': time.perf_counter() - started,
        'processed_at_utc': datetime.now(timezone.utc).isoformat(),
        'record_numbering': '1-based logical data records, excluding the header; multiline fields are one record',
        'edits_scope': 'Includes evaluated changes to subsequently removed duplicate records',
    }
    for name, data in [('summary', summary), ('changes', edits), ('exceptions', exceptions), ('removed', removed), ('table', {'headers': header, 'rows': clean_rows, 'source_rows': records})]:
        (destination / f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report = [f'CSV cleanup: {len(records)} input records, {len(clean_rows)} retained.',
              f'{len(removed)} exact duplicates removed; {len(exceptions)} exceptions retained.',
              'Record numbers exclude the header. Quoted values expose whitespace.', '', 'CELL CHANGES']
    report.extend(f'Record {e["record"]}, {e["column"]}: {e["before"]!r} -> {e["after"]!r}' for e in edits)
    report += ['', 'REMOVED RECORDS']
    report.extend(f'Record {e["record"]} matches record {e["duplicate_of_record"]}: {e["reason"]}' for e in removed)
    report += ['', 'UNRESOLVED EXCEPTIONS']
    report.extend(f'Record {e["record"]}, {e["column"]}: {e["reason"]}' for e in exceptions)
    (destination / 'change-report.txt').write_text('\n'.join(report) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('rules')
    parser.add_argument('destination')
    args = parser.parse_args()
    result = clean(args.source, json.loads(Path(args.rules).read_text(encoding='utf-8-sig')), args.destination)
    print(json.dumps({k: result[k] for k in ('input_records', 'output_records', 'duplicate_records_removed', 'exceptions', 'measured_processing_seconds')}))
