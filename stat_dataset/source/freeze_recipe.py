"""Freeze new seeds and the complete specification before production generation."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def cases():
    result=[]
    def independent_index(field,serial):
        order=sorted(range(40),key=lambda i:hashlib.sha256(f'stat-v1-{field}-{i}'.encode()).digest())
        return order.index(serial)
    pure=['uniform','zipf','hotspot','lognormal']
    plans={'train':[(f,t) for f in pure for t in ['static','slow','fast','burst']]+[('mixed','mixed')]*8,
           'dev':list(zip(pure,['slow','fast','burst','static']))+[('mixed','mixed')]*2,
           'eval':[(f,t) for f,ts in zip(pure,[['static','fast'],['slow','burst'],['fast','slow'],['burst','static']]) for t in ts]+[('mixed','mixed')]*2}
    serial=0
    for split,items in plans.items():
        for i,(family,temporal) in enumerate(items):
            short=i in ({0,5,10,15} if split=='train' else {0,3} if split=='dev' else {0,4})
            k,p=[(1,64),(2,32),(4,32),(4,64),(8,32),(8,64)][independent_index('shape',serial)%6]
            phase='shared' if independent_index('phase',serial)%2==0 or k==1 else 'staggered'
            result.append({'case_id':f'{split}_{i:02d}_{family}_{temporal}_{phase}', 'split':split,
                'parameters':{'seed':20261030810001+serial*1009,'n':1000000 if short else 5000000,
                    'k':k,'p':p,'memory':(64,128,256,512,1024,2048,4096)[independent_index('memory',serial)%7]*1048576,
                    'pressure':(1.25,1.75,2.5,3.5,5.,6.)[independent_index('pressure',serial)%6],
                    'family':family,'temporal':temporal,'phase':phase,
                    'build_fraction':(.25,.3,.35,.4,.45)[independent_index('build_fraction',serial)%5],
                    'size_sigma':(.6,1.,1.4)[independent_index('size_sigma',serial)%3],
                    'write':(100,50,300,200)[independent_index('bandwidth',serial)%4],'read':(80,160,100,400)[independent_index('bandwidth',serial)%4],
                    'penalty':(10,30,100,300)[independent_index('penalty',serial)%4],'period':(31,127,509,2048)[independent_index('period',serial)%4],
                    'tick':64,'trace_every':max(1024,(1000000 if short else 5000000)//32)}})
            serial+=1
    return result
def main():
    rows=cases();target=ROOT/'recipe.json'
    obj={'name':'stat_dataset','version':'1.0.0','schema_version':1,'cases':rows,
         'total_operations':sum(r['parameters']['n'] for r in rows),
         'frozen_before_production':True,'seed_substitution':False,'score_filtering':False,
         'meaning':'stat is the requested name, not a claim that the probability process is stationary',
         'independence':'Independent per-flat-partition latent states and RNG streams; only categorical normalization couples probabilities. No operator heat/process/prior/selection multiplier.',
         'clock':'Every latent process ticks on the common global operation clock, every 64 operations, including BUILD and SWITCH; sampling holds weights fixed within a tick.',
         'mixed':'Independent partition-level mixture of base distributions and static/slow/fast/burst profiles within the same input; legal shared/staggered phase schedules.',
         'scope':'Ordinary workloads with dyna-inspired drift/shock intensity; no engineered capacity/empty-probe/cycle/adversarial corner suite.',
         'split_policy':'New unique seeds for train/dev/eval; no old eval used in train; eval is frozen regression material after exposure, not guaranteed unseen forever.'}
    data=(json.dumps(obj,indent=2)+'\n').encode()
    if target.exists():assert target.read_bytes()==data,'refuse changing frozen recipe'
    else:target.write_bytes(data)
    print(json.dumps({'cases':len(rows),'operations':obj['total_operations'],'recipe_sha256':hashlib.sha256(data).hexdigest()}))
if __name__=='__main__':main()
