# Maintainer information

This documentation is not exposed by the dashboard. There is no Info page or public admin route.

## Exam classification

- Each non-empty exam-code row is one operation. Combined codes remain one row.
- Cancelled exams: Data cleaned by MIS equals Cancelled (case-insensitive, surrounding spaces ignored; Canceled spelling also accepted). These rows remain available to filters, totals and original-data downloads.
- Complete: a non-cancelled exam with all seven activity cells populated after trimming whitespace. This measures filled cells, not whether all reports have been sent.
- WIP: a non-cancelled exam with at least one blank activity cell.
- Report Not sent: a non-cancelled exam with at least one activity marked Not sent. This overlaps Complete or WIP; it is not a mutually exclusive fourth category.
- Complete + WIP + Cancelled exams equals total selected operations.

## Activity charts and heatmaps

Completed and WIP exam cohorts are displayed separately. Cancelled exams are excluded from activity analytics and follow-ups. Blank activity cells and explicit WIP/in progress text are WIP. Not sent remains Not sent; other populated values count as Complete under the populated-cell rule. An exam whose cells are all populated can therefore be in the completed cohort while a literal WIP activity remains WIP in its heatmap.

Each process chart shows Done, Not sent, and Total. Total includes all exams in its cohort; Done + Not sent + WIP = Total. Percentage is Done / Total. Hover includes all counts. Heatmap hover always lists Complete, Not sent and WIP, including zero counts. Cell color precedence is Not sent, then WIP, then Complete.

## Filters and data

Months, clients, owners and status accept multiple selections. Empty selection means all. Values within each filter combine with OR; filters combine with AND. Status selection uses the overlapping flags above without duplicating rows.

Month is the first listed exam date. Ambiguous dates are logged on the server and excluded when a month filter is active; clearing the month filter includes them. Monthly workload charts show the selected months. Owners are alphabetical in both workload charts. Exam and workload totals include selected cancelled rows; case analytics and follow-ups use non-cancelled rows.

Download complete data exports original sheet columns and values for the exact filtered rows, without derived fields. Candidate and centre totals sum numeric values; missing values remain unknown. Across Exams includes numeric zeroes except for Impersonation found, which counts only non-zero numeric values. The reported/found owner chart sums its respective source columns.

Attention required retains only Not sent activities from non-cancelled exams whose starting date has arrived (India time). Blank cells and literal WIP are not added to attention required.

The Google Sheet is cached for 60 seconds. Refresh data forces a fresh read; idle pages do not poll automatically. Date warnings are available in server logs. No public Info route is registered.

Process bars use #469ec2 for Done and #a0d9ef for the remainder (Not sent plus WIP). Process bars are thicker with the numeric done count inside the done section and numeric total inside the end of the bar; the percentage is outside on the right. At zero completion the zero count appears inside the remainder bar. All counts remain available on hover.

Case counts and the impersonation owner chart sit side by side before the process charts. Dashboard tables use escaped HTML for consistent first-column-left and remaining-columns-centered alignment. Original data downloads remain available.


## Sheet-button processing report

Open Google Sheet downloads exam_processing_report.csv and opens the original sheet in a new tab from the same user click. The report uses the currently loaded sheet snapshot (refresh first for newer changes) and includes only rows not processed or excluded from date-based analysis because their date cannot be parsed. Processed rows, including numeric warnings, are omitted. This is a source-data exclusion report, not a list of rows hidden by the selected client, owner, status, or month filters. A clean sheet produces a headers-only report. Sheet row numbers preserve blank-row positions.

Report classifications distinguish Not processed (missing exam code or required columns), Partially processed - date issue (omitted by month filtering), Processed with warnings (such as missing/nonnumeric counts), and Processed. Missing optional case counts and blank activity cells are not processing errors. Cancelled exams are valid records with their existing exclusions. Negative or fractional numeric counts are flagged but their current dashboard treatment remains unchanged. Source URL and fetch time are included. Formula-like strings are exported as literal text for Excel safety.

The report is CSV, as requested, and opens in Excel. The browser must allow downloads and opening a new tab for the app. No file is downloaded during page render; the action requires the user's click. The report remains available even when required columns cause dashboard preparation to fail, provided the sheet itself can be loaded.
