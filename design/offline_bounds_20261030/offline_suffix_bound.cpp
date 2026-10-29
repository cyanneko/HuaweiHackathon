// OFFLINE EVALUATION ONLY. This program reads the full input, true p and B.
// It must never be linked into a submitted/online scheduler or its features.
// Mathematical exactness refers to the stated boundary/suffix relaxation in
// real arithmetic. long double plus a downward allowance is NOT a certified
// floating-point lower-bound implementation. Review and toy checks are pending.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace offline_suffix_bound {

using I64 = std::int64_t;
using U64 = std::uint64_t;
using Real = long double;
constexpr int kMaxQ = 16;
constexpr U64 kWorkLimit = 200000000ULL;
constexpr Real kAbsoluteAllowance = 0.02L;
constexpr Real kRelativeAllowance = 1e-12L;
const Real kInfinity = std::numeric_limits<Real>::infinity();

void require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}

std::string escaped(const std::string& value) {
    static const char hex[] = "0123456789abcdef";
    std::string result;
    for (unsigned char c : value) {
        if (c == '\\' || c == '"') {
            result.push_back('\\'); result.push_back(static_cast<char>(c));
        } else if (c < 32) {
            result += "\\u00";
            result.push_back(hex[c >> 4]); result.push_back(hex[c & 15]);
        } else result.push_back(static_cast<char>(c));
    }
    return result;
}

struct Input {
    int k = 0, p = 0, n = 0, period = 0, penalty = 0;
    I64 memory = 0, total_bytes = 0;
    Real write = 0, read = 0;
    U64 prefix_data_operations = 0, all_data_operations = 0;
    int last_switch_position = 0; // One-based input operation index.
    std::array<I64, 512> final_sizes{};
    std::vector<std::uint16_t> suffix_targets; // Global op*P+pid, including empty targets.
};

Input read_input(const char* filename) {
    std::ifstream stream(filename);
    require(bool(stream), "cannot open input");
    Input in;
    I64 n = 0, period = 0;
    require(bool(stream >> in.k >> in.p >> in.memory >> in.write >> in.read >> in.penalty),
            "invalid first header");
    require(bool(stream >> n >> period), "invalid N/B header");
    require(in.k >= 1 && in.k <= 8 && in.p >= 2 && in.p <= 64, "K/P outside formal limits");
    require(in.memory >= 64LL * 1024 * 1024 && in.memory <= 4LL * 1024 * 1024 * 1024,
            "memory outside formal limits");
    require(std::isfinite(in.write) && std::isfinite(in.read) && in.write >= 1 &&
            in.write <= 10000 && in.read >= 1 && in.read <= 10000, "invalid bandwidth");
    require(in.penalty >= 1 && in.penalty <= 1000, "penalty outside formal limits");
    require(n >= 1 && n <= 5000000 && period >= 1 && period <= 10000, "N/B outside formal limits");
    in.n = static_cast<int>(n); in.period = static_cast<int>(period);
    std::array<I64, 8> wanted_build{}, wanted_probe{}, actual_build{}, actual_probe{};
    std::array<bool, 8> probe_phase{};
    I64 declared_operations = in.k;
    for (int o = 0; o < in.k; ++o) {
        int id = -1; I64 build = 0, probe = 0;
        require(bool(stream >> id >> build >> probe), "invalid operator metadata");
        require(id == o, "operator headers must be ascending 0..K-1");
        require(build >= 0 && probe >= 0 && build <= n && probe <= n, "invalid declared counts");
        wanted_build[o] = build; wanted_probe[o] = probe;
        declared_operations += build + probe;
    }
    require(declared_operations == n, "declared counts plus K SWITCHes differ from N");
    for (int i = 1; i <= in.n; ++i) {
        std::string kind; int o = -1;
        require(bool(stream >> kind >> o), "truncated operation");
        require(o >= 0 && o < in.k, "invalid operation operator");
        if (kind == "SWITCH") {
            require(!probe_phase[o], "duplicate SWITCH");
            probe_phase[o] = true;
            in.last_switch_position = i;
            in.prefix_data_operations = in.all_data_operations;
            // Every later SWITCH discards the temporary earlier suffix.
            in.suffix_targets.clear();
            continue;
        }
        require(kind == "INSERT" || kind == "PROBE", "unknown opcode");
        I64 key = -1;
        require(bool(stream >> key) && key >= 0 && key <= 1000000000LL, "invalid key");
        const int global = o * in.p + static_cast<int>(key % in.p);
        if (kind == "INSERT") {
            I64 bytes = 0;
            require(bool(stream >> bytes) && bytes >= 1 && bytes <= 1048576, "invalid tuple size");
            require(!probe_phase[o], "INSERT after SWITCH");
            require(in.final_sizes[global] <= in.memory - bytes, "partition exceeds memory");
            in.final_sizes[global] += bytes;
            in.total_bytes += bytes;
            ++actual_build[o];
        } else {
            require(probe_phase[o], "PROBE before SWITCH");
            ++actual_probe[o];
            in.suffix_targets.push_back(static_cast<std::uint16_t>(global));
        }
        ++in.all_data_operations;
    }
    for (int o = 0; o < in.k; ++o) {
        require(probe_phase[o], "every operator needs exactly one SWITCH");
        require(wanted_build[o] == actual_build[o] && wanted_probe[o] == actual_probe[o],
                "observed counts differ from metadata");
    }
    std::string extra;
    require(!(stream >> extra), "extra nonempty tokens after N operations");
    require(in.last_switch_position >= 1, "missing boundary SWITCH");
    require(in.suffix_targets.size() == static_cast<U64>(in.n - in.last_switch_position),
            "suffix after all SWITCHes is not exclusively PROBE");
    require(in.prefix_data_operations + in.suffix_targets.size() + static_cast<U64>(in.k) ==
            static_cast<U64>(in.n), "periodic counter accounting mismatch");
    return in;
}

struct Bound {
    int q = 0;
    bool computed = false;
    std::string reason;
    U64 state_count = 0, feasible_count = 0;
    U64 work_estimate = 0, suffix_work_estimate = 0, transforms = 0;
    unsigned best_boundary = 0;
    Real raw_value = 0, allowance = 0, lower_value = 0;
    std::vector<int> globals;
};

// min_T[g(T) + transfer(S,T)] for every S. Infeasible destination T must
// ALREADY have g(T)=infinity. Never prune capacity inside these bit passes:
// their intermediate entries are partial eliminations, not resident states.
void directed_hamming_min_plus(std::vector<Real>& g, const std::vector<I64>& bytes,
                              Real write, Real read) {
    const unsigned states = static_cast<unsigned>(g.size());
    for (unsigned bit = 0; bit < bytes.size(); ++bit) {
        const unsigned step = 1u << bit;
        const Real loading = static_cast<Real>(bytes[bit]) / read;
        const Real spilling = static_cast<Real>(bytes[bit]) / write;
        for (unsigned block = 0; block < states; block += 2 * step) {
            for (unsigned j = 0; j < step; ++j) {
                const unsigned zero = block + j, one = zero + step;
                const Real old_zero = g[zero], old_one = g[one];
                // Simultaneous updates, with directions determined by SOURCE S.
                g[zero] = std::min(old_zero, old_one + loading);
                g[one] = std::min(old_one, old_zero + spilling);
            }
        }
    }
}

Bound compute(const Input& in) {
    Bound out;
    std::array<int, 512> bit_of_global; bit_of_global.fill(-1);
    std::vector<I64> bytes;
    for (int id = 0; id < in.k * in.p; ++id) {
        if (in.final_sizes[id] > 0) {
            bit_of_global[id] = out.q++;
            out.globals.push_back(id); bytes.push_back(in.final_sizes[id]);
        }
    }
    if (out.q > kMaxQ) {
        out.reason = "q_exceeds_limit";
        return out;
    }
    const unsigned states = 1u << out.q;
    out.state_count = states;
    const U64 suffix_n = static_cast<U64>(in.suffix_targets.size());
    // Conservative requested budget uses original input N. No-suffix cases
    // need only state enumeration, so irrelevant prefix length costs no DP work.
    out.work_estimate = suffix_n ? 2ULL * static_cast<U64>(in.n) * out.q * states : 0;
    out.suffix_work_estimate = 2ULL * suffix_n * out.q * states;
    std::vector<I64> sum(states, 0);
    for (int bit = 0; bit < out.q; ++bit) {
        const unsigned block = 1u << bit;
        for (unsigned j = 0; j < block; ++j) sum[block + j] = sum[j] + bytes[bit];
    }
    std::vector<unsigned char> feasible(states, 0);
    for (unsigned mask = 0; mask < states; ++mask) {
        feasible[mask] = static_cast<unsigned char>(sum[mask] <= in.memory);
        out.feasible_count += feasible[mask];
    }
    if (out.work_estimate > kWorkLimit) {
        out.reason = "estimated_work_exceeds_limit";
        return out;
    }
    std::vector<Real> next(states, kInfinity), after, miss(states), current(states);
    for (unsigned mask = 0; mask < states; ++mask) if (feasible[mask]) next[mask] = 0;
    // Q=0 means every suffix access is a free hit. The one state remains zero,
    // including every periodic event; no numerical DP loop is necessary.
    if (out.q != 0) {
        for (std::size_t pos = in.suffix_targets.size(); pos-- > 0;) {
            after = next;
            const U64 after_counter = in.prefix_data_operations + static_cast<U64>(pos) + 1;
            if (after_counter % static_cast<U64>(in.period) == 0) {
                directed_hamming_min_plus(after, bytes, in.write, in.read);
                ++out.transforms;
            }
            const int target = bit_of_global[in.suffix_targets[pos]];
            if (target >= 0) {
                const unsigned target_bit = 1u << target;
                // Destination T immediately after miss actions must fit and
                // contain the current target. Its LOAD can be performed last.
                for (unsigned mask = 0; mask < states; ++mask)
                    miss[mask] = feasible[mask] && (mask & target_bit) ? after[mask] : kInfinity;
                directed_hamming_min_plus(miss, bytes, in.write, in.read);
                ++out.transforms;
                for (unsigned mask = 0; mask < states; ++mask) {
                    current[mask] = !feasible[mask] ? kInfinity : (mask & target_bit) ?
                        after[mask] : static_cast<Real>(in.penalty) + miss[mask];
                }
            } else {
                // Do NOT remove empty-partition probes: pos still advances the
                // periodic counter and the periodic transform above still runs.
                for (unsigned mask = 0; mask < states; ++mask)
                    current[mask] = feasible[mask] ? after[mask] : kInfinity;
            }
            next.swap(current);
        }
    }
    Real best = kInfinity;
    for (unsigned mask = 0; mask < states; ++mask) if (feasible[mask]) {
        const Real prefix_write = static_cast<Real>(in.total_bytes - sum[mask]) / in.write;
        const Real value = prefix_write + next[mask];
        if (value < best) { best = value; out.best_boundary = mask; }
    }
    require(std::isfinite(best) && best >= 0, "unexpected nonfinite/negative DP value");
    out.raw_value = best;
    const Real scale = std::max(1.0L, std::fabs(best));
    // Downward numerical allowance, NOT a proof of floating error bounds.
    // Includes a conservative operation-depth heuristic; no interval arithmetic
    // or directed rounding is used, and this must not be called certified.
    const Real depth_allowance = 128.0L * std::numeric_limits<Real>::epsilon() *
        (static_cast<Real>(suffix_n) + 1) * (static_cast<Real>(out.q) + 1) * scale;
    out.allowance = kAbsoluteAllowance + kRelativeAllowance * scale + depth_allowance;
    out.lower_value = std::max(0.0L, best - out.allowance);
    out.computed = true;
    return out;
}

void print_result(const Input& in, const Bound& b) {
    const U64 suffix_n = static_cast<U64>(in.suffix_targets.size());
    const U64 prefix_periodic = in.prefix_data_operations / static_cast<U64>(in.period);
    const U64 all_periodic = in.all_data_operations / static_cast<U64>(in.period);
    std::cout << std::setprecision(std::numeric_limits<Real>::max_digits10)
        << "{\"status\":\"" << (b.computed ? "ok" : "skipped") << "\",\"computed\":"
        << (b.computed ? "true" : "false") << ",\"kind\":\"offline_boundary_suffix_relaxation\""
        << ",\"q\":" << b.q << ",\"q_limit\":" << kMaxQ
        << ",\"input_operations\":" << in.n << ",\"suffixlen\":" << suffix_n
        << ",\"boundary_after_operation\":" << in.last_switch_position
        << ",\"periodicprefix\":" << in.prefix_data_operations
        << ",\"periodic_prefix_mod_B\":" << in.prefix_data_operations % static_cast<U64>(in.period)
        << ",\"prefix_periodic_callbacks\":" << prefix_periodic
        << ",\"suffix_periodic_callbacks\":" << all_periodic - prefix_periodic
        << ",\"period_B\":" << in.period << ",\"miss_penalty\":" << in.penalty
        << ",\"total_nonempty_bytes\":" << in.total_bytes
        << ",\"work_limit\":" << kWorkLimit << ",\"machine_certified\":false"
        << ",\"long_double_digits\":" << std::numeric_limits<Real>::digits;
    if (b.q <= kMaxQ) {
        std::cout << ",\"state_count\":" << b.state_count << ",\"feasible_states\":" << b.feasible_count
            << ",\"estimated_work\":" << b.work_estimate
            << ",\"estimated_suffix_work\":" << b.suffix_work_estimate;
    } else std::cout << ",\"state_count\":null,\"feasible_states\":null,\"estimated_work\":null,\"estimated_suffix_work\":null";
    if (b.computed) {
        std::cout << ",\"lower_bound\":" << b.lower_value << ",\"raw_relaxation_value\":" << b.raw_value
            << ",\"downward_allowance\":" << b.allowance
            << ",\"absolute_comparison_tolerance\":" << kAbsoluteAllowance
            << ",\"relative_comparison_tolerance\":" << kRelativeAllowance
            << ",\"exact_in_real_arithmetic\":true,\"transform_calls\":" << b.transforms
            << ",\"relaxed_best_boundary_mask\":" << b.best_boundary
            << ",\"exactness_scope\":\"stated relaxed prefix bound and exact suffix DP, not full-case optimum\"";
    } else std::cout << ",\"lower_bound\":null,\"raw_relaxation_value\":null,\"exact_in_real_arithmetic\":null,\"skip_reason\":\"" << escaped(b.reason) << '"';
    std::cout << ",\"floating_point_caution\":\"long double with heuristic downward allowance; not machine-certified\""
        << ",\"interpretation\":\"lower bound only; any gap to a measured Score is an upper bound on possible improvement, not achievable savings\""
        << ",\"nonempty_partitions\":[";
    for (std::size_t i = 0; i < b.globals.size(); ++i) {
        const int id = b.globals[i]; if (i) std::cout << ',';
        std::cout << "{\"bit\":" << i << ",\"operator\":" << id / in.p
            << ",\"partition\":" << id % in.p << ",\"bytes\":" << in.final_sizes[id] << '}';
    }
    std::cout << "]}\n";
}

} // namespace offline_suffix_bound

int main(int argc, char** argv) {
    using namespace offline_suffix_bound;
    if (argc != 2) {
        std::cout << "{\"status\":\"error\",\"message\":\"usage: offline_suffix_bound <official_input.txt>\"}\n";
        return 2;
    }
    try {
        const Input in = read_input(argv[1]);
        const Bound bound = compute(in);
        print_result(in, bound);
        return 0; // skipped is explicit, never encoded as lower_bound=0.
    } catch (const std::exception& error) {
        std::cout << "{\"status\":\"error\",\"computed\":false,\"lower_bound\":null,\"message\":\""
            << escaped(error.what()) << "\"}\n";
        return 2;
    }
}
