// OFFLINE ANALYSIS ONLY: never link this tool or its future input into a solver.
// Integer byte bounds are exact. Floating-point divisions are not certified.
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
#include <utility>
#include <vector>

namespace window_bound {
using I64 = std::int64_t;
using U64 = std::uint64_t;
using Real = long double;
const I64 NEG = std::numeric_limits<I64>::min() / 4;

void require(bool yes, const char* reason) {
    if (!yes) throw std::runtime_error(reason);
}

struct Input {
    int k = 0, p = 0, n = 0, period = 0, penalty = 0, boundary = 0;
    I64 memory = 0, total_bytes = 0, prefix_data = 0;
    Real write = 0, read = 0;
    U64 fingerprint = 1469598103934665603ULL;
    std::array<I64, 512> sizes{};
};

void mix(U64& h, U64 value) {
    for (int b = 0; b < 8; ++b) {
        h ^= (value >> (8 * b)) & 255;
        h *= 1099511628211ULL;
    }
}

// No operation list is retained. Visitor sees (one-based position, opcode,
// global partition); opcode 0=SWITCH, 1=INSERT, 2=PROBE.
template <class Visitor>
Input scan(const char* filename, Visitor visitor) {
    std::ifstream stream(filename);
    require(bool(stream), "cannot_open_input");
    // Accept the same optional UTF-8 BOM as the public input auditor.
    if (stream.peek() == 0xef) {
        require(stream.get() == 0xef && stream.get() == 0xbb && stream.get() == 0xbf,
                "invalid_utf8_bom");
    }
    Input a;
    I64 n = 0, period = 0;
    require(bool(stream >> a.k >> a.p >> a.memory >> a.write >> a.read >> a.penalty), "invalid_header");
    require(bool(stream >> n >> period), "invalid_N_B");
    require(1 <= a.k && a.k <= 8 && 2 <= a.p && a.p <= 64, "invalid_K_P");
    require(64LL * 1024 * 1024 <= a.memory && a.memory <= 4LL * 1024 * 1024 * 1024,
            "invalid_capacity");
    require(std::isfinite(a.write) && std::isfinite(a.read) && 1 <= a.write && a.write <= 10000 &&
            1 <= a.read && a.read <= 10000 && 1 <= a.penalty && a.penalty <= 1000, "invalid_costs");
    require(1 <= n && n <= 5000000 && 1 <= period && period <= 10000, "invalid_N_B_limits");
    a.n = static_cast<int>(n); a.period = static_cast<int>(period);
    std::array<I64, 8> builds{}, probes{}, actual_builds{}, actual_probes{};
    std::array<bool, 8> switched{};
    I64 declared = a.k, data_ops = 0;
    for (int o = 0; o < a.k; ++o) {
        int id = -1;
        require(bool(stream >> id >> builds[o] >> probes[o]), "invalid_declarations");
        require(id == o && builds[o] >= 0 && probes[o] >= 0 && builds[o] <= n && probes[o] <= n,
                "invalid_declaration_values_or_order");
        declared += builds[o] + probes[o];
    }
    require(declared == n, "declared_count_mismatch");
    for (int i = 1; i <= a.n; ++i) {
        std::string op; int o = -1;
        require(bool(stream >> op >> o) && 0 <= o && o < a.k, "invalid_operation");
        int kind = 0, g = -1;
        I64 key = 0, bytes = 0;
        if (op == "SWITCH") {
            require(!switched[o], "duplicate_SWITCH");
            switched[o] = true; a.boundary = i; a.prefix_data = data_ops;
        } else {
            require(op == "INSERT" || op == "PROBE", "unknown_opcode");
            require(bool(stream >> key) && 0 <= key && key <= 1000000000LL, "invalid_key");
            g = o * a.p + static_cast<int>(key % a.p);
            if (op == "INSERT") {
                kind = 1;
                require(bool(stream >> bytes) && 1 <= bytes && bytes <= 1048576 && !switched[o],
                        "invalid_INSERT");
                require(a.sizes[g] <= a.memory - bytes, "partition_exceeds_capacity");
                a.sizes[g] += bytes; a.total_bytes += bytes; ++actual_builds[o];
            } else {
                kind = 2;
                require(switched[o], "PROBE_before_SWITCH"); ++actual_probes[o];
            }
            ++data_ops;
        }
        mix(a.fingerprint, kind); mix(a.fingerprint, o);
        mix(a.fingerprint, static_cast<U64>(key)); mix(a.fingerprint, static_cast<U64>(bytes));
        visitor(i, kind, g);
    }
    for (int o = 0; o < a.k; ++o) {
        require(switched[o] && builds[o] == actual_builds[o] && probes[o] == actual_probes[o],
                "phase_or_actual_count_mismatch");
    }
    std::string extra;
    require(!(stream >> extra), "extra_tokens");
    require(a.boundary > 0 && a.prefix_data + a.n - a.boundary + a.k == a.n,
            "suffix_counter_mismatch");
    return a;
}

bool same_input(const Input& a, const Input& b) {
    return a.k == b.k && a.p == b.p && a.n == b.n && a.period == b.period &&
        a.penalty == b.penalty && a.boundary == b.boundary && a.memory == b.memory &&
        a.write == b.write && a.read == b.read && a.total_bytes == b.total_bytes &&
        a.prefix_data == b.prefix_data && a.fingerprint == b.fingerprint && a.sizes == b.sizes;
}

class RangeMax {
    int n;
    std::vector<I64> maximum, lazy;
    void apply(int node, I64 value) { maximum[node] += value; lazy[node] += value; }
    void push(int node) {
        if (lazy[node]) { apply(2 * node, lazy[node]); apply(2 * node + 1, lazy[node]); lazy[node] = 0; }
    }
    void set(int node, int lo, int hi, int pos, I64 value) {
        if (lo == hi) { maximum[node] = value; lazy[node] = 0; return; }
        push(node); const int mid = (lo + hi) / 2;
        if (pos <= mid) set(node * 2, lo, mid, pos, value);
        else set(node * 2 + 1, mid + 1, hi, pos, value);
        maximum[node] = std::max(maximum[node * 2], maximum[node * 2 + 1]);
    }
    void add(int node, int lo, int hi, int left, int right, I64 value) {
        if (left <= lo && hi <= right) { apply(node, value); return; }
        push(node); const int mid = (lo + hi) / 2;
        if (left <= mid) add(node * 2, lo, mid, left, right, value);
        if (mid < right) add(node * 2 + 1, mid + 1, hi, left, right, value);
        maximum[node] = std::max(maximum[node * 2], maximum[node * 2 + 1]);
    }
public:
    explicit RangeMax(int count) : n(count), maximum(4ULL * count + 8, NEG), lazy(4ULL * count + 8, 0) {}
    void set(int pos, I64 value) { set(1, 0, n - 1, pos, value); }
    void add(int left, int right, I64 value) { if (value) add(1, 0, n - 1, left, right, value); }
    I64 top() const { return maximum[1]; }
};

struct Entry { I64 value = NEG; int owner = -1; };
struct TopTwo { Entry first, second; };

TopTwo merge(const TopTwo& a, const TopTwo& b) {
    std::array<Entry, 4> x{{a.first, a.second, b.first, b.second}};
    std::sort(x.begin(), x.end(), [](const Entry& u, const Entry& v) {
        return u.value != v.value ? u.value > v.value : u.owner < v.owner;
    });
    TopTwo r;
    for (const Entry& e : x) {
        if (e.owner < 0 || e.value == NEG) continue;
        if (r.first.owner < 0) r.first = e;
        else if (e.owner != r.first.owner) { r.second = e; break; }
    }
    return r;
}

class PathTree {
    int base = 1;
    std::vector<TopTwo> tree;
public:
    explicit PathTree(int n) { while (base < n) base *= 2; tree.resize(2 * base); }
    void set(int pos, int owner, I64 value) {
        pos += base; tree[pos] = TopTwo{};
        tree[pos].first.value = value; tree[pos].first.owner = owner;
        while ((pos /= 2)) tree[pos] = merge(tree[2 * pos], tree[2 * pos + 1]);
    }
    TopTwo query(int lo, int hi) const { // [lo,hi)
        TopTwo answer;
        for (lo += base, hi += base; lo < hi; lo /= 2, hi /= 2) {
            if (lo & 1) answer = merge(answer, tree[lo++]);
            if (hi & 1) answer = merge(answer, tree[--hi]);
        }
        return answer;
    }
};

struct Result {
    int q = 0, suffixlen = 0;
    bool computed = false;
    std::string reason;
    U64 memory_estimate = 0;
    I64 forced = 0, excess = 0, window = 0, path = 0, reads = 0, writes = 0;
    Real raw = 0, allowance = 0, lower = 0;
};

Result compute(const char* filename, const Input& in, U64 budget) {
    Result out; out.suffixlen = in.n - in.boundary;
    std::vector<std::pair<I64, int>> ordered;
    for (int g = 0; g < in.k * in.p; ++g)
        if (in.sizes[g]) ordered.emplace_back(in.sizes[g], g);
    std::sort(ordered.begin(), ordered.end()); out.q = static_cast<int>(ordered.size());
    // Two int64 arrays of (4*n+8), plus generously rounded fixed/path overhead.
    out.memory_estimate = 64ULL * out.suffixlen + 256ULL * out.q + 65536ULL;
    if (out.memory_estimate > budget) { out.reason = "estimated_memory_exceeds_budget"; return out; }
    if (out.suffixlen) {
        RangeMax window(out.suffixlen); PathTree paths(out.q);
        std::array<int, 512> last{}, rank; rank.fill(-1);
        std::array<I64, 512> value; value.fill(NEG);
        for (int j = 0; j < out.q; ++j) rank[ordered[j].second] = j;
        int i = 0, previous = -1;
        Input second = scan(filename, [&](int pos, int kind, int target) {
            if (pos <= in.boundary) return;
            require(kind == 2, "non_PROBE_in_static_suffix");
            ++i; const I64 size = in.sizes[target];
            // Insert cut i-1 BEFORE changing F or distinct(j+1..i).
            window.set(i - 1, out.excess + out.forced);
            if (previous >= 0 && previous != target && in.sizes[previous] + size > in.memory)
                out.forced += size;
            window.add(last[target], i - 1, size);
            out.excess = std::max(out.excess, window.top() - in.memory - out.forced);
            last[target] = i; previous = target; // Empty probes still split adjacency/windows.
            if (size) {
                const auto start = std::upper_bound(ordered.begin(), ordered.end(),
                    std::make_pair(in.memory - size, std::numeric_limits<int>::max()));
                const TopTwo top = paths.query(static_cast<int>(start - ordered.begin()), out.q);
                const Entry best = top.first.owner != target ? top.first : top.second;
                I64 next = std::max<I64>(0, value[target]); // First SEEN occurrence is an anchor.
                if (best.owner >= 0) next = std::max(next, best.value + size);
                value[target] = next; paths.set(rank[target], target, next);
                out.path = std::max(out.path, next);
            }
        });
        require(i == out.suffixlen && same_input(in, second), "input_changed_between_streaming_passes");
    } else {
        const Input second = scan(filename, [](int, int, int) {});
        require(same_input(in, second), "input_changed_between_streaming_passes");
    }
    out.window = out.forced + out.excess;
    out.reads = std::max(out.window, out.path);
    out.writes = std::max<I64>(0, in.total_bytes + out.reads - in.memory);
    out.raw = static_cast<Real>(out.writes) / in.write + static_cast<Real>(out.reads) / in.read;
    out.allowance = 0.02L + 1e-12L * std::max<Real>(1, out.raw) +
        64 * std::numeric_limits<Real>::epsilon() * std::max<Real>(1, out.raw);
    out.lower = std::max<Real>(0, out.raw - out.allowance);
    out.computed = true; return out;
}

void output(const Input& in, const Result& r, U64 budget) {
    std::cout << std::setprecision(std::numeric_limits<Real>::max_digits10);
    std::cout << "{\"status\":\"" << (r.computed ? "ok" : "skipped") << "\",\"computed\":"
        << (r.computed ? "true" : "false") << ",\"q\":" << r.q << ",\"suffixlen\":" << r.suffixlen
        << ",\"boundary_after_operation\":" << in.boundary << ",\"periodicprefix\":" << in.prefix_data
        << ",\"total_insert_bytes\":" << in.total_bytes << ",\"capacity_bytes\":" << in.memory
        << ",\"estimated_memory_bytes\":" << r.memory_estimate << ",\"memory_budget_bytes\":" << budget
        << ",\"machine_certified\":false,\"exact_integer_byte_bounds\":" << (r.computed ? "true" : "null");
    if (!r.computed) {
        std::cout << ",\"skip_reason\":\"" << r.reason << "\",\"read_bytes_lower_bound\":null,"
            "\"write_bytes_lower_bound\":null,\"raw_io_lower_bound\":null,\"lower_bound\":null}" << '\n';
        return;
    }
    std::cout << ",\"adjacent_forced_read_bytes\":" << r.forced << ",\"window_excess_bytes\":" << r.excess
        << ",\"window_read_lower_bound\":" << r.window << ",\"path_read_lower_bound\":" << r.path
        << ",\"read_bytes_lower_bound\":" << r.reads << ",\"write_bytes_lower_bound\":" << r.writes
        << ",\"raw_io_lower_bound\":" << r.raw << ",\"downward_allowance\":" << r.allowance
        << ",\"lower_bound\":" << r.lower << ",\"write_bandwidth\":" << in.write
        << ",\"read_bandwidth\":" << in.read << ",\"ignored_miss_penalty_and_decision_time\":true,"
        "\"interpretation\":\"A lower bound, not an achievable oracle cost. Floating point is not machine-certified.\"}"
        << '\n';
}
} // namespace window_bound

int main(int argc, char** argv) {
    using namespace window_bound;
    try {
        require(argc == 2 || argc == 3, "usage_window_bound_input_optional_memory_mib");
        U64 memory_mib = 512;
        if (argc == 3) {
            const std::string arg = argv[2]; std::size_t used = 0;
            require(!arg.empty() && arg[0] != '-', "invalid_memory_budget");
            memory_mib = std::stoull(arg, &used);
            require(used == arg.size() && memory_mib >= 1 && memory_mib <= 1048576, "invalid_memory_budget");
        }
        const U64 budget = memory_mib * 1024ULL * 1024ULL;
        const Input in = scan(argv[1], [](int, int, int) {});
        const Result result = compute(argv[1], in, budget);
        output(in, result, budget); return 0;
    } catch (const std::bad_alloc&) {
        std::cout << "{\"status\":\"skipped\",\"computed\":false,\"skip_reason\":\"allocation_failed\","
            "\"read_bytes_lower_bound\":null,\"write_bytes_lower_bound\":null,\"raw_io_lower_bound\":null,"
            "\"lower_bound\":null,\"machine_certified\":false}\n";
        return 0;
    } catch (const std::exception&) {
        std::cout << "{\"status\":\"error\",\"computed\":false,\"reason\":\"invalid_input_or_arguments\","
            "\"lower_bound\":null,\"machine_certified\":false}\n";
        return 1;
    }
}
