"""Narrow the stated root audit coverage; no statistical or input recomputation."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    old=HERE/'REPORT_V1.md';new=HERE/'REPORT_V2.md'
    original='根独立审核核回全部算术与身份，未重复读取输入。'
    corrected='root复核选择/绑定、分区/算子计数、HHI、成本及摘要秩相关，未重复解析输入，范围见 `../ZIPF_DIAGNOSTIC_REVIEW_V1.json`；root未独立重算每个全局/算子大小—热度相关。'
    text=old.read_text();assert text.count(original)==1
    with new.open('x') as f:f.write(text.replace(original,corrected))
    with (HERE/'REPORT_CORRECTION_V2.json').open('x') as f:
        json.dump({'reason':'Root requested a precise statement of independent audit coverage; original V1 preserved.',
                   'report_v1_sha256':sha(old),'report_v2_sha256':sha(new),
                   'changed_fields':'One audit-scope sentence only','new_input_reads':0,'new_solver_runs':0},f,indent=2);f.write('\n')


if __name__=='__main__':main()
