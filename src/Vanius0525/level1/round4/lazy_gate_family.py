"""One-time expert selection after 32 visible probes; no hidden length or shadow traces."""
from gate_family import source as family_source

def source(gate='return 0;',force=-1):
    s=family_source(gate,force)
    field=f'int forced_mode_={force},last_mode_=0;';assert field in s
    s=s.replace(field,field+'\n    int selected_mode_=-1;')
    marker='recent_head_=recent_count_=0;graph_version_=0;analyzed_version_=-1;uniform_cycle_=false;';assert marker in s
    s=s.replace(marker,marker+'selected_mode_=-1;')
    marker='''        float gf[12];gateFeatures(s,op,pid,required,gf);
        const int mode=forced_mode_>=0?forced_mode_:gate(gf);last_mode_=mode;''';assert marker in s
    s=s.replace(marker,'''        int mode=forced_mode_;
        if(mode<0) {
            if(selected_mode_<0 && observed_count_>=32) {
                float gf[14];gateFeatures(s,op,pid,required,gf);
                gf[12]=std::log2(s.read_bandwidth/s.write_bandwidth)/14.;
                gf[13]=std::log2(s.write_bandwidth)/14.;
                selected_mode_=gate(gf);
            }
            mode=selected_mode_<0?0:selected_mode_;
        }
        last_mode_=mode;''')
    s=s.replace('''    void forceMode(int mode)''','''    bool gateReady(const SystemState& s) {
        analyzeCycle(s);return observed_count_>=32 && !uniform_cycle_;
    }
    void forceMode(int mode)''')
    return s
