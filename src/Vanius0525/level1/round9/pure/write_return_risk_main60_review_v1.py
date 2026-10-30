"""Render the complete negative result without changing any gate or candidate."""
import hashlib
import json
from pathlib import Path
import statistics as st

HERE = Path(__file__).resolve().parent
NAMES = {'risk_pool100': 'pooling', 'risk_flat100': 'no-pooling', 'risk_scale100': 'global-scale'}
COMP = ('build_write_us', 'probe_write_us', 'probe_read_us', 'miss_us')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    sp, rp = HERE/'RETURN_RISK_MAIN60_SUMMARY_V1.json', HERE/'RETURN_RISK_MAIN60_RESULTS_V1.json'
    ip = HERE.parent/'RETURN_RISK_MAIN60_INDEPENDENT_REVIEW_V1.json'
    x, raw, check = (json.loads(p.read_text()) for p in (sp, rp, ip))
    assert raw['complete'] and raw['new_audited_runs'] == 180 and raw['new_timed_runs'] == 900
    assert check['passed'] and check['canonical_records_checked'] == 60 and check['timed_runs_checked'] == 900
    assert check['results_sha256'] == sha(rp) and check['summary_sha256'] == sha(sp)
    assert all(not v['eligible_for_root_independent_validation_review'] for v in x['methods'].values())
    mean_base = st.mean(r['methods']['paired100']['mean_score'] for r in x['cases'])
    base_cpu = st.mean(st.mean(r['methods']['paired100']['decision_us']) for r in x['cases'])
    max_wall = max(z['wall_seconds'] for r in raw['records'] for values in r['runs'].values() for z in values)
    lines = ['# 三份固定return-risk候选：主训练60流完整负结果', '',
             '**三候选均未通过预先冻结的晋升门槛，停止本组三候选的晋升路径，不进入主108 dev/72 eval，不调整门槛或重选训练流。** no-pooling有小幅平均改善，但未达到0.5%物理改善门槛且最坏退化超过2%；pooling和global-scale平均也退化。', '',
             '原三源码、两proposal、风险项、BUILD与预取均保持冻结。数据为原100-only主60 train（24 Zipf、24 hotspot、12 lognormal），原顺序/seed未变。绑定原180份完整参考审核；本次比较复用其中Naive/paired100的120份审核值，AI参考仅留历史背景，没有新AI实验。新增180份风险候选全动作/字节审核，以及Naive、paired100、三风险版同窗口各3次共900次未插桩计时；复用已有dyna二进制，新增编译0。', '',
             '原exec session15934已正常exit0，持久launch/日志/status/exit记录位于忽略build目录。根独立review再次核对60身份、旧参考、900次计数/成本、同窗口评分与全部门槛，passed；该通过只表示审核一致，不表示算法晋升。', '',
             f"根review SHA：`{sha(ip)}`。执行freeze：`{raw['execution_freeze_sha256']}`。完整逐例与三次原始计时见RESULTS/SUMMARY，不把训练集当盲测。", '',
             '| 候选 | 平均物理/paired | 最坏物理/paired | 改善/相同/退化 | 含决策均分 | 对paired均分差 | 平均决策ms | 平均/尾部/分数门槛 |',
             '|---|---:|---:|---|---:|---:|---:|---|']
    for key, v in x['methods'].items():
        verdict = '/'.join('通过' if v['gate_checks'][k] else '未过' for k in ('mean_physical_ratio', 'worst_physical_ratio', 'mean_decision_inclusive_score'))
        counts = '/'.join(map(str, v['better_equal_worse']))
        lines.append(f"| {NAMES[key]} | {v['mean_physical_ratio']:.9f} | {v['worst_physical_ratio']:.9f} | {counts} | {v['mean_score']:.9f} | {v['mean_score_delta']:+.9f} | {v['mean_decision_us']/1000:.3f} | {verdict} |")
    lines += ['', f"同窗口paired100均分{mean_base:.9f}、平均决策{base_cpu/1000:.3f}ms。门槛固定为60例等权物理比≤0.995、最坏≤1.02、含决策均分不低于paired100，且合法性/计数/runtime全通过；前三项必须同时满足。均分逐例按官方clamp后再等权，三次计时不算独立数据样本。", '',
              '| 候选 | BUILD写差μs | PROBE写差μs | PROBE读差μs | Miss罚值差μs | Miss次数差 | 最坏用例 |',
              '|---|---:|---:|---:|---:|---:|---|']
    for key, v in x['methods'].items():
        d = v['component_delta_us']; values = ' | '.join(f'{d[k]:+.3f}' for k in COMP)
        lines.append(f"| {NAMES[key]} | {values} | {v['miss_delta']:+d} | {check['methods'][key]['worst_case']} |")
    lines += ['', '这些分项为60流总差，不能替代逐例等权比例。各输入真实罚值不同，计费使用输入真实值，调度器未知罚值代理始终100；因此跨流Miss次数减少不必使加权Miss罚值减少。全部BUILD字节与paired100相同，退化发生在PROBE部分；这仍不能仅凭全流费用区分某次估值误差、当前写选择和后续轨迹耦合。', '',
              '| family（流数） | pooling物理均比 | no-pooling物理均比 | global物理均比 |',
              '|---|---:|---:|---:|']
    for family, count in (('random_zipf',24),('random_hotspot',24),('random_lognormal',12)):
        values = ' | '.join(f"{check['methods'][key]['family_mean_physical_ratio'][family]:.9f}" for key in NAMES)
        lines.append(f'| {family}（{count}） | {values} |')
    rows = {r['case']: r for r in x['cases']}; audits = {r['case']: r for r in raw['records']}
    c545 = rows['train/train_545_random_zipf.txt']
    hidden = ', '.join(f"{NAMES[k]}={c545['methods'][k]['physical_over_paired']:.9f}" for k in NAMES)
    c600 = audits['train/train_600_random_zipf.txt']; physical = lambda a: sum(a['costs'][k] for k in COMP)
    lines += ['', '**反事实保留。**', '',
              f"- train545：paired和三候选均被clamp到0分，但物理比分别{hidden}，0分相同不能证明成本相同。",
              f"- train600：Naive为{physical(c600['audit']['naive']):.3f}μs/34 Miss；paired与三风险版均为{physical(c600['audit']['paired100']):.3f}μs/690 Miss，物理/Naive=3.410281071。这里只核对分项/计数，没有TRACE等价核验；本组热度修正未解决这个已有长尾周转失败。",
              '- dyna12上pooling与no-pooling均12/12改善，但该主60面板三者均未过门槛。两个面板同时在流长度、压力、带宽、罚值和动态模式等方面不同，不把反转单独归因于动态/静态热度；也不将dyna的3个holdout继续用于调参。', '',
              f"所有900次未插桩运行均通过60秒限制，最大外层wall={max_wall:.6f}秒；审核时限240秒。计时同窗口、固定seed打乱五方法顺序并使用公共锁，但不是全宿主独占。小例外层wall包含进程启动与等待；本机Python的带timeout等待使用最高50ms轮询睡眠，0.115/0.165秒等台阶不能直接当作调度器CPU变化。分数采用solver内部Total_Decision_Time，未修改任何计时记录或重跑取最好值。", '',
              '**停止与下一步边界。** 主60到此完整关闭。根已完成[费用与配置互补诊断](../RETURN_RISK_MAIN60_COST_DIAGNOSIS_V1.md)：把已完成轨迹统一按100罚值重权后，退化仍存在；四配置从头执行的事后互补也不能充当合法前缀后的教师标签。该描述不替换原门槛或主成绩。纯路线可先对最坏train592/519另写小型共同状态归因方案；未授权读取大TRACE、启动新solver、改候选或加特判。本报告只否定这三份冻结实现按当前门槛晋升，未来数据版本不能追溯改写本轮原60方案和停止决定。计时实现证据另见[只读运行时记录](RETURN_RISK_MAIN60_RUNTIME_NOTE_V1.json)。', '']
    target = HERE/'RETURN_RISK_MAIN60_REVIEW_V1.md'; body = '\n'.join(lines)
    if target.exists(): assert target.read_text() == body
    else: target.write_text(body)
    print(target.name)


if __name__ == '__main__':
    main()
