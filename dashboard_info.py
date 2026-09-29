"""Secondary dashboard page for definitions and original filtered records."""
import streamlit as st


def render_info(original, data, selected, cancelled):
    st.header('Dashboard info')
    st.subheader('Calculation rules & data quality')
    st.markdown('''- **Exams:** one populated exam-code row is one operation; combined codes stay together. Cancelled/discarded operations are excluded.
- **Month:** the first listed exam date determines the month. Multi-month operations count only in their starting month. Unrecognized dates are excluded from monthly views.
- **Process completion:** Done, Sent, and No cases count as complete. Only Not sent counts as pending. Blank cells, WIP, other notes, Not required, N/A, and dashes are ignored. Completion is Complete / (Complete + Not sent). No evaluated cells means no percentage. The chart covers all seven processes, including photo mismatch to Ops and Delivery.
- **Overall status:** any Not sent cell makes the operation Pending. Otherwise, at least one complete cell makes it Complete. Operations with only ignored cells are Not evaluated. These operations remain in workload totals.
- **Workload:** candidate and centre values are summed per row; centres are not distinct physical locations. Unassigned owners are excluded from the Owners KPI.
- **Case table:** Reported count sums numeric values from the named source column. Impersonation reported and Impersonation found use separate source columns. Across Exams counts rows with a numeric entry, including zero. Blank and nonnumeric values are unknown, not zero.
- **Heatmap:** shows Not sent if any evaluated cell is Not sent, Complete if at least one is complete and none are Not sent, or gray if all are ignored.
- **Attention required:** only Not sent activities for exams that have started, based on India time. Blank and WIP cells do not appear.
- **Download complete data:** exports every original sheet column for the same filtered operation rows shown on the dashboard. Values are preserved as read from the sheet; calculated dashboard columns are not added.''')
    invalid = data[data.Date.isna()][['Client','Exam','Exam Date','Owner']]
    if not invalid.empty:
        st.warning(f'{len(invalid)} operations have unrecognized dates and are excluded from monthly views.')
        st.dataframe(invalid, hide_index=True, width='stretch')
    st.write('Missing or invalid numeric values in this selection:', {col:int(selected[col].isna().sum()) for col in ['Candidates','Centres','Shifts']})
    st.caption(f'{cancelled} cancelled/discarded rows excluded from all dashboard totals.')
    st.subheader('View selected exam records')
    st.caption(f'{len(original):,} filtered operations with all original sheet columns.')
    st.dataframe(original, hide_index=True, width='stretch')
