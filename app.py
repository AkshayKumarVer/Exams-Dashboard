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

st.set_page_config(page_title="Exam Operations Dashboard", page_icon=chr(0x1F4CA), layout="wide")


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
import logging
import altair as alt
from analytics import (ACTIVITIES, CASE_COLUMNS, COLORS, prepare, owner_summary,
                       attention, number, rollup, filter_operations, process_summary)


def compact(value):
    if pd.isna(value):
        return 'No data'
    if abs(value) >= 1000000:
        return f'{value/1000000:,.2f}M'
    if abs(value) >= 1000:
        return f'{value/1000:,.1f}K'
    return f'{value:,.0f}'


def bars(frame, label, value, color='#367bf5', order=None):
    if frame.empty:
        st.info('No matching exams.')
        return
    frame = frame.copy()
    frame['Display'] = frame[value].map(compact)
    frame['Plot'] = frame[value].fillna(0)
    chart = alt.Chart(frame).encode(
        y=alt.Y(f'{label}:N',sort=order or frame[label].tolist(),title=None,
                axis=alt.Axis(labelLimit=240,ticks=False,domain=False)),
        x=alt.X('Plot:Q',title=None,axis=None,scale=alt.Scale(zero=True)),
        tooltip=[alt.Tooltip(f'{label}:N'),alt.Tooltip(f'{value}:Q',format=',.0f')])
    bar = chart.mark_bar(color=color,cornerRadiusEnd=4,size=19)
    labels = chart.mark_text(align='left',dx=5,color='#243c57').encode(text='Display:N')
    st.altair_chart((bar+labels).properties(height=max(145,len(frame)*36)).configure_view(stroke=None),width='stretch')


def draw_process(frame, title):
    st.markdown(f'**{title}**')
    if frame.empty:
        st.info('No matching exams.')
        return
    summary = process_summary(frame)
    summary['Start'] = 0
    summary['End'] = 100
    summary['Percent label'] = summary['Completion %'].map(lambda value: f'{value:.1f}%')
    summary['Done label'] = summary['Done'].map(lambda value: f'Done {value:,}')
    summary['Total label'] = summary['Total'].map(lambda value: f'Total {value:,}')
    chart = alt.Chart(summary).encode(
        y=alt.Y('Process:N',sort=summary.Process.tolist(),title=None,
                axis=alt.Axis(labelLimit=240,ticks=False,domain=False)),
        tooltip=[alt.Tooltip('Process:N'),alt.Tooltip('Completion %:Q',format='.1f'),
                 alt.Tooltip('Done:Q'),alt.Tooltip('Not sent:Q'),alt.Tooltip('WIP:Q'),alt.Tooltip('Total:Q')])
    def position(field):
        return alt.X(field,axis=None,title=None,scale=alt.Scale(domain=[-12,115]))
    # Red is the entire remainder, including Not sent and WIP.
    remainder = chart.mark_bar(color='#d34b55',size=20).encode(
        x=position('Completion %:Q'),x2='End:Q')
    done = chart.mark_bar(color='#16845b',size=20).encode(
        x=position('Start:Q'),x2='Completion %:Q')
    percentage = chart.mark_text(align='right',dx=-9,color='#243c57',fontWeight='bold').encode(
        x=position('Start:Q'),text='Percent label:N')
    done_count = chart.mark_text(align='center',dy=-20,color='#16845b',fontWeight='bold').encode(
        x=position('Completion %:Q'),text='Done label:N')
    total_count = chart.mark_text(align='left',dx=9,color='#243c57',fontWeight='bold').encode(
        x=position('End:Q'),text='Total label:N')
    st.altair_chart((remainder+done+percentage+done_count+total_count)
                   .properties(height=385).configure_view(stroke=None),width='stretch')


def draw_heatmap(frame, title):
    st.markdown(f'**{title}**')
    if frame.empty:
        st.info('No matching exams.')
        return
    html = '<div style="overflow-x:auto"><table class="heatmap"><thead><tr><th>Owner</th>'
    html += ''.join('<th>'+escape(a)+'</th>' for a in ACTIVITIES) + '</tr></thead><tbody>'
    for owner_name, group in frame.groupby('Owner',sort=True):
        html += '<tr><td>'+escape(owner_name)+'</td>'
        for activity in ACTIVITIES:
            values = group['Status: '+activity]
            state = rollup(values)
            color = COLORS.get(state,'#8090a2')
            hover = ' | '.join(f'{s}: {int(values.eq(s).sum())}' for s in ['Complete','Not sent','WIP'])
            html += f'<td title="{escape(hover,quote=True)}" style="color:{color};background:{color}18;border:1px solid {color}30">{escape(state.upper())}</td>'
        html += '</tr>'
    st.markdown(html+'</tbody></table></div>',unsafe_allow_html=True)


st.markdown('''<style>
.stApp {background:#f5f7fb;}
.block-container {max-width:1440px;padding-top:2.1rem;}
h1 {color:#142842;font-size:2rem!important;letter-spacing:.035em;}
h3 {color:#233952;font-size:1.05rem!important;letter-spacing:.045em;margin-top:1rem;}
[data-testid="stMetric"] {background:white;border:1px solid #e2e8f1;border-radius:12px;padding:18px 20px;}
[data-testid="stMetricLabel"] {text-transform:uppercase;font-size:.75rem;}
[data-testid="stMetricValue"] {color:#142842;font-weight:750;}
.heatmap {width:100%;border-collapse:separate;border-spacing:5px;font-size:12px;}
.heatmap th {text-align:left;font-size:11px;padding:10px 5px;text-transform:uppercase;}
.heatmap td {border-radius:6px;padding:13px 8px;font-weight:600;white-space:nowrap;}
</style>''',unsafe_allow_html=True)
st.title('EXAM OPERATIONS DASHBOARD')
with st.sidebar:
    st.link_button('Open Google Sheet',SHEET_URL)
    if st.button('Refresh data',type='primary',width='stretch'):
        load_sheet.clear()
try:
    with st.spinner('Loading exams...'):
        raw,fetched_at,mode = load_sheet(1)
        data,cancelled = prepare(raw)
except (requests.RequestException,GoogleAuthError,ValueError,KeyError) as exc:
    st.error(str(exc) if isinstance(exc,ValueError) else 'Unable to load exams. Check the sheet connection and refresh.')
    st.stop()
if data.empty:
    st.info('No exam records available.')
    st.stop()
invalid_dates = data.Date.isna().sum()
if invalid_dates:
    logging.getLogger(__name__).warning('%s exam rows have unrecognized dates; month filters exclude them.',invalid_dates)
months = sorted(data.Month.dropna().unique(),reverse=True)
today = datetime.now(ZoneInfo('Asia/Kolkata')).date()
current_month = today.strftime('%Y-%m')
default_months = [current_month] if current_month in months else months[:1]
f1,f2,f3,f4 = st.columns([1.4,1,1,1])
chosen_months = f1.multiselect('Months',months,default=default_months,format_func=lambda m:pd.Timestamp(m+'-01').strftime('%B %Y'),placeholder='All months',key='months_v2')
clients = f2.multiselect('Clients',sorted(data.Client.unique()),placeholder='All clients',key='clients_v2')
owners = f3.multiselect('Owners',sorted(data.Owner.unique()),placeholder='All owners',key='owners_v2')
statuses = f4.multiselect('Status',['Complete','WIP','Report Not sent','Cancelled exams'],placeholder='All statuses',key='statuses_v2')
selected = filter_operations(data,chosen_months,clients,owners,statuses)
active = selected[~selected.Cancelled]
completed = selected[selected['Complete exam']]
wip = selected[selected['WIP exam']]
st.download_button('Download complete data',raw.loc[selected.index].to_csv(index=False).encode('utf-8-sig'),'exam_operations.csv','text/csv',key='download_complete_data')
metrics = [('Exams',len(selected)),('Candidates',selected.Candidates.sum(min_count=1)),('Centres',selected.Centres.sum(min_count=1)),('Clients',selected.Client.nunique()),('Owners',selected.loc[selected.Owner.ne('Unassigned'),'Owner'].nunique())]
for col,(label,value) in zip(st.columns(5),metrics):
    col.metric(label,compact(value) if label=='Candidates' else ('No data' if pd.isna(value) else f'{value:,.0f}'))
for col,(label,value) in zip(st.columns(4),[('Complete',len(completed)),('Report Not sent',int(selected['Report Not sent'].sum())),('WIP',len(wip)),('Cancelled exams',int(selected.Cancelled.sum()))]):
    col.metric(label,value)

st.subheader('WORKLOAD OVERVIEW')
history = selected.dropna(subset=['Month']).groupby('Month').agg(Exams=('Exam','size'),Candidates=('Candidates',lambda s:s.sum(min_count=1))).reset_index()
history['Month label'] = history.Month.map(lambda m:pd.Timestamp(m+'-01').strftime('%b %Y'))
left,right = st.columns(2)
with left:
    st.markdown('**EXAMS BY MONTH**')
    bars(history,'Month label','Exams')
with right:
    st.markdown('**CANDIDATES BY MONTH**')
    bars(history,'Month label','Candidates',color='#12a899')
summary = owner_summary(selected)
owner_order = summary.Owner.tolist()
st.subheader('OWNER WORKLOAD')
left,right = st.columns(2)
with left:
    st.markdown('**EXAMS BY OWNER**')
    bars(summary,'Owner','Exams',order=owner_order)
with right:
    st.markdown('**CANDIDATE WORKLOAD**')
    bars(summary,'Owner','Candidates',color='#12a899',order=owner_order)
st.subheader('OWNER PERFORMANCE')
st.dataframe(summary[['Owner','Exams','Candidates','Centres']],hide_index=True,width='stretch')
st.subheader('PROCESS COMPLETION & CASE ANALYTICS')
# Full-width charts leave room for the process names and count labels.
draw_process(completed,'COMPLETED EXAMS')
draw_process(wip,'WIP EXAMS')
cases=[]
for label,source in {'Impersonation reported':'Impersonation cases reported','Impersonation found':'Impersonations found',**{k:v for k,v in CASE_COLUMNS.items() if k!='Impersonation'}}.items():
    values = number(active[source])
    across = (values.notna() & values.ne(0)).sum() if label=='Impersonation found' else values.notna().sum()
    cases.append({'Case type':label,'Reported count':values.sum(min_count=1),'Across Exams':int(across)})
st.dataframe(pd.DataFrame(cases),hide_index=True,width='stretch')

st.subheader('IMPERSONATION CASES BY OWNER')
comparison=[]
for owner_name,group in active.groupby('Owner',sort=True):
    for label,source in [('Reported','Impersonation cases reported'),('Found','Impersonations found')]:
        values=number(group[source])
        comparison.append({'Owner':owner_name,'Case type':label,'Cases':values.sum(min_count=1)})
comparison=pd.DataFrame(comparison,columns=['Owner','Case type','Cases'])
if comparison.empty:
    st.info('No matching exams.')
else:
    comparison['Label']=comparison.Cases.map(lambda n:'No data' if pd.isna(n) else f'{n:,.0f}')
    comparison['Plot']=comparison.Cases.fillna(0)
    chart=alt.Chart(comparison).encode(
        x=alt.X('Owner:N',sort=owner_order,title=None,axis=alt.Axis(labelAngle=0,ticks=False,domain=False)),
        xOffset=alt.XOffset('Case type:N',sort=['Reported','Found']),
        y=alt.Y('Plot:Q',title=None,axis=None,scale=alt.Scale(zero=True)),
        color=alt.Color('Case type:N',title=None,scale=alt.Scale(domain=['Reported','Found'],range=['#367bf5','#12a899'])),
        tooltip=['Owner:N','Case type:N',alt.Tooltip('Label:N',title='Cases')])
    st.altair_chart((chart.mark_bar(cornerRadiusTopLeft=4,cornerRadiusTopRight=4)+chart.mark_text(dy=-10).encode(text='Label:N',color=alt.value('#243c57'))).properties(height=300).configure_view(stroke=None),width='stretch')

st.subheader('ACTIVITY COMPLETION HEATMAP')
draw_heatmap(completed,'COMPLETED EXAMS')
draw_heatmap(wip,'WIP EXAMS')
st.subheader('ATTENTION REQUIRED')
actions=attention(active,today)[['Owner','Client','Exam','Date','Activity','Status']]
if actions.empty:
    st.success('No reports awaiting sending.')
else:
    st.dataframe(actions,hide_index=True,width='stretch')
    st.download_button('Download outstanding actions',actions.to_csv(index=False).encode('utf-8-sig'),'exam_followups.csv','text/csv')
