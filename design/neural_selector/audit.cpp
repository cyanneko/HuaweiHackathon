// Independent full-trace action/capacity audit. Not used for SDK timing.
#define main offline_label_main
#include "teacher.cpp"
#undef main
static void invariant(const Simulator& s) {
    int64_t used=0;
    for(const auto& o:s.ops)for(const auto& p:o.partitions){
        if(p.data_size<0)throw std::runtime_error("negative size");
        if(p.in_memory)used+=p.data_size;
    }
    if(used!=s.used||used<0||used>s.input->m)throw std::runtime_error("memory sum mismatch");
}
int main(int argc,char** argv){try{
    if(argc!=4)return 2;
    std::ifstream list(argv[1]);std::ofstream out(argv[2]);int mode=std::stoi(argv[3]),n=0;std::string path;
    if(!list||!out)throw std::runtime_error("audit files");
    while(std::getline(list,path)){
        if(!path.empty()&&path.back()=='\r')path.pop_back();if(path.empty())continue;
        Input x=read(path);Simulator s(x,mode);
        while(s.pos<int(x.rows.size())){s.step();if(s.pos%1024==0)invariant(s);}
        invariant(s);
        out<<std::setprecision(17)<<"{\"file\":"<<quoted(path)<<",\"mode\":"<<mode
            <<",\"io\":"<<s.io<<",\"miss\":"<<s.miss<<",\"hit\":"<<s.hit
            <<",\"hash\":"<<s.action_hash<<",\"inferences\":"<<s.policy.inferenceCount()<<"}\n";
        if(++n%128==0)std::cerr<<"Audited "<<n<<" cases\n";
    }
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
