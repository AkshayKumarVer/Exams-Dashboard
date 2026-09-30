import unittest
from datetime import date
import pandas as pd
from analytics import parse_start,normalize_status,rollup,prepare,completion,attention,ACTIVITIES,CASE_COLUMNS

class AnalyticsTests(unittest.TestCase):
    def test_date_ranges(self):
        for raw, expected in {"23 sep-05 Oct'26":'2026-09-23',"18 Aug-10 Sep'26":'2026-08-18',"17,18 Sep'26":'2026-09-17','20,27-Sep-26':'2026-09-20','24-Jun-26- 08-Jul-26':'2026-06-24','13-Jul-26-07-Aug-26':'2026-07-13','20 September 2026':'2026-09-20','46132':'2026-04-20'}.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_start(raw),pd.Timestamp(expected))
        self.assertTrue(pd.isna(parse_start('15,16,17')))
        self.assertTrue(pd.isna(parse_start('29,30 Jun & 1,2,3,4 Jul')))
    def make_row(self, code):
        row={'Client':'A','Exam code':code,'Exam Date':'20 September 2026','Owner from Product':'Alex','Candidate count':'1,200','Centres':'5','Shift':'2','Data cleaned by MIS':'Done','Impersonations found':'0'}
        row.update({source:'Done' for _,source in ACTIVITIES.values()})
        row.update({source:'' for source in CASE_COLUMNS.values()})
        return row

    def test_exam_classification(self):
        rows=[self.make_row(str(i)) for i in range(5)]
        rows[1][ACTIVITIES['Photo Quality'][1]]='Not Sent'
        rows[2][ACTIVITIES['Delivery'][1]]='  '
        rows[3]['Data cleaned by MIS']=' Cancelled '
        rows[4][ACTIVITIES['Delivery'][1]]=None
        rows[4][ACTIVITIES['Photo Quality'][1]]='Not sent'
        df,cancelled=prepare(pd.DataFrame(rows))
        self.assertEqual(len(df),5)
        self.assertEqual(cancelled,1)
        self.assertEqual(df['Complete exam'].sum(),2)
        self.assertEqual(df['WIP exam'].sum(),2)
        self.assertEqual(df['Report Not sent'].sum(),2)
        self.assertEqual(len(attention(df,date(2026,9,29))),2)
        self.assertEqual(df.Candidates.iloc[0],1200)
        from analytics import filter_operations,process_summary
        self.assertEqual(len(filter_operations(df,statuses=['Complete','Report Not sent'])),3)
        self.assertEqual(len(filter_operations(df,statuses=['Cancelled exams'])),1)
        self.assertTrue(filter_operations(df,owners=['Other']).empty)
        summary=process_summary(df[df['WIP exam']]).set_index('Process')
        self.assertEqual(summary.loc['Photo mismatch to Delivery','WIP'],2)
        self.assertEqual(summary.loc['Photo Quality','Not sent'],1)
        self.assertTrue((summary.Done+summary['Not sent']+summary.WIP==summary.Total).all())

    def test_cell_states(self):
        self.assertEqual(normalize_status(''),'WIP')
        self.assertEqual(normalize_status(None),'WIP')
        self.assertEqual(normalize_status(' WIP '),'WIP')
        self.assertEqual(normalize_status(' Not sent '),'Not sent')
        self.assertEqual(normalize_status('No cases'),'Complete')
        self.assertEqual(rollup(['Complete','WIP']),'WIP')

if __name__=='__main__': unittest.main()
