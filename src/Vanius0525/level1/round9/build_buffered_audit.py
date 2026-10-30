"""Same official engine/scheduler calls, bounded buffered TRACE for large audits.

Only the diagnostic wrapper changes. Timed runs use the original unaudited
builder. The wrapper preserves the established TRACE bytes and call order.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build as original

BUFFERED_AUDIT = r'''
#include <cstdio>
#include <cstdlib>
#include <string>
class AuditScheduler : public SpillScheduler {
    MySpillScheduler inner_;
    std::string buffer_;
    void flush() {
        if (buffer_.empty()) return;
        if (std::fwrite(buffer_.data(),1,buffer_.size(),stderr)!=buffer_.size()) std::abort();
        buffer_.clear();
    }
    void log(char tag,int op,int pid,int64_t bytes,const std::vector<Action>& a) {
        buffer_ += "TRACE ";buffer_ += tag;
        buffer_ += " " + std::to_string(op) + " " + std::to_string(pid);
        buffer_ += " " + std::to_string(bytes) + " " + std::to_string(a.size());
        for (const auto& x:a) {
            buffer_ += (x.type==Action::SPILL ? " S " : " L ");
            buffer_ += std::to_string(x.op_id) + " " + std::to_string(x.partition_id);
        }
        buffer_ += '\n';
        if (buffer_.size()>=65536) flush();
    }
public:
    AuditScheduler(){buffer_.reserve(65536);}
    ~AuditScheduler() override {flush();}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t z) override {
        auto a=inner_.onMemoryOverflow(s,o,p,z);log('O',o,p,z,a);return a;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {
        auto a=inner_.onPartitionMiss(s,o,p);log('M',o,p,0,a);return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        auto a=inner_.onPeriodicAdjust(s);log('P',-1,-1,0,a);return a;
    }
};
'''


def build_buffered(source, name):
    saved = original.AUDIT
    try:
        original.AUDIT = BUFFERED_AUDIT
        return original.build(source, name, audit=True)
    finally:
        original.AUDIT = saved
