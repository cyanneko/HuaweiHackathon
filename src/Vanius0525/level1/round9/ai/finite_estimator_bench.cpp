// Offline CPU kernel benchmark. The input contains legal observations only.
// No true probabilities, future requests, dataset labels, or engine modifications.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

struct Event {int64_t clock;char kind;int id=0,source=0;double count=0;std::string mask;};
struct Group {std::vector<int> members;double count=0;};
struct Snapshot {int prefix,iterations;double change;bool converged;std::vector<double> p;};
struct Trial {double total_us=0,update_us=0,query_us=0;size_t bytes=0,groups=0;std::vector<Snapshot> snapshots;};
using Clock=std::chrono::steady_clock;
double micros(Clock::time_point a,Clock::time_point b){return std::chrono::duration<double,std::micro>(b-a).count();}

Trial run(const std::string& method,const std::vector<Event>& events,int n) {
    const auto start=Clock::now();const bool next=method=="next_only",incremental=method=="incremental";
    std::vector<double> known,next_count,soft;
    if(incremental)soft.assign(n,64.0/n);
    else {next_count.assign(n,0);if(!next)known.assign(n,0);}
    double next_total=0,known_total=0,anonymous_total=0;
    std::vector<Group> groups;std::unordered_map<std::string,size_t> index;
    Trial result;size_t at=0;
    for(int prefix:{64,256,1024,4096}) {
        const auto update_start=Clock::now();
        while(at<events.size() && events[at].clock<=prefix) {
            const auto& e=events[at++];
            if(e.kind=='E') {
                if(e.source && !incremental) {++next_count[e.id];++next_total;}
                if(incremental)soft[e.id]+=1;
                else if(!next){++known[e.id];++known_total;}
            }else if(!next) {
                if(incremental) {
                    double mass=0;for(int i=0;i<n;++i)if(e.mask[i]=='1')mass+=soft[i];
                    if(!(mass>0))throw std::runtime_error("empty anonymous resident mass");
                    for(int i=0;i<n;++i)if(e.mask[i]=='1')soft[i]+=e.count*soft[i]/mass;
                }else {
                    std::string key((n+7)/8,'\0');
                    for(int i=0;i<n;++i)if(e.mask[i]=='1')key[i/8]=static_cast<char>(static_cast<unsigned char>(key[i/8])|(1u<<(i%8)));
                    auto found=index.find(key);size_t slot;
                    if(found==index.end()) {
                        slot=groups.size();Group row;
                        for(int i=0;i<n;++i)if(e.mask[i]=='1')row.members.push_back(i);
                        groups.push_back(std::move(row));index.emplace(std::move(key),slot);
                    }else slot=found->second;
                    groups[slot].count+=e.count;anonymous_total+=e.count;
                }
            }
        }
        result.update_us+=micros(update_start,Clock::now());
        const auto query_start=Clock::now();Snapshot snapshot{prefix,0,0,true,{}};
        snapshot.p.resize(n);
        if(next)for(int i=0;i<n;++i)snapshot.p[i]=(next_count[i]+64.0/n)/(next_total+64.0);
        else if(incremental) {
            const double total=std::accumulate(soft.begin(),soft.end(),0.0);
            for(int i=0;i<n;++i)snapshot.p[i]=soft[i]/total;
        }else {
            const bool full=method=="full_mle";
            const int budget=full?1000:std::stoi(method.substr(2));
            for(int i=0;i<n;++i)snapshot.p[i]=full?1.0/n:(next_count[i]+64.0/n)/(next_total+64.0);
            std::vector<double> proposed(n);const double denominator=known_total+anonymous_total+64.0;
            snapshot.converged=false;
            for(int step=1;step<=budget;++step) {
                for(int i=0;i<n;++i)proposed[i]=known[i]+64.0/n;
                for(const auto& group:groups) {
                    double mass=0;for(int i:group.members)mass+=snapshot.p[i];
                    if(!(mass>0))throw std::runtime_error("invalid EM group mass");
                    const double factor=group.count/mass;
                    for(int i:group.members)proposed[i]+=factor*snapshot.p[i];
                }
                double change=0;
                for(int i=0;i<n;++i){proposed[i]/=denominator;change=std::max(change,std::abs(proposed[i]-snapshot.p[i]));}
                snapshot.p.swap(proposed);snapshot.iterations=step;snapshot.change=change;
                snapshot.converged=change<1e-10;
                if(full && snapshot.converged)break;
            }
        }
        result.snapshots.push_back(std::move(snapshot));result.query_us+=micros(query_start,Clock::now());
    }
    result.total_us=micros(start,Clock::now());
    // Logical method-specific storage estimate; benchmark scaffolding is excluded.
    // Allocator/node metadata and output copies are not claimed to be measured RSS.
    result.bytes=2*static_cast<size_t>(n)*sizeof(double);
    if(!next && !incremental) {
        result.bytes=4*static_cast<size_t>(n)*sizeof(double)+groups.capacity()*sizeof(Group)+index.bucket_count()*sizeof(void*);
        for(const auto& group:groups)result.bytes+=group.members.capacity()*sizeof(int);
        for(const auto& entry:index)result.bytes+=sizeof(entry)+entry.first.capacity();
    }
    result.groups=groups.size();return result;
}

int main(int argc,char** argv) {
    if(argc!=2)return 2;std::ifstream in(argv[1]);int n,count;in>>n>>count;
    if(n<1 || n>512)throw std::runtime_error("bad object count");std::vector<Event> events;
    for(int j=0;j<count;++j) {
        Event e;in>>e.clock>>e.kind;
        if(e.kind=='E')in>>e.id>>e.source;
        else {in>>e.count>>e.mask;if(static_cast<int>(e.mask.size())!=n)throw std::runtime_error("bad mask");}
        if(!events.empty() && e.clock<events.back().clock)throw std::runtime_error("causal event order reversed");
        events.push_back(std::move(e));
    }
    if(!in)throw std::runtime_error("bad input");std::cout<<std::setprecision(17);
    const std::vector<std::string> methods={"next_only","incremental","em1","em4","em16","full_mle"};
    for(const auto& method:methods)run(method,events,n); // One fixed warm-up.
    for(int repeat=0;repeat<3;++repeat)for(size_t j=0;j<methods.size();++j) {
        const auto& method=methods[(j+repeat)%methods.size()];const Trial result=run(method,events,n);
        std::cout<<"TIME "<<method<<' '<<repeat<<' '<<result.total_us<<' '<<result.update_us<<' '<<result.query_us<<' '<<result.bytes<<' '<<result.groups<<'\n';
        if(repeat==0)for(const auto& s:result.snapshots) {
            std::cout<<"ROW "<<method<<' '<<s.prefix<<' '<<s.iterations<<' '<<s.change<<' '<<s.converged;
            for(double value:s.p)std::cout<<' '<<value;std::cout<<'\n';
        }
    }
}
