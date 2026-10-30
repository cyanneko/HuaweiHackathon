#include "../audit/sha256.hpp"
#include <cassert>
#include <iostream>
int main(){SHA256 s;assert(s.digest()=="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");s.update("abc",3);assert(s.digest()=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");SHA256 a;for(int i=0;i<1000000;++i)a.update("a",1);assert(a.digest()=="cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");std::cout<<"SHA256 known vectors PASS\n";}
