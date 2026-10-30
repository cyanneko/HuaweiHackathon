// RESOURCE_HEADER
#include <chrono>
#include <ctime>
#include <iostream>
#include <iomanip>
// This exercises only BoundedHitV1 on legal callback states. No scheduler,
// penalty proxy, cost ranking, hidden data, or official test input is used.
static int request_id(int64_t q) {return q%16?0:255+static_cast<int>((q/16)%257);}
static void execute(int period,int repeat,int64_t probes,bool print) {
    BoundedHitV1 estimator;BoundedHitV1::Mask resident{};
    for(int id=0;id<256;++id)resident[id/64]|=1ULL<<(id%64);
    // 512 partitions of 256KiB, 256 residents: exactly the 64MiB capacity.
    // A legal 512 INSERT + 8 SWITCH prefix precedes this all-PROBE continuation.
    int buffer=255;int64_t hits=0,misses=0;
    const auto cpu=std::clock();const auto wall=std::chrono::steady_clock::now();
    for(int64_t q=1;q<=probes;++q) {
        const int id=request_id(q),next=q<probes?request_id(q+1):-1;
        const bool hit=(resident[id/64]>>(id%64))&1ULL;
        if(hit)++hits;
        else {
            ++misses;estimator.before(512,true,q,hits,misses,resident,'M',id,next);
            resident[buffer/64]&=~(1ULL<<(buffer%64));resident[id/64]|=1ULL<<(id%64);buffer=id;
            estimator.after(resident);
        }
        if((512+q)%period==0){estimator.before(512,true,q,hits,misses,resident,'P',-1,next);estimator.after(resident);}
    }
    const double cpu_us=(std::clock()-cpu)*1e6/CLOCKS_PER_SEC;
    const double wall_us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-wall).count();
    if(print){const auto& c=estimator.counters();std::cout<<std::setprecision(17)
        <<"{\"period\":"<<period<<",\"repeat\":"<<repeat<<",\"probes\":"<<probes<<",\"hits\":"<<hits<<",\"misses\":"<<misses
        <<",\"process_cpu_us\":"<<cpu_us<<",\"wall_us\":"<<wall_us<<",\"sizeof_estimator\":"<<sizeof(BoundedHitV1)
        <<",\"callbacks\":"<<c.before_calls<<",\"fits\":"<<c.fits<<",\"em_fits\":"<<c.em_fits<<",\"max_blocks\":"<<c.max_blocks
        <<",\"max_probe_span\":"<<c.max_span<<",\"anonymous\":"<<c.hidden<<",\"member_visits\":"<<c.member_visits<<"}\n"<<std::flush;}
}
int main(){for(int period:{1,17})execute(period,-1,2048,false);for(int repeat=0;repeat<3;++repeat)for(int period:{1,17})execute(period,repeat,4999480,true);}
