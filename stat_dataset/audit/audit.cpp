// Independent stream validator: never calls or imports the generator.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include "sha256.hpp"

using i64 = long long;
void require(bool ok, const char* why) { if (!ok) throw std::runtime_error(why); }
struct Fields {
    const char* p;
    explicit Fields(const std::string& s): p(s.c_str()) {}
    void space() { while (*p==' ' || *p=='\t' || *p=='\r') ++p; }
    i64 integer() {
        space(); require(*p>='0' && *p<='9', "expected unsigned integer");
        i64 n=0;
        while (*p>='0' && *p<='9') {
            require(n<=100000000000000LL, "integer overflow/range");
            n=10*n+(*p++-'0');
        }
        require(!*p || *p==' ' || *p=='\t' || *p=='\r', "bad integer delimiter");
        return n;
    }
    std::string word() {
        space(); const char* q=p;
        while (*p && *p!=' ' && *p!='\t' && *p!='\r') ++p;
        return std::string(q,p);
    }
    void end() { space(); require(!*p, "extra tokens"); }
};
template<typename T> void arr(const std::vector<T>& a) {
    std::cout<<'[';
    for (size_t j=0;j<a.size();++j) { if(j)std::cout<<','; std::cout<<a[j]; }
    std::cout<<']';
}
struct PartitionWindow {
    i64 op,local_begin,local_end,global_begin,global_end;
    std::vector<i64> visits,inserts,probes;
};
int main(int argc,char** argv) {
    i64 line_no=0;
    try {
        require(argc>=2&&argc<=4,"usage: audit input.txt [operator_window] [partition_window]");
        const i64 window_size=argc>=3?std::stoll(argv[2]):10000;
        const i64 partition_window_size=argc>=4?std::stoll(argv[3]):10000;
        require(window_size>0&&partition_window_size>0,"invalid window size");
        std::ifstream f(argv[1]); require(bool(f),"cannot open input");
        std::string s,tail; i64 K,P,M,N,B; double W,R,penalty;
        require(bool(std::getline(f,s)),"missing header"); ++line_no;
        std::istringstream h(s); require(bool(h>>K>>P>>M>>W>>R>>penalty),"bad header");
        require(!(h>>tail),"extra header tokens");
        require(K>=1&&K<=8&&P>=2&&P<=64,"K/P range");
        require(M>=67108864LL&&M<=4294967296LL,"memory range");
        require(std::isfinite(W)&&W>=1&&W<=10000&&std::isfinite(R)&&R>=1&&R<=10000,"bandwidth range");
        require(std::isfinite(penalty)&&penalty>=1&&penalty<=1000&&penalty==std::floor(penalty),"penalty range/integer");
        require(bool(std::getline(f,s)),"missing N B"); ++line_no;
        Fields n(s); N=n.integer(); B=n.integer(); n.end();
        require(N>=1&&N<=5000000&&B>=1&&B<=10000,"N/B range");
        std::vector<i64> declared_i(K),declared_p(K),seen_i(K),seen_p(K),sw(K),sizes(K*P),ic(K*P),pc(K*P),switch_at(K,-1),finish_at(K,-1);
        std::vector<i64> first_insert_at(K,-1),last_insert_at(K,-1),first_probe_at(K,-1),last_probe_at(K,-1),local_visits(K),local_start(K),global_start(K,-1),global_last(K,-1);
        std::vector<std::vector<i64>> local_ic(K,std::vector<i64>(P)),local_pc(K,std::vector<i64>(P));
        std::vector<PartitionWindow> partition_windows;
        auto flush_partition=[&](i64 op){
            if(local_visits[op]==local_start[op])return;
            PartitionWindow row;row.op=op;row.local_begin=local_start[op];row.local_end=local_visits[op];
            row.global_begin=global_start[op];row.global_end=global_last[op]+1;
            row.inserts=local_ic[op];row.probes=local_pc[op];row.visits.resize(P);
            for(i64 p=0;p<P;++p)row.visits[p]=row.inserts[p]+row.probes[p];
            partition_windows.push_back(row);
            std::fill(local_ic[op].begin(),local_ic[op].end(),0);std::fill(local_pc[op].begin(),local_pc[op].end(),0);
            local_start[op]=local_visits[op];global_start[op]=-1;
        };
        SHA256 normalized,partition;
        normalized.integer(K);normalized.integer(P);partition.integer(K);partition.integer(P);
        i64 declared=K;
        for(i64 op=0;op<K;++op) {
            require(bool(std::getline(f,s)),"missing counts"); ++line_no;
            Fields x(s); require(x.integer()==op,"operator headers not ascending unique IDs");
            declared_i[op]=x.integer(); declared_p[op]=x.integer(); x.end();
            declared+=declared_i[op]+declared_p[op];
        }
        require(declared==N,"declared total mismatch");
        i64 mixed=0,global_mixed=0,build_bytes=0,ops=0,first_probe=-1,last_insert=-1,run=0,longest_run=0,previous_op=-1,window_mixed=0;
        std::vector<i64> window(K),window_rows,window_mixed_rows;
        for(;ops<N;++ops) {
            require(bool(std::getline(f,s)),"truncated operations"); ++line_no;
            Fields x(s); auto type=x.word(); i64 op=x.integer(); require(op<K,"operator out of range");
            ++window[op];
            if(op==previous_op)++run;else{run=1;previous_op=op;}longest_run=std::max(longest_run,run);
            i64 switching=0;for(auto z:sw)switching+=z;
            if(switching>0&&switching<K){++global_mixed;++window_mixed;}
            if(type=="SWITCH") {
                normalized.update("S",1);normalized.integer(op);partition.update("S",1);partition.integer(op);
                require(sw[op]==0&&seen_i[op]==declared_i[op],"invalid SWITCH phase/count");
                sw[op]=1;switch_at[op]=ops;
            } else {
                i64 key=x.integer(); require(key<=1000000000LL,"key range"); i64 idx=op*P+key%P;
                if(switching>0&&switching<K)++mixed;
                if(type=="INSERT") {
                    last_insert=ops;
                    if(first_insert_at[op]<0)first_insert_at[op]=ops;
                    last_insert_at[op]=ops;
                    require(!sw[op],"INSERT after SWITCH"); i64 bytes=x.integer();
                    require(bytes>=1&&bytes<=1048576,"tuple size range");
                    normalized.update("I",1);normalized.integer(op);normalized.integer(key);normalized.integer(bytes);
                    partition.update("I",1);partition.integer(op);partition.integer(key%P);partition.integer(bytes);
                    sizes[idx]+=bytes; build_bytes+=bytes; ++seen_i[op]; ++ic[idx];
                    ++local_ic[op][key%P];
                    require(seen_i[op]<=declared_i[op],"too many INSERTs");
                    require(sizes[idx]<=M,"partition cannot fit memory");
                } else if(type=="PROBE") {
                    normalized.update("P",1);normalized.integer(op);normalized.integer(key);
                    partition.update("P",1);partition.integer(op);partition.integer(key%P);
                    if(first_probe<0) first_probe=ops;
                    if(first_probe_at[op]<0)first_probe_at[op]=ops;
                    last_probe_at[op]=ops;
                    require(sw[op]==1,"PROBE before SWITCH"); ++seen_p[op]; ++pc[idx];
                    ++local_pc[op][key%P];
                    require(seen_p[op]<=declared_p[op],"too many PROBEs");
                } else throw std::runtime_error("unknown operation");
                if(global_start[op]<0)global_start[op]=ops;
                global_last[op]=ops;++local_visits[op];
                if(local_visits[op]%partition_window_size==0)flush_partition(op);
            }
            x.end();
            if(sw[op]&&seen_p[op]==declared_p[op])finish_at[op]=ops;
            if((ops+1)%window_size==0||ops+1==N) {
                window_rows.insert(window_rows.end(),window.begin(),window.end());
                window_mixed_rows.push_back(window_mixed);window_mixed=0;
                std::fill(window.begin(),window.end(),0);
            }
        }
        require(!std::getline(f,s),"extra lines after N");
        for(i64 op=0;op<K;++op)require(sw[op]==1&&seen_i[op]==declared_i[op]&&seen_p[op]==declared_p[op],"final counts mismatch");
        for(i64 op=0;op<K;++op)flush_partition(op);
        std::vector<double> chi_i(K),chi_p(K),max_z_i(K),max_z_p(K);
        for(i64 op=0;op<K;++op)for(i64 p=0;p<P;++p) {
            const double ei=double(seen_i[op])/P,ep=double(seen_p[op])/P;
            if(ei>0){ double d=ic[op*P+p]-ei; chi_i[op]+=d*d/ei;max_z_i[op]=std::max(max_z_i[op],std::abs(d)/std::sqrt(ei*(1.-1./P))); }
            if(ep>0){ double d=pc[op*P+p]-ep; chi_p[op]+=d*d/ep;max_z_p[op]=std::max(max_z_p[op],std::abs(d)/std::sqrt(ep*(1.-1./P))); }
        }
        std::cout<<std::setprecision(17)<<"{\"valid\":true,\"operations\":"<<ops<<",\"K\":"<<K<<",\"P\":"<<P<<",\"memory\":"<<M
                 <<",\"write\":"<<W<<",\"read\":"<<R<<",\"penalty\":"<<penalty<<",\"period\":"<<B
                 <<",\"total_build_bytes\":"<<build_bytes<<",\"pressure\":"<<double(build_bytes)/M
                 <<",\"max_partition\":"<<*std::max_element(sizes.begin(),sizes.end())<<",\"mixed_phase_operations\":"<<mixed
                 <<",\"mixed_phase_steps_including_SWITCH\":"<<global_mixed<<",\"longest_same_operator_run\":"<<longest_run
                 <<",\"first_probe_zero_based\":"<<first_probe<<",\"last_insert_zero_based\":"<<last_insert;
        std::cout<<",\"build_counts\":";arr(seen_i);std::cout<<",\"probe_counts\":";arr(seen_p);
        std::cout<<",\"partition_bytes\":";arr(sizes);std::cout<<",\"partition_inserts\":";arr(ic);std::cout<<",\"partition_probes\":";arr(pc);
        std::cout<<",\"switch_at_zero_based\":";arr(switch_at);std::cout<<",\"finished_at_zero_based\":";arr(finish_at);
        std::cout<<",\"first_insert_at_zero_based\":";arr(first_insert_at);std::cout<<",\"last_insert_at_zero_based\":";arr(last_insert_at);
        std::cout<<",\"first_probe_at_zero_based\":";arr(first_probe_at);std::cout<<",\"last_probe_at_zero_based\":";arr(last_probe_at);
        std::cout<<",\"local_visit_counts\":";arr(local_visits);
        std::cout<<",\"insert_uniform_chi2\":";arr(chi_i);std::cout<<",\"probe_uniform_chi2\":";arr(chi_p);
        std::cout<<",\"insert_uniform_max_z\":";arr(max_z_i);std::cout<<",\"probe_uniform_max_z\":";arr(max_z_p);
        std::cout<<",\"window_size\":"<<window_size<<",\"partition_window_size\":"<<partition_window_size<<",\"window_op_counts_flat\":";arr(window_rows);
        std::cout<<",\"window_mixed_steps\":";arr(window_mixed_rows);
        std::cout<<",\"partition_windows\":[";
        for(size_t i=0;i<partition_windows.size();++i){const auto&x=partition_windows[i];if(i)std::cout<<',';
            std::cout<<"{\"op\":"<<x.op<<",\"local_begin\":"<<x.local_begin<<",\"local_end\":"<<x.local_end
                     <<",\"global_begin\":"<<x.global_begin<<",\"global_end\":"<<x.global_end;
            std::cout<<",\"visit_counts\":";arr(x.visits);std::cout<<",\"insert_counts\":";arr(x.inserts);std::cout<<",\"probe_counts\":";arr(x.probes);std::cout<<'}';}
        std::cout<<']';
        std::cout<<",\"normalized_operation_sha256\":\""<<normalized.digest()<<"\",\"partition_stream_sha256\":\""<<partition.digest()<<"\"}\n";
    } catch(const std::exception& e) { std::cerr<<"line "<<line_no<<": "<<e.what()<<'\n';return 1; }
}
