"""Export a fully measured and independently audited 785-case checkpoint."""
from pathlib import Path
import argparse,hashlib,json,shutil

ROOT=Path(__file__).resolve().parent
D=ROOT.parent
M=D/'member_eval_20261030'
COMMIT='e119c2326e198922243306eac062785420ed8156'
SUITE='a176758680d7c6a99805cfb1eeeff9786314d8309db7c0e80e269843880e8ce1'
def read(p):return json.loads(p.read_text('utf8'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',required=True);ap.add_argument('--mode',required=True,type=int);ap.add_argument('--search-note',default='');a=ap.parse_args()
    raw=read(ROOT/(a.tag+'_summary.json'));member=read(M/(a.tag+'_members.json'));key=str(a.mode)
    assert raw['scope']=='members' and raw['suite_id']==SUITE and raw['repeats']==3
    assert member['case_count']==785 and member['suite_id']==SUITE and member['repeats']==3
    registry={v['id']:v for v in read(ROOT/'variants.json')};v=registry[a.mode]
    assert raw['variants'][key]==v['name']==member['candidates'][key]['name']
    source=ROOT/v['source'];sha=digest(source);assert sha==v['sha256']
    if key in raw.get('candidate_sources',{}):assert raw['candidate_sources'][key]['sha256']==sha
    audited=[]
    for path in sorted(ROOT.glob('*_audit_summary.json')):
        for record in read(path).values():
            if record['name']==v['name'] and record['source_sha256']==sha and record['cases']==785:
                assert record['strict_actions'] and record['feature_prediction_parity'];audited.append(path.name)
    assert audited,'No independent full-suite action and feature-parity audit for this source'
    original_model=read(ROOT/(v['name']+'.json'))
    from normalize_candidate_metadata import normalize
    model=normalize(original_model)
    normalization=None
    if model!=original_model:
        normalized_path=ROOT/'publication_metadata_private.json'
        dump(normalized_path,model)
        from build_candidates import export
        generated=export(normalized_path)
        assert (ROOT/generated['source']).read_bytes()==source.read_bytes(),'Metadata cleanup changed deployed C++'
        normalization=dict(original_candidate=v['name']+'.json',original_sha256=digest(ROOT/(v['name']+'.json')),
                           canonical_model_sha256=digest(normalized_path),cpp_byte_identity_verified=True)
    shutil.copyfile(source,D/'MySpillScheduler_tree.cpp')
    dump(ROOT/'current_model.json',model)
    train=[]
    for path in sorted(ROOT.glob('train_g*_840_summary.json')):
        report=read(path)
        if report['status']!='complete':continue
        ranking=sorted(report['summary'].items(),key=lambda pair:pair[1]['mean_score'])
        controls={'train_g0_840':{30,32},'train_g1_840':{30,53},'train_g2_840':{30,53,60},'train_g5_840':{0,1,2,30,92},'train_g6_840':{0,1,2,30,108}}.get(report['tag'],{0,1,2,30,60})
        new=[(k,v) for k,v in ranking if int(k) not in controls]
        train.append(dict(tag=report['tag'],scope='train',cases=report['case_count'],repeats=report['repeats'],train_suite_id=report['train_suite_id'],control_modes=sorted(controls),best_new_mode=int(new[0][0]),best_new=new[0][1],all_modes_best=int(ranking[0][0]),candidate_count=len(new),eval_used_for_fitness=False))
    source_bundles={'members_r3':'benchmark_sources','members_r4':'scratch_sources','members_r5':'refine_sources','members_r6':'gate_sources','members_r8':'admission_sources','members_r9':'full_horizon_sources','members_standalone_r1':'standalone_sources','members_standalone_r2':'standalone_admission_sources','members_standalone_r3':'standalone_category_sources'}
    measurement_bundles={'members_r3':'benchmark_measurements','members_r4':'scratch_measurements','members_r5':'refine_measurements','members_r6':'gate_measurements','members_r8':'admission_measurements','members_r9':'full_horizon_measurements','members_standalone_r1':'standalone_measurements','members_standalone_r2':'standalone_admission_measurements','members_standalone_r3':'standalone_category_measurements'}
    source_bundle=source_bundles[a.tag]+'.zip';measurement_bundle=measurement_bundles[a.tag]+'.zip'
    assert (ROOT/source_bundle).is_file() and (ROOT/measurement_bundle).is_file()
    result=dict(status='completed measurement checkpoint; iteration continues',date='2026-10-30',objective='minimise complete raw average SDK Score including callback time',
        name=v['name'],mode=a.mode,model='current_model.json',source='design/MySpillScheduler_tree.cpp',source_sha256=sha,
        dataset_commit=COMMIT,suite_id=SUITE,cases=785,repeats=3,aggregation=raw['aggregation'],
        member_report=a.tag+'_members.json',sdk_report=a.tag+'_summary.json',sdk_runs=a.tag+'_runs.jsonl',
        binary_sha256=raw['binary_sha256'],reference_sha256=digest(D/'holistic_20261026/reference_current.cpp'),
        source_bundle=source_bundle,measurement_bundle=measurement_bundle,deployment=raw.get('deployment','combined research program; mode chosen before timed callbacks'),
        audits=audited,summary=raw['summary'][key],members=member['candidates'][key]['members'],
        public_score_summary=member['candidates'][key]['public_score_summary'],
        train_search=train,search_note=a.search_note,
        caution='Observed development/regression inputs, not hidden tests. Training-only full-trace fitness is separate from final regression. No universal optimality or all-member improvement claim.')
    if normalization is not None:result['model_metadata_normalization']=normalization
    dump(ROOT/'published_checkpoint.json',result)
    text=['第20题：8专家小树与三成员评测（2026-10-30）','',
        '当前本地完整785例平均Score目标的最佳交付：../MySpillScheduler_tree.cpp。',
        '节点阈值与叶子专家内嵌C++14；不依赖外部模型或推理库。',
        '推荐入口：python design/tools/run.py --policy tree --input <正式输入文件>',
        '原规则用--policy rule；原网络用--policy neural；官方Naive用--policy baseline。','',
        '测量记录：published_checkpoint.json；中文说明：../topic20_portfolio_iteration_report.pdf。',
        '三人分别结果：../member_eval_20261030/'+result['member_report'],
        '完整SDK逐次数据：'+result['sdk_runs']+'；每例3次，算术均值。',
        '当前名称：'+result['name'],'源码SHA256：'+sha,
        f'全785例平均Score：{result["summary"]["mean_score"]:.6f} us；比Naive下降{result["summary"]["decrease_vs_naive_percent"]:.6f}%。','',
        '三成员：Vanius0525 0.1.0/209；cyanneko 0.6.0/48；liunianwww 0.1.0/528。',
        '数据固定提交：'+COMMIT,'suite_id：'+SUITE,
        '成员未封顶sum等权主分、原cap50和raw平均Score分别保留，不混写；坏例不删。',
        '840份train用于新标签与直接fitness；eval未作为新标签或fitness输入。',
        'eval已被反复观察，用于开发比较，并非独立未见盲测。','',
        '方法与来源：iteration_notes.txt、../neural_selector/catalog.json、research_sources.json。',
        '8专家编号0..7；评测mode不是分类标签。只有选中的专家实际执行。',
        'overflow、miss每次分类；periodic仅下一INSERT将溢出时分类；普通hit无回调。',
        'cheap路由按路径懒计算；getSystemState及专家仍可能O(Q)，以完整计时为准。',
        'forced-cover只保证固定需求/保护条件的必要集合覆盖时立即写出量最小。','',
        '复现环境：Python 3.10+、g++支持C++14，拟合另需NumPy；CPU串行测量。',
        '正式输入不在源码分支，请先获取datasets分支的两个独立固定worktree：',
        'git worktree add --detach design/dataset_integration_20261029/worktree 0be508208700edae7a7b4443b122c633cc87b0e0',
        'git worktree add --detach design/member_eval_20261030/worktree '+COMMIT,
        '旧worktree用于公共评测模块及旧568例；新worktree用于840 train与785 eval。',
        '先用git fetch origin datasets获取提交；不要把datasets分支合到source分支。','',
        '重拟合父模型（写新前缀，避免覆盖冻结模型）：',
        'python design/portfolio_iter_20261029/train_tree_v2.py --input design/portfolio_iter_20261029/round3_labels.portable.jsonl.gz --features cheap --objectives relative --depths 4 --output-prefix replay',
        '训练压缩包把file改为datasets/<member>/train/<name>；features/costs/权重字段保持一致。',
        'portable_labels_audit.json记录原文件/压缩包哈希、行数和数值语义一致性。',
        'collect_on_policy.py可重采样，CPU标签重测会波动；不要同时运行solver计时与拟合。','',
        '本地实验工具：build_candidates.py导出/编译；evaluate.py串行eval；audit_candidates.py独立动作与特征核对；',
        'search_candidates.py生成train特征邻域变异；train_fitness.py串行完整train评分。',
        'variants.json固定本地mode映射；训练输入编号/成员名/真实p均非在线特征。',
        '当前程序源码快照：'+source_bundle+'；只绑定'+a.tag+'，不同历史程序不混用身份。',
        '当前原字节测量包：'+measurement_bundle+'。旧r3/4/5/6各自的source/measurements包独立保存。',
        '重算本轮成员分前可解包：python -m zipfile -e design/portfolio_iter_20261029/'+measurement_bundle+' design/portfolio_iter_20261029',
        '使用源快照重新编译得到的新CPU时间是复测值，不冒充历史原值。','',
        '旧568例过程：progress.json；其best_model.json保留旧套件最佳，不覆盖为新套件。',
        '本轮最终选择模型：current_model.json。所有设计、PDF与证据均在design下。',a.search_note]
    text.insert(-1,'冻结模型JSON保留生成时candidate_has_measured_fitness=false和父模型640/568来源字段；后续840训练fitness及785实测以published_checkpoint和对应结果为准，不改写冻结原件。')
    (ROOT/'README.txt').write_text('\n'.join(text)+'\n',encoding='utf8')
    print(json.dumps(dict(name=result['name'],mean_score=result['summary']['mean_score'],source_sha256=sha,audits=audited)),flush=True)

if __name__=='__main__':main()
