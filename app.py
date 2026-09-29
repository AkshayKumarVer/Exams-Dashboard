import csv
import io
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd
import requests
import streamlit as st
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession
from google.auth.exceptions import GoogleAuthError

SHEET_ID = "1tA5QngIq4DP0ynHShbLBPV0rPD1b8dok2Br2VD3WR7k"
GID = 1596592637
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit#gid={GID}"

st.set_page_config(page_title="Exam Operations Dashboard", page_icon="📊", layout="wide")


def check_response(response):
    if response.status_code in (401, 403):
        raise ValueError("Google denied access. Enable link viewing, or configure a service account with Viewer access and enable the Google Sheets API.")
    response.raise_for_status()
    if "text/html" in response.headers.get("Content-Type", "").lower():
        raise ValueError("Google returned a sign-in page instead of sheet data. Check sharing permissions.")


def as_frame(rows, header_row):
    if not rows:
        return pd.DataFrame()
    if header_row > len(rows):
        raise ValueError("The header row is beyond the available sheet rows.")
    rows = rows[header_row - 1:]
    width = max(map(len, rows))
    names, used = [], set()
    for i in range(width):
        base = str(rows[0][i]).strip() if i < len(rows[0]) else ""
        base = base or f"Column {i + 1}"
        name, suffix = base, 2
        while name in used:
            name = f"{base} ({suffix})"
            suffix += 1
        used.add(name)
        names.append(name)
    values = [row + [""] * (width - len(row)) for row in rows[1:] if any(str(v).strip() for v in row)]
    return pd.DataFrame(values, columns=names)


@st.cache_data(ttl=60, show_spinner=False)
def load_sheet(header_row):
    try:
        account = dict(st.secrets["gcp_service_account"]) if "gcp_service_account" in st.secrets else None
    except FileNotFoundError:
        account = None
    if account:
        credentials = Credentials.from_service_account_info(account, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        with AuthorizedSession(credentials) as session:
            base = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}"
            response = session.get(base, params={"fields": "sheets.properties"}, timeout=30)
            check_response(response)
            title = next((s["properties"]["title"] for s in response.json()["sheets"] if s["properties"]["sheetId"] == GID), None)
            if title is None:
                raise ValueError("The specified worksheet tab was not found.")
            sheet_range = "'" + title.replace("'", "''") + "'"
            response = session.get(f"{base}/values/{quote(sheet_range, safe='')}", params={"valueRenderOption": "FORMATTED_VALUE"}, timeout=30)
            check_response(response)
            rows = response.json().get("values", [])
        mode = "Private service account"
    else:
        response = requests.get(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export", params={"format": "csv", "gid": GID}, timeout=30)
        check_response(response)
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
        mode = "Link access"
    return as_frame(rows, header_row), datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"), mode


from html import escape
from zoneinfo import ZoneInfo
import altair as alt
from analytics import ACTIVITIES, CASE_COLUMNS, COLORS, prepare, owner_summary, attention, number, rollup

def render_dashboard():
    metrics = [('Exams',len(selected)), ('Candidates',selected['Candidates'].sum(min_count=1)), ('Centres',selected['Centres'].sum(min_count=1)), ('Clients',selected['Client'].nunique()), ('Owners',selected.loc[selected.Owner.ne('Unassigned'),'Owner'].nunique())]
    for col, (label, value) in zip(st.columns(5), metrics):
        col.metric(label, compact(value) if label == 'Candidates' else ('—' if pd.isna(value) else f'{value:,.0f}'))
    for col, (label, key) in zip(st.columns(3), [('Completed','Complete'),('Pending (not sent)','Pending'),('Not evaluated','N/A')]):
        col.metric(label, int(selected['Status'].eq(key).sum()))
    if selected.empty:
        st.info('No exams match these filters. Choose another month, client, owner, or status.')


    def bars(frame, label, value, color='#367bf5', percent=False, order=None):
        if frame.empty or frame[value].notna().sum() == 0:
            st.caption('No data available for these filters.')
            return
        scale = alt.Scale(domain=[0,100]) if percent else alt.Scale(zero=True)
        frame = frame.copy()
        frame['Display value'] = frame[value].map(lambda v: '?' if pd.isna(v) else (f'{v:.1f}%' if percent else compact(v)))
        sort = order if order is not None else '-x'
        chart = alt.Chart(frame).mark_bar(cornerRadiusEnd=4, size=19).encode(
            y=alt.Y(f'{label}:N', sort=sort, title=None, axis=alt.Axis(labelLimit=240, ticks=False, domain=False)),
            x=alt.X(f'{value}:Q', title=None, scale=scale, axis=alt.Axis(format='.0f' if percent else '~s', gridColor='#edf0f5', domain=False)),
            color=alt.value(color),
            tooltip=[alt.Tooltip(f'{label}:N'),alt.Tooltip(f'{value}:Q',format=',.1f' if percent else ',.0f')])
        text = chart.mark_text(align='left', dx=5, color='#243c57').encode(text=alt.Text('Display value:N'))
        st.altair_chart((chart + text).properties(height=max(145, len(frame)*36)).configure_view(stroke=None), width='stretch')

    st.subheader('WORKLOAD OVERVIEW')
    st.caption('Three months ending in the selected month · client, owner, and status filters apply.')
    periods = pd.period_range(end=month, periods=3, freq='M').astype(str).tolist()
    history = base[base.Month.isin(periods)].groupby('Month').agg(Exams=('Exam','size'),Candidates=('Candidates',lambda s:s.sum(min_count=1))).reindex(periods)
    history['Exams'] = history['Exams'].fillna(0)
    history['Month label'] = [pd.Timestamp(m+'-01').strftime('%b %Y') for m in history.index]
    left, right = st.columns(2)
    with left:
        st.markdown('**EXAMS BY MONTH**')
        bars(history.reset_index(), 'Month label','Exams',order=history['Month label'].tolist())
    with right:
        st.markdown('**CANDIDATES BY MONTH**')
        bars(history.reset_index(), 'Month label','Candidates',color='#12a899',order=history['Month label'].tolist())
    summary = owner_summary(selected)
    st.subheader('OWNER WORKLOAD')
    left, right = st.columns(2)
    with left:
        st.markdown('**EXAMS BY OWNER**')
        bars(summary,'Owner','Exams')
    with right:
        st.markdown('**CANDIDATE WORKLOAD**')
        bars(summary,'Owner','Candidates',color='#12a899')

    st.subheader('OWNER PERFORMANCE')
    st.caption('Exam, candidate and centre workload for the selected month.')
    st.dataframe(summary[['Owner','Exams','Candidates','Centres']], hide_index=True, width='stretch', column_config={c:st.column_config.NumberColumn(c,format='localized') for c in ['Exams','Candidates','Centres']})

    st.subheader('PROCESS COMPLETION & CASE ANALYTICS')
    left, right = st.columns([1.4,1])
    with left:
        process = []
        for activity in ACTIVITIES:
            values = selected['Status: '+activity]
            total = values.isin(['Complete', 'Pending']).sum()
            done = int(values.eq('Complete').sum())
            process.append({'Done': done, 'Total': int(total), 'Process': {'Duplicate':'Duplicate Face','Probable':'Probable Match','Ops':'Photo mismatch to Ops','Delivery':'Photo mismatch to Delivery'}.get(activity,activity), 'Completion %': done/total*100 if total else None})
        process_frame = pd.DataFrame(process)
        process_frame['Label'] = process_frame.apply(
            lambda row: (f"{row['Completion %']:.1f}%" if pd.notna(row['Completion %']) else 'N/A')
            + f" | Done {row['Done']:,} / Total {row['Total']:,}", axis=1)
        process_frame['Plot completion'] = process_frame['Completion %'].fillna(0)
        process_chart = alt.Chart(process_frame).encode(
            y=alt.Y('Process:N', sort=[p['Process'] for p in process], title=None,
                    axis=alt.Axis(labelLimit=240, ticks=False, domain=False)),
            x=alt.X('Plot completion:Q', title='Completion (%)', scale=alt.Scale(domain=[0,100]),
                    axis=alt.Axis(gridColor='#edf0f5', domain=False)),
            tooltip=[alt.Tooltip('Process:N'), alt.Tooltip('Completion %:Q', format='.1f'),
                     alt.Tooltip('Done:Q'), alt.Tooltip('Total:Q')])
        process_bars = process_chart.mark_bar(color='#367bf5', cornerRadiusEnd=4, size=16)
        process_labels = process_chart.mark_text(align='left', dy=-17, color='#243c57').encode(
            x=alt.value(2), text='Label:N')
        st.altair_chart((process_bars + process_labels).properties(height=350)
                       .configure_view(stroke=None), width='stretch')
    with right:
        cases = []
        for label, source in {'Impersonation reported': 'Impersonation cases reported', 'Impersonation found': 'Impersonations found', **{k:v for k,v in CASE_COLUMNS.items() if k != 'Impersonation'}}.items():
            values = number(selected[source])
            across_exams = (values.notna() & values.ne(0)).sum() if label == 'Impersonation found' else values.notna().sum()
            cases.append({'Case type':label,'Reported count':values.sum(min_count=1),'Across Exams':int(across_exams)})
        st.dataframe(pd.DataFrame(cases), hide_index=True, width='stretch', column_config={'Reported count':st.column_config.NumberColumn(format='localized')})

    st.subheader('IMPERSONATION CASES BY OWNER')
    st.caption('Reported and found cases for each owner in the current selection.')
    comparison_rows = []
    for owner_name, group in selected.groupby('Owner', sort=True):
        for series_name, source in [('Reported', 'Impersonation cases reported'), ('Found', 'Impersonations found')]:
            counts = number(group[source]) if source in group else pd.Series(dtype=float)
            comparison_rows.append({'Owner': owner_name, 'Case type': series_name, 'Cases': counts.sum(min_count=1), 'Numeric records': int(counts.notna().sum())})
    comparison = pd.DataFrame(comparison_rows, columns=['Owner', 'Case type', 'Cases', 'Numeric records'])
    if comparison.empty or comparison['Cases'].notna().sum() == 0:
        st.info('No numeric impersonation counts are available for this selection.')
    else:
        comparison['Label'] = comparison['Cases'].map(lambda v: 'No data' if pd.isna(v) else f'{v:,.0f}')
        comparison['Plot cases'] = comparison['Cases'].fillna(0)
        grouped = alt.Chart(comparison).encode(
            x=alt.X('Owner:N', title=None, axis=alt.Axis(labelAngle=0)),
            xOffset=alt.XOffset('Case type:N', sort=['Reported', 'Found']),
            y=alt.Y('Plot cases:Q', title='Cases', scale=alt.Scale(zero=True), axis=alt.Axis(tickMinStep=1)),
            color=alt.Color('Case type:N', title=None, scale=alt.Scale(domain=['Reported','Found'], range=['#367bf5','#12a899'])),
            tooltip=[alt.Tooltip('Owner:N'), alt.Tooltip('Case type:N'), alt.Tooltip('Label:N', title='Cases'), alt.Tooltip('Numeric records:Q')])
        chart_bars = grouped.mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        chart_labels = grouped.mark_text(dy=-10, color='#243c57').encode(text='Label:N', color=alt.value('#243c57'))
        st.altair_chart((chart_bars + chart_labels).properties(height=300).configure_view(stroke=None), width='stretch')
        st.caption('Blank and nonnumeric counts are excluded. No data means no numeric count was supplied; it does not mean zero.')

    st.subheader('ACTIVITY COMPLETION HEATMAP')
    st.caption('Green = Complete | Red = Not sent | Gray = no evaluated activity')
    heat = '<div style="overflow-x:auto"><table class="heatmap"><thead><tr><th>Owner</th>' + ''.join('<th>'+escape(a)+'</th>' for a in ACTIVITIES) + '</tr></thead><tbody>'
    for name, group in selected.groupby('Owner'):
        heat += '<tr><td>'+escape(name)+'</td>'
        for activity in ACTIVITIES:
            values = group['Status: '+activity]
            state = rollup(values)
            state = {'Not sent': 'Pending', 'WIP': 'N/A'}.get(state, state)
            color = COLORS.get(state, '#8090a2')
            label = {'Pending': 'NOT SENT', 'Complete': 'COMPLETE'}.get(state, chr(8212))
            detail = ', '.join(f"{'Not sent' if k == 'Pending' else k}: {v}" for k,v in values[values.ne('N/A')].value_counts().items()) or 'No evaluated activity'
            heat += f'<td title="{escape(detail, quote=True)}" style="color:{color};background:{color}18;border:1px solid {color}30">{escape(label)}</td>'
        heat += '</tr>'
    heat += '</tbody></table></div>'
    st.markdown(heat, unsafe_allow_html=True)
    st.caption('Not sent is the only pending activity. Blank and WIP cells are excluded. Hover for evaluated activity counts.')

    st.subheader('ATTENTION REQUIRED')
    st.caption('Only activities marked Not sent, for exams that have started.')
    actions = attention(selected, today)[['Owner','Client','Exam','Date','Activity','Status']]
    if actions.empty:
        st.success('No outstanding activities for exams that have started in this selection.')
    else:
        st.dataframe(actions, hide_index=True, width='stretch', height=min(600, 38+len(actions)*35))
        st.download_button('Download outstanding actions',actions.to_csv(index=False).encode('utf-8-sig'),'exam_followups.csv','text/csv')


def render_info_page():
    from dashboard_info import render_info
    render_info(raw.loc[selected.index], data, selected, cancelled)


dashboard_page = st.Page(render_dashboard, title='Dashboard', default=True)
info_page = st.Page(render_info_page, title='Info', url_path='info')
page = st.navigation([dashboard_page, info_page], position='hidden')

st.markdown("""<style>
.stApp {background:#f5f7fb;}
.block-container {max-width:1440px;padding-top:2.1rem;}
h1 {color:#142842;font-size:2rem!important;letter-spacing:.035em;font-weight:800!important;}
h3 {color:#233952;font-size:1.05rem!important;letter-spacing:.045em;margin-top:1rem;}
[data-testid="stMetric"] {background:white;border:1px solid #e2e8f1;border-radius:12px;padding:18px 20px;box-shadow:0 2px 5px #14284204;}
[data-testid="stMetricLabel"] {color:#6b7c90;text-transform:uppercase;font-size:.75rem;letter-spacing:.08em;}
[data-testid="stMetricValue"] {color:#142842;font-weight:750;}
.caption {color:#7a8ba0;font-size:.8rem;letter-spacing:.12em;}
.heatmap {width:100%;border-collapse:separate;border-spacing:5px;font-size:12px;}
.heatmap th {color:#62728a;text-align:left;font-size:11px;padding:10px 5px;text-transform:uppercase;}
.heatmap td {border-radius:6px;padding:13px 8px;font-weight:600;white-space:nowrap;}
</style>""", unsafe_allow_html=True)
st.markdown('<div class="caption">OPERATIONS INTELLIGENCE / LIVE GOOGLE SHEETS</div>', unsafe_allow_html=True)
st.title('EXAM OPERATIONS DASHBOARD')
with st.sidebar:
    st.header('Data connection')
    st.link_button('Open Google Sheet', SHEET_URL)
    header_row = st.number_input('Header row', min_value=1, value=1, step=1, key='header_row')
    if st.button('Refresh data', type='primary', width='stretch'):
        load_sheet.clear()
    st.caption('Data is cached for 60 seconds. Refresh to fetch changes immediately.')
try:
    with st.spinner('Loading exam operations…'):
        raw, fetched_at, mode = load_sheet(header_row)
        data, cancelled = prepare(raw)
except (requests.RequestException, GoogleAuthError, ValueError, KeyError) as exc:
    st.error('Unable to load exam operations.')
    st.info(str(exc) if isinstance(exc, ValueError) else 'Check the sheet connection and sharing permissions, then refresh.')
    st.stop()
with st.sidebar:
    st.success('Sheet connected')
    st.caption('Last fetched: ' + fetched_at)
    st.caption(f'{len(data):,} active operation rows · {cancelled} cancelled/discarded rows excluded')

months = sorted(data['Month'].dropna().unique(), reverse=True)
if not months:
    st.warning('No recognizable exam dates. Check the sheet dates and header row.')
    st.stop()
today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
current_month = today.strftime('%Y-%m')
default_month = months.index(current_month) if current_month in months else 0
def remember_filter(key):
    st.session_state.setdefault('saved_filters', {})[key] = st.session_state[key]

for filter_key, filter_value in st.session_state.get('saved_filters', {}).items():
    st.session_state[filter_key] = filter_value

f1, f2, f3, f4 = st.columns([1.4,1,1,1])
month = f1.selectbox('Month', months, index=default_month, key='filter_month', on_change=remember_filter, args=('filter_month',), format_func=lambda m: pd.Timestamp(m + '-01').strftime('%B %Y'))
client = f2.selectbox('Client', ['All'] + sorted(data['Client'].unique()), key='filter_client', on_change=remember_filter, args=('filter_client',))
owner = f3.selectbox('Owner', ['All'] + sorted(data['Owner'].unique()), key='filter_owner', on_change=remember_filter, args=('filter_owner',))
status = f4.selectbox('Status', ['All','Complete','Pending','N/A'], key='filter_status', on_change=remember_filter, args=('filter_status',))
base = data.copy()
if client != 'All':
    base = base[base['Client'].eq(client)]
if owner != 'All':
    base = base[base['Owner'].eq(owner)]
if status != 'All':
    base = base[base['Status'].eq(status)]
selected = base[base['Month'].eq(month)].copy()

def compact(value):
    if pd.isna(value):
        return '—'
    if abs(value) >= 1000000:
        return f'{value / 1000000:,.2f}M'
    if abs(value) >= 1000:
        return f'{value / 1000:,.1f}K'
    return f'{value:,.0f}'

download_col, info_col = st.columns([9, 1])
with download_col:
    st.download_button(
        'Download complete data',
        raw.loc[selected.index].to_csv(index=False).encode('utf-8-sig'),
        f'exam_operations_{month}.csv',
        'text/csv',
        help='All original sheet columns for the rows matching the current filters.',
        key='download_complete_data')
with info_col:
    if page.url_path == 'info':
        if st.button('Back', key='back_to_dashboard', width='stretch'):
            st.switch_page(dashboard_page)
    elif st.button('Info', key='open_info', width='stretch'):
        st.switch_page(info_page)
page.run()
