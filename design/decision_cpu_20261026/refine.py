from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    s=(ROOT/'PreviousScheduler.cpp').read_text('utf8')
    s=s.replace('++linear_plans;return {Action(Action::SPILL,c[chosen].o,c[chosen].p)};',
       '++linear_plans;std::vector<Action> a;a.reserve(build?1:3);a.emplace_back(Action::SPILL,c[chosen].o,c[chosen].p);return a;')
    s=s.replace('if(single>=0)return {Action(Action::SPILL,c[single].o,c[single].p)};',
       'if(single>=0){std::vector<Action> a;a.reserve(build?1:3);a.emplace_back(Action::SPILL,c[single].o,c[single].p);return a;}')
    s=s.replace('std::vector<Action> a;a.reserve(take);','std::vector<Action> a;a.reserve(take+(build?0:2));')
    # The final current LOAD is compulsory; one neighbour LOAD is the only extra.
    s=s.replace('auto a=plan(s,size,o,p,false);int64_t freed=written(s,a);',
       'auto a=plan(s,size,o,p,false);if(a.capacity()<a.size()+2)a.reserve(a.size()+2);int64_t freed=written(s,a);')
    (ROOT/'ReserveScheduler.cpp').write_text(s,encoding='utf8')
    s=s.replace('    struct Ghost', '    std::array<Victim,512> scratch_;\n    struct Ghost')
    s=s.replace('std::array<Victim,512> c;int n=', 'auto& c=scratch_;int n=')
    (ROOT/'ScratchScheduler.cpp').write_text(s,encoding='utf8')
    s=s.replace('for(auto& g:ghost_)if(g.at && !g.credited && now+1-g.at>width){credit(g.rule,0.0);g.credited=true;}',
       'for(int i=0,q=int(s.operators.size())*s.num_partitions;i<q;++i){auto& g=ghost_[i];if(g.at && !g.credited && now+1-g.at>width){credit(g.rule,0.0);g.credited=true;}}')
    s=s.replace('uint64_t now=tick(s);int mask=0;\n        for(const auto& op:s.operators)if(op.phase==Phase::PROBE)mask|=1<<op.op_id;',
       'uint64_t now=tick(s);int mask=phase_mask_;\n        if(mask!=((1<<int(s.operators.size()))-1)){mask=0;for(const auto& op:s.operators)if(op.phase==Phase::PROBE)mask|=1<<op.op_id;}')
    (ROOT/'LeanScheduler.cpp').write_text(s,encoding='utf8')
    e=(ROOT/'experiment.py').read_text('utf8')
    e=e.replace("'dynamic':'DynamicScheduler.cpp'", "'dynamic':'DynamicScheduler.cpp','reserve':'ReserveScheduler.cpp','scratch':'ScratchScheduler.cpp','lean':'LeanScheduler.cpp'")
    (ROOT/'experiment.py').write_text(e,encoding='utf8')
    print('Generated reserve, scratch reuse, and reduced bookkeeping variants.')
if __name__=='__main__':main()
