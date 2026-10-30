#include <cmath>
#include <array>
#include <cstdint>
namespace r74 {
inline double decay(int64_t delta) {
 // Lazy initialization occurs inside the first real Risk.advance call.
 // Direct exp evaluation preserves the original expression per entry.
 static const std::array<double,1025> table=[]() {
  std::array<double,1025> values{};
  for(int i=0;i<=1024;++i)values[i]=std::exp(-static_cast<double>(i)/512.);
  return values;
 }();
 return delta>=0 && delta<=1024 ? table[static_cast<std::size_t>(delta)]
     : std::exp(-static_cast<double>(delta)/512.);
}

struct Risk {
 double exposure=0, events=0, starts=0; int active=0; int64_t last=0;
 void advance(int64_t q) {
  if(q<=last)return;
  if(!active && exposure==0. && events==0. && starts==0.) {last=q;return;}
  const double f=decay(q-last);
  exposure=exposure*f+active*512.*(1.-f);
  events*=f; starts*=f; last=q;
 }
 void begin(int64_t q) {advance(q); ++active; ++starts;}
 void end(int64_t q,bool event) {advance(q); --active; if(event)++events;}
 double mean(int64_t q,double prior=64.) {advance(q); return (exposure+prior)/(events+1.);}
};
}
