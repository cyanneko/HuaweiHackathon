#include <cmath>
#include <cstdint>
namespace r74 {
struct Risk {
 double exposure=0, events=0, starts=0; int active=0; int64_t last=0;
 void advance(int64_t q) {
  if(q<=last)return;
  if(!active && exposure==0. && events==0. && starts==0.) {last=q;return;}
  const double f=std::exp(-static_cast<double>(q-last)/512.);
  exposure=exposure*f+active*512.*(1.-f);
  events*=f; starts*=f; last=q;
 }
 void begin(int64_t q) {advance(q); ++active; ++starts;}
 void end(int64_t q,bool event) {advance(q); --active; if(event)++events;}
 double mean(int64_t q,double prior=64.) {advance(q); return (exposure+prior)/(events+1.);}
};
}
