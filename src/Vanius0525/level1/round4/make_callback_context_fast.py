"""Runtime-only contextual optimizations. Preserve frozen trained/support variants."""
from pathlib import Path
import json,hashlib
from make_fast import vectorize
BASE=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
parents=['ai_context_callback_pure_summary_d6_m005', 'ai_context_callback_agg_summary_d6_m005', 'ai_context_callback_pure_exactactions_d6_m005', 'ai_context_callback_agg_exactactions_d6_m005'];records={}
for parent in parents:
    original=(OUT/(parent+'.cpp')).read_text();s=vectorize(original)
    # A necessary condition avoids full uniform-cycle scans on unconfirmed graphs.
    s=s.replace('bool uniform_cycle_=false;','bool uniform_cycle_=false;\n    int confirmed_edges_=0;',1)
    s=s.replace('if (confidence_[previous_id]==3) ++graph_version_;','if (confidence_[previous_id]==3) {++graph_version_;++confirmed_edges_;}')
    s=s.replace('} else {successor_[previous_id]=current_id;confidence_[previous_id]=1;++graph_version_;}', '} else {if(confidence_[previous_id]>=3)--confirmed_edges_;successor_[previous_id]=current_id;confidence_[previous_id]=1;++graph_version_;}')
    marker='recent_head_=recent_count_=0;graph_version_=0;analyzed_version_=-1;uniform_cycle_=false;';assert marker in s;s=s.replace(marker,marker+'confirmed_edges_=0;')
    marker='        if (last_op_<0) return;';assert s.count(marker)==1;s=s.replace(marker,'        if(confirmed_edges_!=static_cast<int>(history_.size()))return;\n'+marker)
    # Cache only exact feature tuples; the static neural function has no other input.
    marker='    double neural(const float* f) const {';assert s.count(marker)==1
    fields='''    mutable int prediction_count_=0;
    mutable float prediction_features_[4][12]={};
    mutable double prediction_values_[4]={};
'''
    lookup='''
        for(int j=0;j<prediction_count_;++j)
            if(std::memcmp(f,prediction_features_[j],12*sizeof(float))==0)return prediction_values_[j];'''
    s=s.replace(marker,fields+marker+lookup)
    marker='''        return std::max(0.0,std::min(1.0,y));''';assert s.count(marker)==1
    s=s.replace(marker,'''        const double result=std::max(0.0,std::min(1.0,y));
        if(prediction_count_<4) {
            std::copy(f,f+12,prediction_features_[prediction_count_]);
            prediction_values_[prediction_count_++]=result;
        }
        return result;''')
    marker='''    void forceMode(int mode)''';assert s.count(marker)==1
    s=s.replace(marker,'''    void beginChoices(){prediction_count_=0;}
    bool uniformVerified() const{return uniform_cycle_;}
'''+marker)
    marker='''        float context[12];family_.prepareFeatures(s,op,pid,z,miss,context);
        family_.forceMode(0);
        auto baseline=miss?family_.onPartitionMiss(s,op,pid):family_.onMemoryOverflow(s,op,pid,z);
        // When no space was released, every alternative is identical.
        if(baseline.empty() || (miss && baseline.size()==1))return baseline;
        float bf[8];family_.actionFeatures(s,baseline,bf);''';assert marker in s
    s=s.replace(marker,'''        family_.beginChoices();family_.forceMode(0);
        auto baseline=miss?family_.onPartitionMiss(s,op,pid):family_.onMemoryOverflow(s,op,pid,z);
        // No release, cold largest-first prefix, or equal-size PROBE cycle:
        // all three internal modes produce the same actions in valid trajectories.
        if(baseline.empty() || (miss && baseline.size()==1) ||
           s.hit_count+s.miss_count==0 || family_.uniformVerified())return baseline;
        float context[12];family_.gateFeatures(s,op,pid,z,context);
        float bf[8];family_.actionFeatures(s,baseline,bf);''')
    s='#include <cstring>\n'+s
    name=parent+'_fast';target=OUT/(name+'.cpp');target.write_text(s)
    records[name]={'parent':parent,'parent_sha256':hashlib.sha256(original.encode()).hexdigest(),'sha256':hashlib.sha256(s.encode()).hexdigest(),'changes':['baseline before pure context statistics','skip alternatives when no release, no Probe evidence, or uniform-cycle path','exact feature-tuple neural cache within each callback','neural loop interchange','necessary confirmed-edge count shortcut'],'claim':'Intended action-equivalent on valid actual trajectories; complete trajectory tests required before timing.'}
(OUT/'CALLBACK_CONTEXT_FAST_VARIANTS.json').write_text(json.dumps(records,indent=2)+'\n')
