"""Data normalization and aggregation for the exam operations dashboard."""
import re
import pandas as pd

ACTIVITIES = {
    'Photo Quality': ('Pre', 'Pre - Photo Quality'),
    'Pre-Dedupe': ('Pre', 'Pre - Dedupe'),
    'Duplicate': ('Post', 'Post - Duplicate Face'),
    'Probable': ('Post', 'Post - Probable Match'),
    'Auto Move': ('Post', 'Post - Auto Move'),
    'Ops': ('Post', 'Post - Photo mismatch to Ops post exam'),
    'Delivery': ('Post', 'Post - Photo mismatch to Delivery post data cleaning'),
}
CASE_COLUMNS = {
    'Impersonation': 'Impersonation cases reported',
    'Duplicate Face': 'Duplicate face cases',
    'Probable Match': 'Probable match cases',
    'Auto Move': 'Automove cases',
    'Poor Photo': 'Poor quality enrol photo reported',
}
NUMBERS = {'Candidates': 'Candidate count', 'Centres': 'Centres', 'Shifts': 'Shift'}
COLORS = {'Complete': '#16845b', 'Pending': '#d34b55', 'N/A': '#8090a2'}
MONTHS = {m: i for i, m in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'], 1)}


def parse_start(value):
    """Use first listed day/month and an explicit year; never guess missing months."""
    value = str(value).strip().lower()
    if re.fullmatch(r'\d{5}(?:\.0)?', value):
        return pd.Timestamp('1899-12-30') + pd.Timedelta(days=float(value))
    month = re.search(r'\b(jan\w*|feb\w*|mar\w*|apr\w*|may|jun\w*|jul\w*|aug\w*|sep\w*|oct\w*|nov\w*|dec\w*)', value)
    if not month:
        return pd.NaT
    day = re.search(r'\d{1,2}', value[:month.start()])
    year = re.search(r"\b(20\d{2})\b", value)
    if year is None:
        year = re.search(r"'(\d{2})(?!\d)", value)
    if year is None:
        year = re.search(r"^[-\s]+(\d{2})(?!\d|\s*[a-z])", value[month.end():])
    if not day or not year:
        return pd.NaT
    y = int(year.group(1))
    y = y + 2000 if y < 100 else y
    try:
        return pd.Timestamp(year=y, month=MONTHS[month.group()[:3]], day=int(day.group()))
    except ValueError:
        return pd.NaT


def number(series):
    return pd.to_numeric(series.astype(str).str.replace(',', '', regex=False).str.strip(), errors='coerce')


def normalize_status(value):
    value = re.sub(r'\s+', ' ', str(value).strip().lower())
    if value in {'done', 'complete', 'completed', 'sent', 'no cases'}:
        return 'Complete'
    if value == 'not sent':
        return 'Pending'
    # Blank, WIP, non-applicable cells and other notes are not evaluated.
    return 'N/A'


def rollup(values):
    values = set(values)
    if 'Pending' in values:
        return 'Pending'
    if 'Complete' in values:
        return 'Complete'
    return 'N/A'


def prepare(raw):
    required = ['Client', 'Exam code', 'Exam Date', 'Owner from Product', *NUMBERS.values(), *[v[1] for v in ACTIVITIES.values()], *CASE_COLUMNS.values()]
    missing = sorted(set(required) - set(raw.columns))
    if missing:
        raise ValueError('Required columns missing: ' + ', '.join(missing))
    df = raw.fillna('').copy()
    df = df[df['Exam code'].astype(str).str.strip().ne('')].copy()
    df['Owner'] = df['Owner from Product'].astype(str).str.strip().replace('', 'Unassigned')
    df['Client'] = df['Client'].astype(str).str.strip().replace('', 'Unspecified')
    df['Exam'] = df['Exam code'].astype(str).str.replace(r'\s+', ' ', regex=True)
    df['Date'] = pd.to_datetime(df['Exam Date'].map(parse_start))
    df['Month'] = df['Date'].dt.strftime('%Y-%m')
    for name, source in NUMBERS.items():
        df[name] = number(df[source])
    for name, (_, source) in ACTIVITIES.items():
        df['Status: ' + name] = df[source].map(normalize_status)
    df['Status'] = df[['Status: ' + a for a in ACTIVITIES]].apply(rollup, axis=1)
    cancelled = df.get('Data cleaned by MIS', pd.Series('', index=df.index)).astype(str).str.contains('cancelled|canceled', case=False, regex=True)
    cancelled |= df[ACTIVITIES['Delivery'][1]].astype(str).str.contains('exam cancelled|discarded', case=False, regex=True)
    return df.loc[~cancelled].copy(), int(cancelled.sum())


def completion(frame):
    values = frame[['Status: ' + a for a in ACTIVITIES]]
    applicable = values.isin(['Complete', 'Pending']).sum().sum()
    return float(values.eq('Complete').sum().sum() / applicable * 100) if applicable else None


def owner_summary(frame):
    rows = []
    for owner, group in frame.groupby('Owner', sort=True):
        rows.append({'Owner': owner, 'Exams': len(group), 'Candidates': group['Candidates'].sum(min_count=1), 'Centres': group['Centres'].sum(min_count=1), 'Shifts': group['Shifts'].sum(min_count=1), 'Clients': group['Client'].nunique(), 'Completion': completion(group)})
    return pd.DataFrame(rows, columns=['Owner','Exams','Candidates','Centres','Shifts','Clients','Completion'])


def attention(frame, today):
    rows = []
    for _, row in frame.iterrows():
        if pd.isna(row['Date']) or row['Date'].date() > today:
            continue
        for activity, (stage, source) in ACTIVITIES.items():
            status = row['Status: ' + activity]
            if status != 'Pending':
                continue
            rows.append({'Age': (today - row['Date'].date()).days, 'Client': row['Client'], 'Exam': row['Exam'], 'Date': row['Date'].strftime('%d %b %Y'), 'Owner': row['Owner'], 'Stage': stage, 'Activity': activity, 'Status': 'Not sent', 'Sheet note': str(row[source]).strip() or '(blank)'})
    result = pd.DataFrame(rows, columns=['Age','Client','Exam','Date','Owner','Stage','Activity','Status','Sheet note'])
    return result.sort_values(['Age','Owner'], ascending=[False,True]) if not result.empty else result
