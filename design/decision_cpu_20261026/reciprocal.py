from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'LeanScheduler.cpp').read_text('utf8')
a=s.index('    std::vector<Action> plan(');b=s.index('    static int64_t written(',a)
part=s[a:b]
part=part.replace('std::array<Victim,512> c;int n=','std::array<Victim,512> c;int n=')
part=part.replace('int n=0,best=-1;uint64_t now=tick(s);',
    'int n=0,best=-1;uint64_t now=tick(s);\n        double inv_w=0,inv_r=0;if(rule==4){inv_w=1.0/s.write_bandwidth;inv_r=1.0/s.read_bandwidth;}')
assert 'double inv_w' in part
part=part.replace('double(x.data_size)/s.write_bandwidth','double(x.data_size)*inv_w').replace('double(x.data_size)/s.read_bandwidth','double(x.data_size)*inv_r')
s=s[:a]+part+s[b:]
(ROOT/'ReciprocalScheduler.cpp').write_text(s,encoding='utf8')
e=(ROOT/'experiment.py').read_text('utf8').replace("'lean':'LeanScheduler.cpp'","'lean':'LeanScheduler.cpp','reciprocal':'ReciprocalScheduler.cpp'")
(ROOT/'experiment.py').write_text(e,encoding='utf8')
print('Generated reciprocal-hoisting candidate; floating-point decisions require separate verification.')
