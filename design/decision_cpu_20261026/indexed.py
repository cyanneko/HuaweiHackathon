from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'LeanScheduler.cpp').read_text('utf8')
loc=s.index('    int flags_,rule_=4;')
fields='''    bool indexed_=false;
    int resident_count_=0;
    std::array<int,512> residents_,positions_;
    std::array<double,8> immutable_caps_{};
    void indexIfImmutable(const SystemState& s) {
        if(indexed_)return;
        for(const auto& op:s.operators)if(op.phase!=Phase::PROBE)return;
        positions_.fill(-1);resident_count_=0;
        for(const auto& op:s.operators)for(const auto& x:op.partitions){
            immutable_caps_[op.op_id]+=double(x.data_size);
            if(x.in_memory&&x.data_size>0){int id=op.op_id*s.num_partitions+x.partition_id;positions_[id]=resident_count_;residents_[resident_count_++]=id;}
        }
        indexed_=true;
    }
    void indexActions(const SystemState& s,const std::vector<Action>& a) {
        if(!indexed_)return;
        for(const auto& x:a) {
            int id=x.op_id*s.num_partitions+x.partition_id,pos=positions_[id];
            if(s.operators[x.op_id].partitions[x.partition_id].data_size<=0)continue;
            if(x.type==Action::SPILL&&pos>=0){int moved=residents_[--resident_count_];residents_[pos]=moved;positions_[moved]=pos;positions_[id]=-1;}
            else if(x.type==Action::LOAD&&pos<0){positions_[id]=resident_count_;residents_[resident_count_++]=id;}
        }
    }
'''
s=s[:loc]+fields+s[loc:]
# Update only after a final plan is chosen. Hypothetical alternatives do not
# mutate the resident index. The engine is sequential and all sizes are frozen.
a=s.index('    void remember(');b=s.index('    int requester_',a)
piece=s[a:b];needle='            } else loaded(s,x.op_id,x.partition_id);\n        }\n    }'
assert needle in piece
piece=piece.replace(needle,'            } else loaded(s,x.op_id,x.partition_id);\n        }\n        indexActions(s,a);\n    }')
s=s[:a]+piece+s[b:]
s=s.replace('for(const auto& x:op.partitions)cap[op.op_id]+=double(x.data_size);',
    'if(indexed_)cap[op.op_id]=immutable_caps_[op.op_id];else for(const auto& x:op.partitions)cap[op.op_id]+=double(x.data_size);')
a=s.index('    std::vector<Action> plan(');b=s.index('    static int64_t written(',a)
piece=s[a:b]
piece=piece.replace('int rule=build?0:rule_;','if(!build)indexIfImmutable(s);\n        int rule=build?0:rule_;')
needle='for(const auto& op:s.operators)for(const auto& x:op.partitions)if(x.in_memory)used[op.op_id]+=double(x.data_size);'
assert needle in piece
piece=piece.replace(needle,'''if(indexed_){for(int i=0;i<resident_count_;++i){int id=residents_[i];used[id/s.num_partitions]+=double(s.operators[id/s.num_partitions].partitions[id%s.num_partitions].data_size);}}
            else for(const auto& op:s.operators)for(const auto& x:op.partitions)if(x.in_memory)used[op.op_id]+=double(x.data_size);''')
begin=piece.index('        for(const auto& op:s.operators)for(const auto& x:op.partitions) {')
end=piece.index('        // The sorted greedy',begin)
block=piece[begin:end]
block=block.replace('        for(const auto& op:s.operators)for(const auto& x:op.partitions) {','        auto consider=[&](const OperatorState& op,const PartitionState& x) {',1)
block=block.replace('||(o==po&&p==pp))continue;','||(o==po&&p==pp))return;')
assert 'continue;' not in block
# Last brace belongs to the former loop, now the lambda.
assert block.endswith('        }\n')
block=block[:-10]+'''        };
        if(indexed_)for(int i=0;i<resident_count_;++i){int id=residents_[i];const auto& op=s.operators[id/s.num_partitions];consider(op,op.partitions[id%s.num_partitions]);}
        else for(const auto& op:s.operators)for(const auto& x:op.partitions)consider(op,x);
'''
piece=piece[:begin]+block+piece[end:]
s=s[:a]+piece+s[b:]
(ROOT/'IndexedScheduler.cpp').write_text(s,encoding='utf8')
e=(ROOT/'experiment.py').read_text('utf8').replace("'reciprocal':'ReciprocalScheduler.cpp'","'reciprocal':'ReciprocalScheduler.cpp','indexed':'IndexedScheduler.cpp'")
(ROOT/'experiment.py').write_text(e,encoding='utf8')
e=(ROOT/'prepare_strict.py').read_text('utf8').replace("('Reciprocal','Reciprocal')","('Reciprocal','Reciprocal'),('Indexed','Indexed')")
e=e.replace('    else throw std::runtime_error("Unknown profile");','    else if(name=="indexed")policy.reset(new IndexedScheduler());\n    else throw std::runtime_error("Unknown profile");')
(ROOT/'prepare_strict.py').write_text(e,encoding='utf8')
print('Generated resident index activated only after every operator enters PROBE.')
