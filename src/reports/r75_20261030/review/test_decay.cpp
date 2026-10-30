#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include "risk.hpp"
bool same_bits(double a,double b) {
 uint64_t aa=0,bb=0;std::memcpy(&aa,&a,sizeof a);std::memcpy(&bb,&b,sizeof b);return aa==bb;
}
int main() {
 for(int64_t d=0;d<=20000;++d)
  assert(same_bits(r74::decay(d),std::exp(-static_cast<double>(d)/512.)));
 const int64_t gaps[]={1023,1024,1025,100000,1000000,INT64_C(1000000000000)};
 for(int64_t d:gaps)assert(same_bits(r74::decay(d),std::exp(-static_cast<double>(d)/512.)));
 std::cout<<"decay bitwise equality passed: 0..20000, boundaries, large gaps\n";
}
