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
    def test_status(self):
        self.assertEqual(normalize_status('No Cases'),'Complete')
        self.assertEqual(normalize_status('Portal not working'),'N/A')
        self.assertEqual(normalize_status(''),'N/A')
        self.assertEqual(normalize_status('Not required'),'N/A')
        self.assertEqual(normalize_status('WIP'),'N/A')
        self.assertEqual(normalize_status(' Not Sent '),'Pending')
        self.assertEqual(rollup(['Complete','Pending','N/A']),'Pending')
        self.assertEqual(rollup(['N/A','Complete']),'Complete')
        self.assertEqual(rollup(['N/A','N/A']),'N/A')
    def test_aggregation_and_attention(self):
        row={'Client':'A','Exam code':'x','Exam Date':'20 September 2026','Owner from Product':'Alex','Candidate count':'1,200','Centres':'5','Shift':'2'}
        row.update({source:'Done' for _,source in ACTIVITIES.values()})
        row.update({source:'' for source in CASE_COLUMNS.values()})
        row[ACTIVITIES['Photo Quality'][1]]='Not Sent'
        row[ACTIVITIES['Pre-Dedupe'][1]]='Not required'
        df,_=prepare(pd.DataFrame([row]))
        self.assertEqual(df.Candidates.iloc[0],1200)
        self.assertAlmostEqual(completion(df),5/6*100)
        actions=attention(df,date(2026,9,29))
        self.assertEqual(len(actions),1)
        self.assertEqual(actions.Status.iloc[0], 'Not sent')
        self.assertEqual(actions.Age.iloc[0],9)
        self.assertTrue(attention(df,date(2026,9,19)).empty)
        row.update({source:'' for _,source in ACTIVITIES.values()})
        row[ACTIVITIES['Photo Quality'][1]] = 'WIP'
        df,_ = prepare(pd.DataFrame([row]))
        self.assertEqual(df.Status.iloc[0], 'N/A')
        self.assertIsNone(completion(df))
        self.assertTrue(attention(df,date(2026,9,29)).empty)
        row[ACTIVITIES['Pre-Dedupe'][1]] = 'Done'
        row[ACTIVITIES['Duplicate'][1]] = 'Not sent'
        df,_ = prepare(pd.DataFrame([row]))
        self.assertEqual(completion(df),50)
        self.assertEqual(len(attention(df,date(2026,9,29))),1)

if __name__=='__main__': unittest.main()
