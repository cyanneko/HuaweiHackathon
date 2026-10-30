#include TEST_INCLUDE
#include "oracle.hpp"
// Only old interfaces/fields are used, so the parent must compile and fail on
// its actual pure-fast probability, not on a missing candidate declaration.
int main(){
 auto s=fixture(3,4);MySpillScheduler x;x.update(s);Oracle oracle(3,4);
 oracle.check_probabilities(x,s,0);
 for(int q=1;q<=12;++q){int o=q<8?0:2,j=q%4;oracle.sample(o,j,q);x.sampleNext(o,j,q);oracle.check_probabilities(x,s,q);}
 std::cout<<"integrated mixture behavior PASS\n";
}
