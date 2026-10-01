"""Read-only audit using the same parser and numeric rules as the dashboard."""
import pandas as pd
from analytics import ACTIVITIES, CASE_COLUMNS, NUMBERS, parse_start, number

# Derive the schema from established exports so a hot-reloaded app also works
# when Streamlit still holds the prior analytics module in memory.
REQUIRED_COLUMNS = ['Client', 'Exam code', 'Exam Date', 'Owner from Product',
                    *NUMBERS.values(), *[source for _, source in ACTIVITIES.values()],
                    *CASE_COLUMNS.values()]

AUDIT_COLUMNS = ['Sheet row', 'Exam code', 'Client', 'Owner', 'Original date', 'Parsed start date',
                 'Processing result', 'Issues', 'Dashboard impact', 'Exam state']


def audit_rows(raw, header_row=1):
    missing = sorted(set(REQUIRED_COLUMNS) - set(raw.columns))
    audits = []
    numeric_columns = list(dict.fromkeys([*NUMBERS.values(), *CASE_COLUMNS.values(),
        'Impersonations found', 'Poor quality enrol photo corrected']))
    for position, (_, row) in enumerate(raw.fillna('').iterrows()):
        if not any(str(v).strip() for v in row):
            continue
        value = lambda name: str(row.get(name, '')).strip()
        issues, impacts = [], []
        code = value('Exam code')
        parsed = parse_start(value('Exam Date'))
        if missing:
            issues.append('Missing required columns: ' + ', '.join(missing))
            impacts.append('Dashboard cannot load until these column headings are restored.')
        if not code:
            issues.append('Exam code is blank.')
            impacts.append('Row is excluded from all exam totals.')
        if pd.isna(parsed):
            issues.append('Exam Date is blank.' if not value('Exam Date') else 'Exam Date cannot be parsed; provide a day, month and year.')
            impacts.append('Excluded when a month is selected and from monthly charts and attention required; included in overall totals only when all months are selected.')
        for column in numeric_columns:
            if column not in raw.columns:
                continue
            text = value(column)
            n = number(pd.Series([text])).iloc[0]
            if pd.isna(n):
                if text:
                    issues.append(f'{column}: nonnumeric value ({text}).')
                    impacts.append(f'{column} is omitted from numeric totals.')
                elif column in NUMBERS.values():
                    issues.append(f'{column}: missing count.')
                    impacts.append(f'{column} is omitted from numeric totals.')
            elif n < 0 or not float(n).is_integer():
                issues.append(f'{column}: negative or fractional count ({text}); verify source value.')
                impacts.append(f'{column} is currently included as entered.')
        if not value('Owner from Product'):
            issues.append('Owner from Product is blank.')
            impacts.append('Grouped as Unassigned; excluded from the Owners card.')
        if not value('Client'):
            issues.append('Client is blank.')
            impacts.append('Grouped as Unspecified.')
        cancelled = value('Data cleaned by MIS').lower() in {'cancelled', 'canceled'}
        state = 'Cancelled exams' if cancelled else ('Complete' if all(value(source) for _, source in ACTIVITIES.values()) else 'WIP')
        if cancelled:
            impacts.append('Valid cancelled exam: included in filtered totals, excluded from process analytics and follow-ups.')
        if missing or not code:
            result = 'Not processed'
        elif pd.isna(parsed):
            result = 'Partially processed - date issue'
        elif issues:
            result = 'Processed with warnings'
        else:
            result = 'Processed'
        audits.append([position+header_row+1, code, value('Client'), value('Owner from Product'),
            value('Exam Date'), '' if pd.isna(parsed) else parsed.strftime('%Y-%m-%d'), result,
            '\n'.join(issues), '\n'.join(dict.fromkeys(impacts)) or 'Available to dashboard filters and totals.', state])
    return pd.DataFrame(audits, columns=AUDIT_COLUMNS)

def report_csv(raw, source_url, fetched_at):
    audit = audit_rows(raw)
    audit['Source'] = source_url
    audit['Fetched at'] = fetched_at
    # Keep sheet-provided strings as text rather than executable Excel formulas.
    safe = audit.copy()
    for column in safe.select_dtypes(include=['str', 'object']).columns:
        safe[column] = safe[column].map(lambda v: "'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v)
    return safe.to_csv(index=False).encode('utf-8-sig')


def sheet_button_html(csv_bytes, source_url):
    import base64
    import json
    from html import escape
    encoded = base64.b64encode(csv_bytes).decode('ascii')
    return '''<!doctype html><html><head><style>
body {margin:0;font-family:Arial,sans-serif;}
a {display:block;box-sizing:border-box;width:100%;padding:10px 12px;border:1px solid #d4d4d4;border-radius:8px;background:white;color:#222;text-align:center;text-decoration:none;font-size:14px;}
a:hover {border-color:#555;background:#f5f5f5;}
a:focus-visible {outline:2px solid #555;outline-offset:-3px;}
</style></head><body>
<a id="open-sheet" href="''' + escape(source_url, quote=True) + '''" target="_blank" rel="noopener noreferrer">Open Google Sheet</a>
<script>
document.getElementById('open-sheet').addEventListener('click', function () {
    const bytes = Uint8Array.from(atob(''' + json.dumps(encoded) + '''), c => c.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], {type:'text/csv;charset=utf-8'}));
    const download = document.createElement('a');
    download.href = url;
    download.download = 'exam_processing_report.csv';
    document.body.appendChild(download);
    download.click();
    download.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
});
</script></body></html>'''
