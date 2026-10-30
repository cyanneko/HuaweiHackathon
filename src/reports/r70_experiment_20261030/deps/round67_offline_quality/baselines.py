"""Actual frozen policy baselines; permanent independent complete incumbent A."""
from pathlib import Path
import json,os,re,tempfile,time
from official_harness import MODES,_execute,sha,digest

def atomic_write_json(path,obj):
    """Commit one JSON file by same-directory flush/fsync/atomic replace.

    An interrupted temporary file is never a recovery candidate. This is a
    process-interruption guarantee, not a claim about whole-volume power loss.
    """
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    encoded=json.dumps(obj,indent=2,allow_nan=False)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as stream:
            stream.write(encoded);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()

def _validated(report,witness):
    if not isinstance(report,dict) or report.get('replay_verified') is not True or report.get('legal_complete_witness') is not True:raise ValueError('verified complete report required')
    cost=report.get('cost')
    if not isinstance(cost,dict):raise ValueError('cost dictionary required')
    identity=report.get('input_sha256');h=report.get('witness_hash');g=cost.get('G')
    if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{64}',identity):raise ValueError('input SHA256 required')
    if type(g) is not int or g<0:raise ValueError('nonnegative integer G required')
    if not isinstance(witness,list) or not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h) or digest(witness)!=h:raise ValueError('witness hash mismatch')
    for row in witness:
        if not isinstance(row,dict) or type(row.get('raw')) is not int or row['raw']<0 or row.get('kind') not in ('O','M','P') or not isinstance(row.get('stage'),str):raise ValueError('malformed witness row')
        spill=row.get('spill')
        if not isinstance(spill,list) or any(type(i) is not int or i<0 for i in spill) or len(set(spill))!=len(spill):raise ValueError('malformed witness spills')
    return {k:v for k,v in report.items() if k!='witness'}

def _candidate(path):
    """Read committed archive report (or pointer) and its same-folder witness."""
    try:
        report=json.loads(path.read_text(encoding='utf-8'));h=report['witness_hash']
        if path.name!='best.json' and path.name!=h+'.report.json':return None
        if not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h):return None
        witness=json.loads((path.parent/(h+'.witness.json')).read_text(encoding='utf-8'))
        clean=_validated(report,witness);clean['permanent_witness']=str(path.parent/(h+'.witness.json'))
        return clean,witness
    except (OSError,ValueError,TypeError,KeyError,AttributeError):return None

def _candidates(folder):
    folder=Path(folder)
    if not folder.is_dir():return []
    # Never recurse into raw official outputs: verification alone is not an
    # accepted commit, particularly when a deadline elapsed before acceptance.
    paths=[folder/'best.json',*sorted(folder.glob('*.report.json'))]
    return [item for path in paths if (item:=_candidate(path)) is not None]

def _publish(clean,witness,folder):
    folder=Path(folder);h=clean['witness_hash'];wp=folder/(h+'.witness.json');rp=folder/(h+'.report.json')
    existing=_candidate(rp)
    if existing is not None:
        if existing[0]['input_sha256']!=clean['input_sha256'] or existing[0]['cost']['G']!=clean['cost']['G']:raise ValueError('conflicting known-valid content-addressed archive')
    else:
        # Known independently verified payload repairs a truncated same-name
        # archive. A half pair remains unrecoverable until both commits finish.
        atomic_write_json(wp,witness)
    saved=dict(clean,permanent_witness=str(wp))
    if existing is None:atomic_write_json(rp,saved)
    atomic_write_json(folder/'best.json',saved)
    return saved

def recover_incumbent(source_dirs,destination,input_sha256=None):
    """Recover only committed archive pairs/pointers, never official leaf logs.

    With explicit identity, mismatched archives are ignored. Without one,
    mixed-input candidates are rejected rather than compared across cases.
    Destination is always included, so recovery cannot replace a better A.
    """
    destination=Path(destination);folders=list(dict.fromkeys([destination,*map(Path,source_dirs)]))
    items=[item for folder in folders for item in _candidates(folder)]
    if input_sha256 is not None:items=[item for item in items if item[0]['input_sha256']==input_sha256]
    identities={r['input_sha256'] for r,_ in items}
    if len(identities)>1:raise ValueError('refusing cross-input incumbent recovery')
    if not items:return None
    clean,witness=min(items,key=lambda item:(item[0]['cost']['G'],item[0]['witness_hash']))
    pointer=_candidate(destination/'best.json')
    if pointer is not None:
        if pointer[0]['input_sha256']!=clean['input_sha256']:raise ValueError('destination belongs to another input')
        if pointer[0]['cost']['G']<=clean['cost']['G']:return pointer[0]
    return _publish(clean,witness,destination)

def collect_baselines(input_path,out_dir,incumbent_dir=None,deadline_check=None):
    start=time.perf_counter();out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    results={}
    for mode in MODES:
        report=_execute(input_path,mode,out/mode)
        if deadline_check is not None:deadline_check()
        # Every complete feasible baseline has its own permanent witness.
        # Incumbent is initialized immediately, before the next policy runs.
        consider_incumbent(report,out/'A_incumbent')
        if incumbent_dir is not None:consider_incumbent(report,incumbent_dir)
        results[mode]=report
    best=min(results,key=lambda mode:results[mode]['cost']['G'])
    summary={'best_method':best,'best_G':results[best]['cost']['G'],'methods':{name:{k:v for k,v in r.items() if k!='witness'} for name,r in results.items()},'end_to_end_seconds':time.perf_counter()-start,'formal_D':None}
    atomic_write_json(out/'summary.json',summary);return dict(summary,results=results,best_witness=results[best]['witness'])

def consider_incumbent(report,folder):
    clean=_validated(report,report.get('witness'));folder=Path(folder)
    candidates=_candidates(folder)
    if any(r['input_sha256']!=clean['input_sha256'] for r,_ in candidates):raise ValueError('incumbent input mismatch')
    previous=recover_incumbent([folder],folder,clean['input_sha256'])
    if previous is not None and clean['cost']['G']>=previous['cost']['G']:
        # An intact best pointer may coexist with a damaged archive report.
        # Repair the known same-name payload without changing an equal/better A.
        if clean['witness_hash']==previous['witness_hash']:
            h=clean['witness_hash'];rp=folder/(h+'.report.json')
            if _candidate(rp) is None:
                atomic_write_json(folder/(h+'.witness.json'),report['witness'])
                atomic_write_json(rp,dict(clean,permanent_witness=str(folder/(h+'.witness.json'))))
        return False
    _publish(clean,report['witness'],folder);return True
