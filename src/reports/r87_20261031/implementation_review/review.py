"""Static mathematical/source identity review only. Never invokes a compiler/policy."""
from pathlib import Path
import hashlib,json,difflib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
producer=ROOT/'tmp/r87_fixedshare/producer.json';p=read(producer);v=p['variants'][0]
assert sha(producer)=='2545e0d110a1685094a85e93b8525f336c47e60b1db5094326811f3f15a50d4f'
src=ROOT/v['source_path'];tu=ROOT/v['translation_unit_path'];parent=ROOT/'tmp/r85_ablations/R85_fast_prior8/MySpillScheduler.cpp'
assert sha(src)==v['source_sha256']=='c18b92a1ec0df7d36c68c0a424f7414abd000abce650c4f4d20183eb9699ef55'
assert sha(tu)==v['translation_unit_sha256'] and sha(parent)==v['parent_sha256']
a=parent.read_text(encoding='utf-8-sig');b=src.read_text(encoding='utf-8-sig');t=tu.read_text(encoding='utf-8-sig')
assert t.count(b)==1 and hashlib.sha256(t.replace(b,'<SCHEDULER>').encode()).hexdigest()==p['framework_sha256']=='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'
def function(s,needle):
    start=s.index(needle);opening=s.index('{',start);level=1;i=opening+1
    while level:
        level+=(s[i]=='{')-(s[i]=='}');i+=1
    return s[start:i]
unchanged=['void ensureProbability(', 'void refreshSharing(', 'double partitionBase(', 'double refaultReuse(', 'void release(', 'void pruneSpills(', 'std::vector<Action> onMemoryOverflow(', 'std::vector<Action> onPartitionMiss(', 'std::vector<Action> onPeriodicAdjust(']
for f in unchanged:assert function(a,f)==function(b,f),f
sample=function(b,'void sampleNext(')
assert sample.index('if(ordinal<=next_sample_q_)return;')<sample.index('advanceOperatorTotals(q)')<sample.index('updateOperatorWeight(op)')<sample.index('operator_fast_total_+=1.')<sample.index('fast_operator_[op].mass+=1.')
assert 'const int64_t q=std::max(ordinal,operator_total_q_);' in sample and 'probability_cache_valid_=false;' in sample
assert 'alpha+(1.-2.*alpha)*posterior' in function(b,'void updateOperatorWeight(')
release=read(ROOT/'tmp/r87_fixedshare/release.json');tests=read(ROOT/'tmp/r87_fixedshare/test_summary.json')
assert release['producer_sha256']==sha(producer) and release['test_summary_sha256']==sha(ROOT/'tmp/r87_fixedshare/test_summary.json') and tests['status']=='PASS' and release['active_child_processes']==0
checks=[
dict(topic='persistent totals',lines=[78,86,129,138],finding='Tfast/Tslow and operator_total_q are independent members. ensureProbabilities only lazily decays them; it separately resets and sums temporary probability totals. Extra accepted-event work O(1); probability queries retain O(K), no new KP scan.'),
dict(topic='pre-insertion predictive update',lines=[88,101,222,236],finding='New next ordinal is deduplicated before any refresh/share/count. Both persistent totals and selected fast/slow mass advance to common q. pf/ps use matching priors and counts excluding current label; rational posterior is log-loss eta1 update; alpha+(1-2alpha)posterior is sharing to OTHER expert.'),
dict(topic='clock and observations',lines=[132,133,223,225,366,381],finding='Only accepted public next PROBE inserts mass; current miss refresh/observe/refault does not add expert sample. Legal callbacks have monotonic hit+miss and next=q+1. max(ordinal,total_q) prevents rewind; max query q includes last accepted next and total clock. Arbitrarily delayed labels supplied through private test entry are outside official callback semantics, not an official engine bug.'),
dict(topic='query probabilities and conditional',lines=[147,165],finding='Query operator marginal is w*fast+(1-w)*slow. operator_scale divides by slow operator mass+64/K; unchanged ensureProbability supplies original adaptive slow conditional numerator. Joint sum is 1 up to roundoff under legal finite counts. No mixed probability feeds raw counts.'),
dict(topic='cache and reset',lines=[142,145,235,351,356,514],finding='Accepted sample invalidates probability cache; release already invalidates before any proposal; epoch wrap is unchanged. Dimension reset clears both totals, clock, weight=.5 and probability cache. Duplicate removal of refresh is harmless for legal callbacks: miss refresh and query refresh retain lazy aging without a learning trial.'),
dict(topic='legality and action boundary',lines=[348,381,539,563],finding='Added behavior uses public next and hit/miss counters and its own statistics only. Callback/action bodies, actual record, scan/cycle guards, partition refault base, H estimator, horizon64/proxy100 and official framework are unchanged. Positive K/P and valid IDs are inherited official legal-input assumptions.'),
dict(topic='numerical and theory limits',lines=[92,101,151,156],finding='Positive prior keeps legal prequential forecasts positive; finite/weight guards fall back to .5, clamp within alpha..1-alpha. This is not a general repair for corrupt/infinite state, nor bit identity with either endpoint. Prediction objective is on policy-selected observed next labels; no claim of IO/D improvement, unbiased full-access estimation or universal prior optimality.')]
files=[producer,src,tu,parent,ROOT/'tmp/r87_fixedshare/R87_fixedshare_op/parent.diff',ROOT/'tmp/r87_fixedshare/test_statistics.cpp',ROOT/'tmp/r87_fixedshare/test_behavior.cpp',ROOT/'tmp/r87_fixedshare/oracle.hpp',ROOT/'tmp/r87_fixedshare/test_summary.json',ROOT/'tmp/r87_fixedshare/release.json',ROOT/'docs/superpowers/plans/2026-10-30-r87-fixed-share-operator.md']
result=dict(status='PASS',blocking_findings=[],checks=checks,unchanged_function_bodies=unchanged,identities={f.relative_to(ROOT).as_posix():sha(f) for f in files},tests_scope='Read original test/oracle code and bound Root successful build summary; no tests or native re-executed by this reviewer.',producer_test_status=tests['status'],compile_test_seconds=tests['seconds'],native_runs_by_reviewer=0,compile_runs_by_reviewer=0,input_body_scans=0,active_child_processes=0)
with (OUT/'independent_review.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,ensure_ascii=False);f.write('\n')
print(json.dumps(dict(status='PASS',sha256=sha(OUT/'independent_review.json'))))
