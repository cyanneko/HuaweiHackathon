#include <cassert>
#include <cmath>
#include <iostream>
#include "risk.hpp"
int main() {
 r74::Risk a; a.begin(0); const double cold=a.mean(64);
 assert(cold>120. && cold<125.); // ongoing cold episode contributes exposure
 a.end(64,true); assert(a.mean(64)>60. && a.mean(64)<63.);
 r74::Risk censored; censored.begin(0); censored.end(32,false);
 assert(censored.events==0 && censored.active==0 && censored.mean(32)>94.);
 const double e=censored.exposure; censored.advance(64);
 assert(censored.exposure<e); // no exposure after prefetch censor
 r74::Risk op; op.begin(0); op.begin(0); op.advance(64);
 r74::Risk one; one.begin(0); one.advance(64);
 assert(std::abs(op.exposure-2*one.exposure)<1e-10);
 const double old=one.exposure; one.advance(64); assert(one.exposure==old);
 r74::Risk dense; dense.begin(0); for(int i=1;i<=64;++i)dense.advance(i);
 assert(std::abs(dense.exposure-one.exposure)<1e-8); // callback-frequency invariance
 std::cout<<"risk tests passed\n";
}
