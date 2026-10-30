#include "process.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>

using namespace statgen;
template<class T>void arr(std::ostream&f,const std::vector<T>&a){f<<'[';for(size_t i=0;i<a.size();++i){if(i)f<<',';f<<a[i];}f<<']';}
struct Row{uint32_t flat,key;char type;};
int main(int argc,char**argv){try{
 std::map<std::string,std::string> args;
 const std::vector<std::string> allowed={"out","meta","trace","seed","n","k","p","memory","pressure","family","temporal","phase","build_fraction","size_sigma","write","read","penalty","period","tick","trace_every"};
 for(int i=1;i<argc;i+=2){if(i+1==argc||std::string(argv[i]).substr(0,2)!="--")throw std::runtime_error("expected --name value");std::string k=std::string(argv[i]).substr(2);if(std::find(allowed.begin(),allowed.end(),k)==allowed.end()||!args.emplace(k,argv[i+1]).second)throw std::runtime_error("unknown/duplicate argument");}
 for(const auto&k:allowed)if(!args.count(k))throw std::runtime_error("missing argument "+k);
 auto I=[&](const char*k){return std::stoll(args.at(k));};auto D=[&](const char*k){return std::stod(args.at(k));};
 int K=int(I("k")),P=int(I("p")),C=K*P;int64_t N=I("n"),M=I("memory");uint64_t seed=std::stoull(args.at("seed"));
 int W=int(I("write")),R=int(I("read")),penalty=int(I("penalty")),B=int(I("period"));
 double pressure=D("pressure"),fraction=D("build_fraction"),size_sigma=D("size_sigma");int64_t trace_every=I("trace_every");
 if(K<1||K>8||P<2||P>64||N<8000||N>5000000||M<67108864||M>4294967296LL||W<1||W>10000||R<1||R>10000||penalty<1||penalty>1000||B<1||B>10000||I("tick")!=64||trace_every<1||!std::isfinite(pressure)||pressure<=0||pressure>6||!std::isfinite(fraction)||fraction<.2||fraction>.5||!std::isfinite(size_sigma)||size_sigma<0||size_sigma>2||(args["phase"]!="shared"&&args["phase"]!="staggered"))throw std::runtime_error("invalid parameter range");
 Process process(C,args["family"],args["temporal"],seed);
 RNG phase_rng(seed^UINT64_C(0xa54ff53a5f1d36f1)),choice(seed^UINT64_C(0x510e527fade682d1)),keys(seed^UINT64_C(0x9b05688c2b3e6c1f)),sizes(seed^UINT64_C(0x1f83d9abfb41bd6b));
 std::vector<std::pair<int64_t,int>> schedule;
 for(int op=0;op<K;++op){double factor=args["phase"]=="shared"?1.:.7+.6*phase_rng.real();schedule.emplace_back(int64_t(N*fraction*factor),op);}
 std::sort(schedule.begin(),schedule.end());for(int i=1;i<K;++i)schedule[i].first=std::max(schedule[i].first,schedule[i-1].first+1);
 std::vector<int> switched(K);std::vector<int64_t> switch_at(K),build_count(C),probe_count(C),opbuild(K),opprobe(K);
 std::vector<double> build_weight(C),size_weight(C),cdf(C);double bw_sum=0;
 for(int i=0;i<C;++i){RNG rb(stream(seed,i,UINT64_C(0x5be0cd19137e2179))),rs(stream(seed,i,UINT64_C(0xcbbb9d5dc1059ed8)));build_weight[i]=std::exp(std::max(-1.5,std::min(1.5,.35*rb.normal())));bw_sum+=build_weight[i];size_weight[i]=std::exp(std::max(-4.,std::min(4.,size_sigma*rs.normal())));}
 for(auto&v:build_weight)v*=C/bw_sum;
 std::ofstream trace(args["trace"],std::ios::binary);if(!trace)throw std::runtime_error("cannot open trace");
 trace<<std::setprecision(17)<<"before_operation,switched_operators,probe_l1_since_last_tick,probe_max_probability";for(int i=0;i<C;++i)trace<<",p"<<i;trace<<'\n';
 auto p=process.probabilities();auto initial_p=p;double l1=0,l1sum=0,max_l1=0,max_p=*std::max_element(p.begin(),p.end()),sum_error=0;int64_t ticks=0,mixed_steps=0;
 auto refresh=[&](){double total=0;for(int i=0;i<C;++i){total+=switched[i/P]?C*p[i]:build_weight[i];cdf[i]=total;}for(auto&v:cdf)v/=total;cdf.back()=1.;};refresh();
 std::vector<Row> rows;rows.reserve(size_t(N));size_t next_switch=0;
 for(int64_t t=0;t<N;++t){
  if(t&&t%64==0){process.tick();auto pn=process.probabilities();l1=0;double sum=0;for(int i=0;i<C;++i){l1+=std::abs(pn[i]-p[i]);sum+=pn[i];}sum_error=std::max(sum_error,std::abs(sum-1));p.swap(pn);max_p=std::max(max_p,*std::max_element(p.begin(),p.end()));l1sum+=l1;max_l1=std::max(max_l1,l1);++ticks;refresh();}
  int active=std::accumulate(switched.begin(),switched.end(),0);if(active>0&&active<K)++mixed_steps;
  if(t%trace_every==0||t==N-1){trace<<t<<','<<active<<','<<l1<<','<<*std::max_element(p.begin(),p.end());for(double v:p)trace<<','<<v;trace<<'\n';}
  if(next_switch<schedule.size()&&t==schedule[next_switch].first){int op=schedule[next_switch].second;switched[op]=1;switch_at[op]=t;rows.push_back({uint32_t(op*P),0,'S'});++next_switch;refresh();continue;}
  int flat=int(std::lower_bound(cdf.begin(),cdf.end(),choice.real())-cdf.begin());if(flat>=C)throw std::runtime_error("sample outside support");int op=flat/P,pid=flat%P;
  uint32_t key=uint32_t(pid+P*keys.bounded((1000000000-pid)/P+1));
  if(!switched[op]){rows.push_back({uint32_t(flat),key,'I'});++build_count[flat];++opbuild[op];}
  else{rows.push_back({uint32_t(flat),key,'P'});++probe_count[flat];++opprobe[op];}
 }
 if(next_switch!=schedule.size())throw std::runtime_error("unfinished phases");
 for(int i=0;i<C;++i)if(build_count[i]==0)throw std::runtime_error("unintended empty partition: preserve failed seed");
 const int64_t build_total=int64_t(std::llround(pressure*M));auto budgets=allocate_bytes(build_count,size_weight,build_total,M);
 auto remaining=budgets,counts_left=build_count;
 std::ofstream out(args["out"],std::ios::binary);if(!out)throw std::runtime_error("cannot open input");
 out<<K<<' '<<P<<' '<<M<<' '<<W<<' '<<R<<' '<<penalty<<'\n'<<N<<' '<<B<<'\n';
 for(int op=0;op<K;++op)out<<op<<' '<<opbuild[op]<<' '<<opprobe[op]<<'\n';
 int64_t min_tuple=MAX_TUPLE,max_tuple=0;
 for(const auto&r:rows){int i=int(r.flat),op=i/P;
  if(r.type=='S'){out<<"SWITCH "<<op<<'\n';continue;}
  if(r.type=='P'){out<<"PROBE "<<op<<' '<<r.key<<'\n';continue;}
  int64_t left=counts_left[i],bytes=remaining[i];
  int64_t low=std::max<int64_t>(1,bytes-(left-1)*MAX_TUPLE),high=std::min<int64_t>(MAX_TUPLE,bytes-left+1);
  int64_t size=int64_t(std::llround((double(bytes)/left)*(.5+sizes.real())));size=std::max(low,std::min(high,size));
  remaining[i]-=size;--counts_left[i];min_tuple=std::min(min_tuple,size);max_tuple=std::max(max_tuple,size);
  out<<"INSERT "<<op<<' '<<r.key<<' '<<size<<'\n';
 }
 for(int i=0;i<C;++i)if(remaining[i]||counts_left[i])throw std::runtime_error("build allocation remainder");
 std::ofstream meta(args["meta"],std::ios::binary);if(!meta)throw std::runtime_error("cannot open metadata");
 meta<<std::setprecision(17)<<"{\"schema_version\":1,\"seed\":"<<seed<<",\"operations\":"<<N<<",\"K\":"<<K<<",\"P\":"<<P<<",\"memory\":"<<M
 <<",\"family\":\""<<args["family"]<<"\",\"temporal\":\""<<args["temporal"]<<"\",\"phase\":\""<<args["phase"]<<"\",\"operator_heat_process\":false"
 <<",\"build_bytes\":"<<build_total<<",\"realized_pressure\":"<<double(build_total)/M<<",\"min_tuple\":"<<min_tuple<<",\"max_tuple\":"<<max_tuple
 <<",\"max_partition_bytes\":"<<*std::max_element(budgets.begin(),budgets.end())<<",\"mixed_phase_steps_including_SWITCH\":"<<mixed_steps
 <<",\"ticks\":"<<ticks<<",\"max_probability_sum_error\":"<<sum_error<<",\"mean_probe_l1_per_tick\":"<<(ticks?l1sum/ticks:0)
 <<",\"max_probe_l1_per_tick\":"<<max_l1<<",\"maximum_probe_probability\":"<<max_p<<",\"build_counts\":";arr(meta,opbuild);meta<<",\"probe_counts\":";arr(meta,opprobe);
 meta<<",\"partition_inserts\":";arr(meta,build_count);meta<<",\"partition_probes\":";arr(meta,probe_count);meta<<",\"partition_bytes\":";arr(meta,budgets);
 meta<<",\"switch_at_zero_based\":";arr(meta,switch_at);meta<<",\"initial_probe_probabilities\":";arr(meta,initial_p);meta<<",\"final_probe_probabilities\":";arr(meta,p);
 meta<<",\"partition_processes\":[";for(int i=0;i<C;++i){if(i)meta<<',';const auto&x=process.nodes[i];meta<<"{\"flat_id\":"<<i<<",\"mode\":"<<x.mode<<",\"component\":"<<x.component<<",\"base_weight\":"<<std::exp(x.log_base)<<",\"log_deviation_bound\":"<<x.bound<<",\"shocks\":"<<x.shocks<<",\"reflections\":"<<x.reflections<<'}';}meta<<"]}\n";
 out.close();meta.close();trace.close();if(!out||!meta||!trace)throw std::runtime_error("write failed");
 std::cout<<"OK "<<N<<' '<<build_total<<'\n';
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
