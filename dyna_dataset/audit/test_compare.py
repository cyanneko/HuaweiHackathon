import copy,unittest
from run_audit import compare,check_configuration

def fixture():
    actual=dict(K=2,P=2,operations=6,memory=67108864,write=100,read=80,penalty=100,period=31,total_build_bytes=300,max_partition=200,
        build_counts=[1,1],probe_counts=[1,1],local_visit_counts=[2,2],longest_same_operator_run=2,
        mixed_phase_steps_including_SWITCH=3,partition_bytes=[100,0,0,200],partition_inserts=[1,0,0,1],
        partition_probes=[1,0,0,1],switch_at_zero_based=[1,4],last_probe_at_zero_based=[3,5],
        first_probe_at_zero_based=[3,5],last_insert_at_zero_based=[0,2],pressure=300/67108864,
        window_size=10000,window_op_counts_flat=[3,3],window_mixed_steps=[3],
        partition_windows=[dict(op=0,local_begin=0,local_end=2,global_end=4,visit_counts=[2,0],insert_counts=[1,0],probe_counts=[1,0]),
                           dict(op=1,local_begin=0,local_end=2,global_end=6,visit_counts=[0,2],insert_counts=[0,1],probe_counts=[0,1])])
    proc=dict(steps=6,min_probability=.5,max_probability=.5,max_probability_sum_error=0,mean_probability_l1_step=0,regime='normal')
    meta=dict(operations=6,K=2,P=2,memory=67108864,write=100,read=80,penalty=100,period=31,total_build_bytes=300,max_partition_bytes=200,
        actual_build_counts=[1,1],actual_probe_counts=[1,1],partition_local_visits=[2,2],longest_same_operator_run=2,
        mixed_phase_steps=3,partition_bytes=[[100,0],[0,200]],partition_counts=[[[1,0],[1,0]],[[0,1],[0,1]]],
        switch_steps=[2,5],last_probe_steps=[4,6],partition_last_visit_steps=[4,6],realized_pressure=300/67108864,
        min_active=2,max_active=2,single_active_steps=0,switch_thresholds=[2,4],phase='staggered',operator_process=proc,
        partition_processes=[dict(proc,steps=2),dict(proc,steps=2)])
    op=[dict(end_step=6,window_steps=6,mean_active=2,mixed_phase_steps=3,count_0=3,count_1=3,mean_p_0=.5,mean_p_1=.5,mean_probability_l1_step=0)]
    parts=[dict(operator=0,local_end=2,global_end=4,window_visits=2,build_visits=1,probe_visits=1,count_0=2,count_1=0,mean_q_0=.5,mean_q_1=.5,mean_probability_l1_step=0),
           dict(operator=1,local_end=2,global_end=6,window_visits=2,build_visits=1,probe_visits=1,count_0=0,count_1=2,mean_q_0=.5,mean_q_1=.5,mean_probability_l1_step=0)]
    return meta,actual,op,parts

class ComparisonTests(unittest.TestCase):
    def test_good(self):
        result=compare(*fixture());self.assertTrue(result['all_partition_windows_match'])
    def test_reject_false_actual_counts(self):
        args=fixture();args[0]['actual_build_counts'][0]=2
        with self.assertRaisesRegex(ValueError,'actual_build_counts'):compare(*args)
    def test_reject_time_threshold_violation(self):
        args=fixture();args[0]['switch_thresholds'][1]=3
        with self.assertRaisesRegex(ValueError,'INSERT at/after'):compare(*args)
    def test_reject_partition_window_counts(self):
        args=fixture();args[3][0]['count_0']=1
        with self.assertRaisesRegex(ValueError,'actual counts'):compare(*args)
    def test_reject_missing_partition_tail(self):
        args=fixture();args[3].pop()
        with self.assertRaisesRegex(ValueError,'row count'):compare(*args)
    def test_reject_invalid_probability_sum(self):
        args=fixture();args[3][0]['mean_q_0']=.9
        with self.assertRaisesRegex(ValueError,'mean probability'):compare(*args)
    def test_reject_normal_large_local_skew(self):
        args=fixture();args[3][0]['mean_q_0']=.56;args[3][0]['mean_q_1']=.44
        with self.assertRaisesRegex(ValueError,'normalization envelope'):compare(*args)
    def test_explicit_rare_hot_not_rejected_for_nonuniformity(self):
        args=fixture();args[0]['partition_processes'][0].update(regime='rare_hot',target_probabilities=[.8,.2],initial_probabilities=[.8,.2],min_probability=.2,max_probability=.8)
        args[3][0]['mean_q_0']=.8;args[3][0]['mean_q_1']=.2
        checked=compare(*args)
        self.assertEqual(checked['partition_process_quality'][0]['rare_pid'],0)
    def test_large_integer_seed_must_match_exactly(self):
        with self.assertRaisesRegex(ValueError,'seed'):
            check_configuration(dict(seed=202610307102,partition_processes=[]),dict(seed=202610307101))

if __name__=='__main__':unittest.main()
