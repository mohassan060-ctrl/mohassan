import os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
TMP=tempfile.TemporaryDirectory()
os.environ['VISASPONSOR_DB_PATH']=str(Path(TMP.name)/'test.sqlite3')
import workflow as w

class TestFlow(unittest.TestCase):
    def setUp(self):
        self.id='test:'+self._testMethodName
        w.upsert_jobs([dict(job_id=self.id,company='Example Inc',title='Communications Manager',location='London',url='https://example.org/jobs/123',description='This role values communications.',source='Greenhouse',match_score=82,sponsorship='Not stated',evidence='No sponsorship statement')])
    def test_unverified_cannot_be_approved(self):
        with self.assertRaisesRegex(ValueError,'Approval blocked'): w.set_stage(self.id,'Approved to apply')
    def test_history_not_enough(self):
        w.add_evidence(self.id,'Official sponsor register','Employer licensed / past sponsorship only','Listed company','https://example.org/register')
        self.assertFalse(w.sponsorship_assessment(w.get_evidence(self.id))[1])
    def test_explicit_role_positive_allows_approval(self):
        w.add_evidence(self.id,'Role posting','Explicit role sponsorship','Visa sponsorship is available for this role','https://example.org/jobs/123')
        w.set_stage(self.id,'Approved to apply')
        self.assertEqual(w.job_by_id(self.id)['status'],'Approved to apply')
    def test_negative_overrides_positive(self):
        w.add_evidence(self.id,'Role posting','Explicit role sponsorship','Sponsorship available','https://example.org/a')
        w.add_evidence(self.id,'Role posting','Explicit no sponsorship','No sponsorship offered','https://example.org/b')
        with self.assertRaises(ValueError):w.set_stage(self.id,'Approved to apply')
    def test_applied_requires_approval(self):
        with self.assertRaises(ValueError):w.set_stage(self.id,'Applied')
    def test_documents_are_real_docx(self):
        j=w.job_by_id(self.id);p={'verified_achievements':['Led a team of four'],'claims_to_confirm':[]}
        for data in [w.make_cv_docx(j,p),w.make_letter_docx(j,p),w.make_evidence_docx(j,w.get_evidence(self.id))]:
            self.assertEqual(data[:2],b'PK')

if __name__=='__main__':unittest.main()
