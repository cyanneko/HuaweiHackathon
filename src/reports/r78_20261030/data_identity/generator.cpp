// R72 hierarchical probability/velocity generator. C++14, bounded streaming state.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

struct RNG {
    uint64_t state;
    explicit RNG(uint64_t seed) : state(seed) {}
    uint64_t next() {
        uint64_t z = (state += UINT64_C(0x9e3779b97f4a7c15));
        z = (z ^ (z >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
        z = (z ^ (z >> 27)) * UINT64_C(0x94d049bb133111eb);
        return z ^ (z >> 31);
    }
    double real() { return (next() >> 11) * (1.0 / 9007199254740992.0); }
    uint64_t bounded(uint64_t n) {
        const uint64_t threshold = uint64_t(-n) % n;
        for (;;) { const uint64_t x = next(); if (x >= threshold) return x % n; }
    }
};

struct Parameters { double rho, sigma, large_probability, large_multiplier, vmax; };
Parameters parameters(const std::string& name, double scale) {
    Parameters x;
    if (name == "slow") x = {.9995, .000002, .00001, 20., .003};
    else if (name == "fast") x = {.97, .0002, .00001, 20., .01};
    else if (name == "burst") x = {.999, .0000003, .00002, 1000., .006};
    else throw std::runtime_error("unknown process profile");
    x.sigma *= scale; x.vmax *= scale; return x;
}

template<class T> void array(std::ostream& f, const std::vector<T>& values) {
    f << '[';
    for (size_t i = 0; i < values.size(); ++i) { if (i) f << ','; f << values[i]; }
    f << ']';
}

struct Process {
    std::string name;
    std::string regime = "operator";
    Parameters cfg;
    double scale, floor, relative_band = 0, mean_reversion = 0, max_relative_target_deviation = 0;
    int rare_pid = -1;
    RNG rng;
    std::vector<double> probability, velocity, pending, initial_probabilities, target_probabilities;
    int64_t steps = 0, large_events = 0, reflections = 0;
    double minimum, maximum, sum_error = 0, l1_sum = 0;
    Process(int dimensions, const std::string& profile, double multiplier, uint64_t seed)
        : name(profile), cfg(parameters(profile, multiplier)), scale(multiplier), floor(.0001/dimensions),
          rng(seed), probability(dimensions, 1.0/dimensions), velocity(dimensions), pending(dimensions),
          initial_probabilities(probability), target_probabilities(probability),
          minimum(1.0/dimensions), maximum(1.0/dimensions) {}
    void configure_partition(const std::vector<double>& initial, const std::vector<double>& target,
                             const std::string& label, int exceptional_pid) {
        regime = label; rare_pid = exceptional_pid; probability = initial;
        initial_probabilities = initial; target_probabilities = target;
        name = "partition_slow"; cfg.rho = .9998; cfg.large_probability = .0000001; cfg.large_multiplier = 100;
        relative_band = .05; mean_reversion = 1.0/50000;
        minimum = *std::min_element(initial.begin(), initial.end());
        maximum = *std::max_element(initial.begin(), initial.end());
        for (size_t i=0;i<initial.size();++i)
            max_relative_target_deviation=std::max(max_relative_target_deviation,std::abs(initial[i]/target[i]-1));
    }
    int sample(RNG& choice) const {
        const double target = choice.real(); double cumulative = 0;
        for (size_t i = 0; i < probability.size(); ++i) {
            cumulative += probability[i];
            if (target < cumulative) return int(i);
        }
        return int(probability.size())-1;
    }
    double update() {
        const int dimensions = int(probability.size());
        double mean = 0;
        for (int i = 0; i < dimensions; ++i) {
            const bool large = rng.real() < cfg.large_probability;
            if (large) ++large_events;
            const double noise = (2*rng.real()-1) * cfg.sigma * (large ? cfg.large_multiplier : 1);
            velocity[i] = std::max(-cfg.vmax, std::min(cfg.vmax, cfg.rho*velocity[i]+noise));
            mean += velocity[i]/dimensions;
        }
        double total = 0;
        for (int i = 0; i < dimensions; ++i) {
            velocity[i] -= mean;
            pending[i] = probability[i] + velocity[i] + mean_reversion*(target_probabilities[i]-probability[i]);
            const double lower = relative_band ? (1-relative_band)*target_probabilities[i] : floor;
            const double upper = relative_band ? (1+relative_band)*target_probabilities[i] : 2.;
            if (pending[i] < lower) {
                pending[i] = lower; velocity[i] = std::abs(velocity[i])*.25; ++reflections;
            } else if (pending[i] > upper) {
                pending[i] = upper; velocity[i] = -std::abs(velocity[i])*.25; ++reflections;
            }
            total += pending[i];
        }
        double l1 = 0, sum = 0;
        for (int i = 0; i < dimensions; ++i) {
            pending[i] /= total;
            if (!std::isfinite(pending[i]) || pending[i] <= 0) throw std::runtime_error("invalid process probability");
            l1 += std::abs(pending[i]-probability[i]);
            probability[i] = pending[i];
            sum += probability[i];
            minimum = std::min(minimum, probability[i]); maximum = std::max(maximum, probability[i]);
            max_relative_target_deviation=std::max(max_relative_target_deviation,std::abs(probability[i]/target_probabilities[i]-1));
        }
        ++steps; l1_sum += l1; sum_error = std::max(sum_error, std::abs(sum-1));
        return l1;
    }
    void json(std::ostream& f) const {
        f << "{\"profile\":\"" << name << "\",\"dimensions\":" << probability.size()
          << ",\"regime\":\"" << regime << "\",\"rare_pid\":" << rare_pid
          << ",\"scale\":" << scale << ",\"rho\":" << cfg.rho << ",\"sigma\":" << cfg.sigma
          << ",\"large_probability\":" << cfg.large_probability << ",\"large_multiplier\":" << cfg.large_multiplier
          << ",\"vmax_before_centering\":" << cfg.vmax << ",\"pre_normalization_floor\":" << (relative_band ? 0 : floor)
          << ",\"relative_target_band\":" << relative_band << ",\"mean_reversion\":" << mean_reversion
          << ",\"steps\":" << steps << ",\"noise_large_events\":" << large_events
          << ",\"boundary_reflections\":" << reflections << ",\"min_probability\":" << minimum
          << ",\"max_probability\":" << maximum << ",\"max_probability_sum_error\":" << sum_error
          << ",\"mean_probability_l1_step\":" << (steps ? l1_sum/steps : 0)
          << ",\"max_relative_target_deviation\":" << max_relative_target_deviation << ",\"initial_probabilities\":";
        array(f,initial_probabilities); f << ",\"target_probabilities\":"; array(f,target_probabilities); f << '}';
    }
};

int main(int argc, char** argv) {
  try {
    std::map<std::string, std::string> args;
    for (int i = 1; i < argc; i += 2) {
        if (i+1 == argc || std::string(argv[i]).substr(0,2) != "--") throw std::runtime_error("expected --key value");
        if (!args.emplace(std::string(argv[i]).substr(2),argv[i+1]).second) throw std::runtime_error("duplicate argument");
    }
    const std::vector<std::string> allowed = {"out","meta","trace","partition-trace","seed","n","k","p","memory",
        "pressure","build-fraction","profile","partition-profile","partition-speed","rare","phase","period","window","partition-window","write","read","penalty"};
    for (const auto& a : args) if (std::find(allowed.begin(),allowed.end(),a.first)==allowed.end())
        throw std::runtime_error("unknown argument: "+a.first);
    auto get = [&](const std::string& key, const std::string& fallback) {
        auto found = args.find(key); return found == args.end() ? fallback : found->second;
    };
    const int k = std::stoi(get("k","8")), pcount = std::stoi(get("p","64"));
    const int64_t n = std::stoll(get("n","5000000")), memory = std::stoll(get("memory","67108864"));
    const uint64_t seed = std::stoull(get("seed","7201"));
    const double pressure = std::stod(get("pressure","3")), fraction = std::stod(get("build-fraction","0.3"));
    const int period = std::stoi(get("period","127")), window = std::stoi(get("window","10000"));
    const int part_window = std::stoi(get("partition-window","10000"));
    const int write = std::stoi(get("write","100")), read = std::stoi(get("read","80")), penalty = std::stoi(get("penalty","100"));
    const std::string op_profile = get("profile","slow"), part_profile = get("partition-profile","slow"), phase = get("phase","staggered");
    const std::string rare = get("rare","none");
    const double part_speed = std::stod(get("partition-speed","0.0025"));
    if (k<1 || k>8 || pcount<2 || pcount>64 || n<4*k || n>5000000 || memory<67108864 || memory>INT64_C(4294967296) ||
        !std::isfinite(pressure) || pressure<=0 || !std::isfinite(fraction) || fraction<.08 || fraction>.65 ||
        period<1 || period>10000 || window<1 || part_window<1 || write<1 || write>10000 || read<1 || read>10000 ||
        penalty<1 || penalty>1000 || (phase!="shared" && phase!="staggered") || part_profile!="slow" ||
        !std::isfinite(part_speed) || part_speed<=0 || part_speed>.1 ||
        (rare!="none" && rare!="hot" && rare!="cold")) throw std::runtime_error("invalid parameters");
    parameters(op_profile, 1.);
    RNG op_choice(seed ^ UINT64_C(0xa3b195354a39b70d));
    RNG phase_rng(seed ^ UINT64_C(0x64c5e389da71f02b));
    RNG rare_rng(seed ^ UINT64_C(0x05fb927c41ea830d));
    RNG key_rng(seed ^ UINT64_C(0xc29f56e147bad013)), size_rng(seed ^ UINT64_C(0x519fb468a93c027d));
    Process op_process(k, op_profile, 1., seed ^ UINT64_C(0x7d6a9b21fe843ac1));
    std::vector<int64_t> thresholds(k);
    double expected_builds = 0;
    for (int i = 0; i < k; ++i) {
        const double factor = phase == "shared" ? 1. : .7+.6*phase_rng.real();
        thresholds[i] = int64_t(std::floor(n*std::max(.08,std::min(.65,fraction*factor))));
        thresholds[i] = std::max(int64_t(1), thresholds[i]);
        expected_builds += double(thresholds[i])/k;
    }
    const double average_size = memory*pressure/expected_builds;
    if (!std::isfinite(average_size) || average_size<2 || 1.5*average_size>1048576)
        throw std::runtime_error("expected build size incompatible with tuple bounds");
    const int rare_op = rare=="none" ? -1 : int(rare_rng.bounded(k));
    const int rare_partition = rare=="none" ? -1 : int(rare_rng.bounded(pcount));
    const double rare_target_mass = rare=="hot" ? .5+.3*rare_rng.real() : (rare=="cold" ? .001/pcount : 0.);
    std::vector<Process> part_processes;
    std::vector<RNG> part_choices;
    for (int i=0;i<k;++i) {
        const uint64_t identity = uint64_t(i+1)*UINT64_C(0x9e3779b97f4a7c15);
        part_processes.emplace_back(pcount,"slow",8.0/pcount*part_speed,seed ^ UINT64_C(0x83d2e5f11c038b69) ^ identity);
        part_choices.emplace_back(seed ^ UINT64_C(0x2961b8f40d7a35ce) ^ identity);
        RNG initial_rng(seed ^ UINT64_C(0xda834e7026bf519c) ^ identity);
        std::vector<double> initial(pcount), target(pcount,1.0/pcount);
        double sum=0;
        for (int pid=0;pid<pcount;++pid) { initial[pid]=.95+.1*initial_rng.real(); sum+=initial[pid]; }
        for (auto& x:initial) x/=sum;
        if (i==rare_op) {
            const double other_mass=1-initial[rare_partition];
            for (int pid=0;pid<pcount;++pid)
                initial[pid]=pid==rare_partition ? rare_target_mass : initial[pid]*(1-rare_target_mass)/other_mass;
            target=initial;
        }
        part_processes.back().configure_partition(initial,target,i==rare_op ? "rare_"+rare : "normal",i==rare_op ? rare_partition : -1);
    }
    const std::string out_path=get("out",""), meta_path=get("meta",""), trace_path=get("trace",""), part_path=get("partition-trace","");
    if (out_path.empty() || meta_path.empty() || trace_path.empty() || part_path.empty())
        throw std::runtime_error("out/meta/trace/partition-trace required");
    std::ofstream out(out_path,std::ios::binary), meta(meta_path,std::ios::binary), trace(trace_path,std::ios::binary), ptrace(part_path,std::ios::binary);
    if (!out || !meta || !trace || !ptrace) throw std::runtime_error("cannot open output files");
    out << k << ' ' << pcount << ' ' << memory << ' ' << write << ' ' << read << ' ' << penalty << '\n' << n << ' ' << period << '\n';
    std::vector<std::streampos> build_positions(k), probe_positions(k);
    for (int i=0;i<k;++i) {
        out << i << ' '; build_positions[i]=out.tellp(); out << std::setw(12) << 0 << ' ';
        probe_positions[i]=out.tellp(); out << std::setw(12) << 0 << '\n';
    }
    trace << "end_step,window_steps,mean_active,mean_probability_l1_step,mean_max_probability,mixed_phase_steps";
    for (int i=0;i<k;++i) trace << ",count_" << i << ",mean_p_" << i;
    trace << '\n' << std::setprecision(17);
    ptrace << "operator,local_end,global_end,window_visits,build_visits,probe_visits,mean_probability_l1_step";
    for (int p=0;p<pcount;++p) ptrace << ",count_" << p << ",mean_q_" << p;
    ptrace << '\n' << std::setprecision(17);
    std::vector<int64_t> builds(k), probes(k), switch_steps(k), last_probe_steps(k), visits(k), last_visit_steps(k);
    std::vector<std::vector<int64_t>> bytes(k,std::vector<int64_t>(pcount));
    std::vector<std::vector<std::vector<int64_t>>> counts(k,std::vector<std::vector<int64_t>>(2,std::vector<int64_t>(pcount)));
    std::vector<int64_t> op_counts(k), part_wsteps(k), part_wbuild(k), part_wprobe(k);
    std::vector<double> op_psum(k), part_wl1(k);
    std::vector<std::vector<int64_t>> part_wcounts(k,std::vector<int64_t>(pcount));
    std::vector<std::vector<double>> part_qsum(k,std::vector<double>(pcount));
    int64_t total_bytes=0, win_steps=0, win_mixed=0, total_mixed=0, longest_run=0, run=0;
    double win_l1=0, win_max=0;
    int previous_op=-1;
    auto flush_partition_window = [&](int op) {
        if (!part_wsteps[op]) return;
        ptrace << op << ',' << visits[op] << ',' << last_visit_steps[op] << ',' << part_wsteps[op]
               << ',' << part_wbuild[op] << ',' << part_wprobe[op] << ',' << part_wl1[op]/part_wsteps[op];
        for (int pid=0;pid<pcount;++pid) {
            ptrace << ',' << part_wcounts[op][pid] << ',' << part_qsum[op][pid]/part_wsteps[op];
            part_wcounts[op][pid]=0; part_qsum[op][pid]=0;
        }
        ptrace << '\n'; part_wsteps[op]=part_wbuild[op]=part_wprobe[op]=0; part_wl1[op]=0;
    };
    for (int64_t t=1;t<=n;++t) {
        const int op=op_process.sample(op_choice);
        ++op_counts[op];
        for (int i=0;i<k;++i) op_psum[i]+=op_process.probability[i];
        win_max+=*std::max_element(op_process.probability.begin(),op_process.probability.end());
        if (op==previous_op) ++run; else { run=1; previous_op=op; }
        longest_run=std::max(longest_run,run);
        int switched=0;
        for (int i=0;i<k;++i) switched+=switch_steps[i]!=0;
        const int mixed=switched>0 && switched<k;
        win_mixed+=mixed; total_mixed+=mixed;
        if (!switch_steps[op] && t>=thresholds[op]) {
            switch_steps[op]=t; out << "SWITCH " << op << '\n';
        } else {
            const int pid=part_processes[op].sample(part_choices[op]);
            for (int p=0;p<pcount;++p) part_qsum[op][p]+=part_processes[op].probability[p];
            ++visits[op]; ++part_wsteps[op]; ++part_wcounts[op][pid]; last_visit_steps[op]=t;
            const int64_t key=pid+int64_t(pcount)*key_rng.bounded((1000000000-pid)/pcount+1);
            if (!switch_steps[op]) {
                const int64_t size=int64_t(std::floor(average_size*(.5+size_rng.real())+.5));
                bytes[op][pid]+=size;
                if (size<1 || size>1048576 || bytes[op][pid]>memory)
                    throw std::runtime_error("partition capacity exceeded; original case rejected, no repartitioning/replacement seed");
                ++builds[op]; ++counts[op][0][pid]; ++part_wbuild[op]; total_bytes+=size;
                out << "INSERT " << op << ' ' << key << ' ' << size << '\n';
            } else {
                ++probes[op]; ++counts[op][1][pid]; ++part_wprobe[op]; last_probe_steps[op]=t;
                out << "PROBE " << op << ' ' << key << '\n';
            }
            part_wl1[op]+=part_processes[op].update();
            if (part_wsteps[op]==part_window) flush_partition_window(op);
        }
        win_l1+=op_process.update(); ++win_steps;
        if (win_steps==window || t==n) {
            trace << t << ',' << win_steps << ',' << k << ',' << win_l1/win_steps << ',' << win_max/win_steps << ',' << win_mixed;
            for (int i=0;i<k;++i) {
                trace << ',' << op_counts[i] << ',' << op_psum[i]/win_steps;
                op_counts[i]=0; op_psum[i]=0;
            }
            trace << '\n'; win_steps=win_mixed=0; win_l1=win_max=0;
        }
    }
    for (int i=0;i<k;++i) {
        if (!switch_steps[i]) throw std::runtime_error("EOF before all operators switched; preserve failed seed without forced completion");
        if (part_processes[i].steps!=builds[i]+probes[i]) throw std::runtime_error("local clock mismatch");
        flush_partition_window(i);
    }
    const std::streampos end_position=out.tellp();
    for (int i=0;i<k;++i) {
        out.seekp(build_positions[i]); out << std::setw(12) << builds[i];
        out.seekp(probe_positions[i]); out << std::setw(12) << probes[i];
    }
    out.seekp(end_position);
    int64_t max_partition=0;
    for (const auto& row:bytes) for (auto b:row) max_partition=std::max(max_partition,b);
    meta << std::setprecision(17) << "{\n\"schema_version\":3,\"generator\":\"r72-hierarchical-probability-velocity-v3\","
         << "\"seed\":" << seed << ",\"operations\":" << n << ",\"K\":" << k << ",\"P\":" << pcount
         << ",\"memory\":" << memory << ",\"period\":" << period << ",\"window\":" << window << ",\"partition_window\":" << part_window
         << ",\"write\":" << write << ",\"read\":" << read << ",\"penalty\":" << penalty
         << ",\"profile\":\"" << op_profile << "\",\"partition_profile\":\"" << part_profile << "\",\"phase\":\"" << phase << '"'
         << ",\"partition_speed\":" << part_speed
         << ",\"requested_pressure\":" << pressure << ",\"build_fraction\":" << fraction
         << ",\"expected_build_count_for_size\":" << expected_builds << ",\"expected_tuple_size\":" << average_size
         << ",\"realized_pressure\":" << double(total_bytes)/memory << ",\"total_build_bytes\":" << total_bytes
         << ",\"max_partition_bytes\":" << max_partition << ",\"min_active\":" << k << ",\"max_active\":" << k
         << ",\"single_active_steps\":" << (k==1?n:0) << ",\"mixed_phase_steps\":" << total_mixed
         << ",\"longest_same_operator_run\":" << longest_run << ",\n\"actual_build_counts\":"; array(meta,builds);
    meta << ",\"actual_probe_counts\":"; array(meta,probes);
    meta << ",\"switch_thresholds\":"; array(meta,thresholds);
    meta << ",\"switch_steps\":"; array(meta,switch_steps);
    meta << ",\"last_probe_steps\":"; array(meta,last_probe_steps);
    meta << ",\"partition_local_visits\":"; array(meta,visits);
    meta << ",\"partition_last_visit_steps\":"; array(meta,last_visit_steps);
    meta << ",\"rare\":{\"kind\":\"" << rare << "\",\"operator\":" << rare_op << ",\"partition\":" << rare_partition
         << ",\"target_mass\":" << rare_target_mass << ",\"global_start\":" << (rare_op<0?0:1)
         << ",\"global_end\":" << (rare_op<0?0:n) << ",\"local_start\":" << (rare_op<0?0:1)
         << ",\"local_end\":" << (rare_op<0?0:visits[rare_op]) << '}';
    meta << ",\"planned_expected_partition_capacity_fraction\":[";
    for (int i=0;i<k;++i) {
        if (i) meta << ',';
        const double largest_target=*std::max_element(part_processes[i].target_probabilities.begin(),part_processes[i].target_probabilities.end());
        const double mass_upper=1.05*largest_target/(.95+.1*largest_target);
        meta << average_size*thresholds[i]/k*mass_upper/memory;
    }
    meta << ']';
    meta << ",\n\"operator_process\":"; op_process.json(meta);
    meta << ",\n\"partition_processes\":[";
    for (int i=0;i<k;++i) { if (i) meta << ','; part_processes[i].json(meta); }
    meta << "],\n\"partition_bytes\":[";
    for (int i=0;i<k;++i) { if (i) meta << ','; array(meta,bytes[i]); }
    meta << "],\n\"partition_counts\":[";
    for (int i=0;i<k;++i) { if (i) meta << ','; meta << '['; array(meta,counts[i][0]); meta << ','; array(meta,counts[i][1]); meta << ']'; }
    meta << "],\n\"clock_semantics\":\"Operator p/v updates after every global operation including SWITCH. Each operator partition q/u updates only after its own INSERT or PROBE, never at SWITCH or another operator access. All K operators remain eligible through EOF. Build and Probe header counts are actual realized totals, backfilled after EOF.\"\n}\n";
    out.close(); meta.close(); trace.close(); ptrace.close();
    if (!out || !meta || !trace || !ptrace) throw std::runtime_error("write/close failure");
    std::cout << "OK operations=" << n << " build_bytes=" << total_bytes << " max_partition=" << max_partition << '\n';
    return 0;
  } catch (const std::exception& e) { std::cerr << "ERROR: " << e.what() << '\n'; return 1; }
}
