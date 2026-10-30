import unittest
import runner as r
class RecoveryContract(unittest.TestCase):
    def test_fixed_replacement_rejects_partial_and_excludes_old_lastcase(self):
        cases=[{'case_id':'c'+str(i)} for i in range(10)];names=['A','B']
        old=[dict(case_id=c['case_id'],method=n,valid=True,origin='old') for c in cases for n in names]
        new=[dict(case_id='c9',method=n,valid=True,origin='new') for n in names]
        merged=r.merge_rows(cases,names,old,new,'c9')
        self.assertEqual(len(merged),20);self.assertTrue(all(x['origin']=='new' for x in merged if x['case_id']=='c9'))
        with self.assertRaises(AssertionError):r.merge_rows(cases,names,old,new[:-1],'c9')
        new[0]['valid']=False
        with self.assertRaises(AssertionError):r.merge_rows(cases,names,old,new,'c9')
if __name__=='__main__':unittest.main()
