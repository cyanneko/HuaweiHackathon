"""Build only in this agent's ignored cache; preserve frozen engine exactly."""
from pathlib import Path
import hashlib,re,subprocess,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from build import FROZEN,FROZEN_SHA,REPO,AUDIT

def reference():
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    return next(b for b in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in b).replace('\xa0',' ')
def declarations():
    ref=reference();return ref[ref.index('enum class Phase'):ref.index('/* ===== 朴素调度器')]
def compile_text(name,source):
    out=HERE/'build';out.mkdir(exist_ok=True);path=out/(name+'.cpp');exe=out/name
    if path.exists():assert path.read_text()==source
    else:path.write_text(source)
    if not exe.exists():subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra',str(path),'-o',str(exe)],check=True,capture_output=True,text=True)
    return exe

def official(name,source=None,audit=False):
    ref=reference();before=ref.split('class HashJoinEngine',1)[1].split('/* ===== 主函数',1)[0]
    chosen='NaiveSpillScheduler'
    if source:
        policy=Path(source).read_text();assert 'int main(' not in policy
        ref=ref.replace('class HashJoinEngine',policy+(AUDIT if audit else '')+'\nclass HashJoinEngine',1)
        chosen='AuditScheduler' if audit else 'MySpillScheduler'
    assert ref.split('class HashJoinEngine',1)[1].split('/* ===== 主函数',1)[0]==before
    ref=ref.replace('std::make_unique<NaiveSpillScheduler>()','std::make_unique<'+chosen+'>()')
    return compile_text(name,ref)
