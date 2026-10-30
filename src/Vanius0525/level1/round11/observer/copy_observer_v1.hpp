// Appended public member methods; called only on a pre-callback deep copy.
public:
    void observerEmit(const SystemState& s,char tag,int op,int pid,int64_t required,
                      uint64_t callback,const std::vector<int>& thresholds,const std::vector<Action>& actual) const {
        static_assert(R80_MODE==2 && R74_SIZE==0,"observer is bound to exact R80 mode2 size0");
        obs11::require(tag=='M' || tag=='O',"unexpected observed callback");
        obs11::require(required>s.memory_limit-s.memory_used,"snapshot lacks release pressure");
        R80ObservedReference prepared(*this);
        prepared.active_=true;
        if(tag=='M')prepared.update(s,op,pid);else prepared.update(s);
        // Neither planner shares mutable vectors/caches with the actual scheduler or each other.
        R80ObservedReference hier(prepared),flat(prepared),view(prepared);
        std::vector<Action> ha,fa,actual_spills;
        hier.probability_cache_valid_=false;hier.propose(s,op,pid,required,ha,2);hier.pruneSpills(s,required,ha);
        flat.probability_cache_valid_=false;flat.propose(s,op,pid,required,fa,1);flat.pruneSpills(s,required,fa);
        for(const auto& a:actual)if(a.type==Action::SPILL)actual_spills.push_back(a);
        obs11::require(obs11::same(ha,actual_spills),"hier-copy spills differ from actual pruned spills");
        if(tag=='M')obs11::require(!actual.empty() && actual.back().type==Action::LOAD &&
            actual.back().op_id==op && actual.back().partition_id==pid,"actual demand LOAD missing");
        view.probability_cache_valid_=false;view.analyzeCycle(s);view.ensureProbabilities(s);
        const int n=static_cast<int>(view.next_mass_.size());
        for(int i=0;i<n;++i)view.ensureProbability(i);
        const int64_t now=s.hit_count+s.miss_count+1;
        const bool scan=view.streak_>=6 && view.stride_>0 && view.observed_count_*2>now;
        const bool cycle=view.uniform_cycle_;
        std::ostringstream out;out << std::setprecision(17);
        out << "OBS_STATE {\"callback\":" << callback << ",\"tag\":\"" << tag << "\",\"target_op\":" << op
            << ",\"target_partition\":" << pid << ",\"required_bytes\":" << required
            << ",\"q\":" << s.hit_count+s.miss_count << ",\"thresholds\":[";
        for(std::size_t j=0;j<thresholds.size();++j){if(j)out << ',';out << thresholds[j];}
        out << "],\"hier_copy_equals_actual_spills\":true,\"scan\":" << (scan?"true":"false")
            << ",\"cycle\":" << (cycle?"true":"false") << ",\"state\":";obs11::state(out,s);
        out << ",\"probability_clock\":" << view.probability_clock_ << ",\"next_sample_q\":" << view.next_sample_q_
            << ",\"total_mass\":";obs11::number(out,view.probability_total_);
        out << ",\"total_weight2\":";obs11::number(out,view.probability_weight2_);
        out << ",\"probability_prior_per_object\":";obs11::number(out,view.probability_prior_);
        out << ",\"probability_denom\":";obs11::number(out,view.probability_denom_);
        out << ",\"groups\":[";
        for(std::size_t o=0;o<view.sharing_.size();++o){if(o)out << ',';const auto& g=view.sharing_[o];
            out << "{\"op\":" << o << ",\"last\":" << g.last << ",\"mass\":";obs11::number(out,g.mass);
            out << ",\"squares\":";obs11::number(out,g.squares);out << ",\"weight2\":";obs11::number(out,g.weight2);
            out << ",\"share\":";obs11::number(out,g.share);out << ",\"heterogeneity\":";obs11::number(out,g.heterogeneity);
            out << ",\"n_eff\":";obs11::number(out,g.weight2>0?g.mass*g.mass/g.weight2:0.);out << '}';
        }
        out << "],\"objects\":[";
        for(int i=0;i<n;++i){if(i)out << ',';const int o=i/view.p_,pa=i%view.p_;
            const auto& part=s.operators[o].partitions[pa];const auto& c=view.next_mass_[i];
            const double mass=c.mass==0.?0.:c.mass*probabilityDecay(std::max<int64_t>(0,view.probability_clock_-c.last));
            const bool eligible=part.in_memory && part.data_size>0 && !(o==op && pa==pid);
            const bool protected_next=s.next_op.type=="PROBE" && s.next_op.op_id==o && s.next_op.key%view.p_==pa;
            const bool frequency=eligible && s.operators[o].phase==Phase::PROBE && !scan && !cycle;
            out << "{\"id\":" << i << ",\"op\":" << o << ",\"partition\":" << pa
                << ",\"size\":" << part.data_size << ",\"resident\":" << (part.in_memory?"true":"false")
                << ",\"eligible\":" << (eligible?"true":"false") << ",\"next_protected\":" << (protected_next?"true":"false")
                << ",\"frequency_branch\":" << (frequency?"true":"false") << ",\"mass\":";
            obs11::number(out,mass);out << ",\"flat_p\":";obs11::number(out,view.flat_probability_[i]);
            out << ",\"hier_p\":";obs11::number(out,view.hier_probability_[i]);out << '}';
        }
        out << "],\"actual_actions\":";obs11::actions(out,actual);
        out << ",\"hier_spills\":";obs11::actions(out,ha);out << ",\"flat_spills\":";obs11::actions(out,fa);
        out << ",\"cross_objectives\":{";
        auto objective=[&](const char* label,const std::vector<Action>& actions) {
            int64_t bytes=0;double ff=0,hh=0,protection=0;bool valid=!scan && !cycle;
            for(const auto& a:actions){const auto& part=s.operators[a.op_id].partitions[a.partition_id];
                const int id=a.op_id*view.p_+a.partition_id;bytes+=part.data_size;
                valid=valid && s.operators[a.op_id].phase==Phase::PROBE;
                const double cost=static_cast<double>(part.data_size)/s.read_bandwidth+
                    static_cast<double>(part.data_size)/s.write_bandwidth+100.;
                ff+=64.*view.flat_probability_[id]*cost;hh+=64.*view.hier_probability_[id]*cost;
                if(s.next_op.type=="PROBE" && s.next_op.op_id==a.op_id && s.next_op.key%view.p_==a.partition_id)
                    protection+=1e12*static_cast<double>(part.data_size);
            }
            const double write=static_cast<double>(bytes)/s.write_bandwidth;
            out << '"' << label << "\":{\"ordinary_frequency_objective_valid\":" << (valid?"true":"false")
                << ",\"victim_count\":" << actions.size() << ",\"spill_bytes\":" << bytes
                << ",\"released_excess_bytes\":" << bytes-(required-(s.memory_limit-s.memory_used))
                << ",\"actual_current_write_us\":";obs11::number(out,write);
            out << ",\"flat_future_proxy_us\":";obs11::number(out,ff);
            out << ",\"hier_future_proxy_us\":";obs11::number(out,hh);
            out << ",\"next_protection_term\":";obs11::number(out,protection);
            out << ",\"flat_subset_objective\":";obs11::number(out,ff+.25*write+protection);
            out << ",\"hier_subset_objective\":";obs11::number(out,hh+.25*write+protection);
            out << '}';
        };
        objective("hier_set",ha);out << ',';objective("flat_set",fa);out << "}}\n";
        std::cerr << out.str();
    }
