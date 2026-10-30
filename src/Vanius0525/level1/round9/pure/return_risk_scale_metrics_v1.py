"""Descriptive attribution only; no future labels choose calibration strength."""
import math


class ScaleAttribution:
    def __init__(self):
        self.g={'forecast':{'count':0,'min':None,'max':None,'sum':0.},'pair':{'count':0,'min':None,'max':None,'sum':0.}}
        self.cross=[0]*8
        self.all_sets={'history':{'count':0,'victims':0,'excess_bytes':0},'dynamic':{'count':0,'victims':0,'excess_bytes':0}}
        self.changed={name:dict(count=0,less_write=0,more_write=0,same_write=0,fewer_victims=0,more_victims=0,same_victims=0,lower_excess=0,higher_excess=0,same_excess=0,old_victims=0,new_victims=0,old_excess_bytes=0,new_excess_bytes=0,current_write_delta_us=0.) for name in ['pooling','no_pooling','global_scale']}
        self.selected={name:dict(count=0,victims=0,excess_bytes=0,current_write_us=0.) for name in ['next','pooling','no_pooling','global_scale']}
        self.mass={'forecast_count':0,'unknown_positions':0,'disk_trials':0,'disk_mass_sum':[0.,0.,0.,0.]}

    def factor(self,where,g):
        assert math.isfinite(g) and g>0
        row=self.g[where];row['count']+=1;row['sum']+=g;row['min']=g if row['min'] is None else min(row['min'],g);row['max']=g if row['max'] is None else max(row['max'],g)

    def forecast(self,g,unknown,disk,hs):
        self.factor('forecast',g);self.mass['forecast_count']+=1;self.mass['unknown_positions']+=unknown;self.mass['disk_trials']+=unknown*len(disk)
        for j in range(4):self.mass['disk_mass_sum'][j]+=unknown*float(hs[j,disk].sum())

    def pair(self,g,choose,freed,cardinality,need,write_bw):
        self.factor('pair',g);assert len(choose)==4 and all(x in [0,1] for x in choose)
        excess=[value-need for value in freed];assert min(excess)>=0
        for j,name in enumerate(['history','dynamic']):
            row=self.all_sets[name];row['count']+=1;row['victims']+=cardinality[j];row['excess_bytes']+=excess[j]
        mask=sum((1<<j) for j in range(3) if choose[j+1]!=choose[0]);self.cross[mask]+=1
        for j,name in enumerate(['next','pooling','no_pooling','global_scale']):
            row=self.selected[name];sel=choose[j];row['count']+=1;row['victims']+=cardinality[sel];row['excess_bytes']+=excess[sel];row['current_write_us']+=freed[sel]/write_bw
        for j,name in enumerate(['pooling','no_pooling','global_scale'],1):
            old,new=choose[0],choose[j]
            if old==new:continue
            row=self.changed[name];row['count']+=1;dw=(freed[new]-freed[old])/write_bw;dc=cardinality[new]-cardinality[old];de=excess[new]-excess[old]
            row['less_write']+=dw<0;row['more_write']+=dw>0;row['same_write']+=dw==0
            row['fewer_victims']+=dc<0;row['more_victims']+=dc>0;row['same_victims']+=dc==0
            row['lower_excess']+=de<0;row['higher_excess']+=de>0;row['same_excess']+=de==0
            row['old_victims']+=cardinality[old];row['new_victims']+=cardinality[new]
            row['old_excess_bytes']+=excess[old];row['new_excess_bytes']+=excess[new];row['current_write_delta_us']+=dw

    def export(self,loss,fields):
        out={'g':self.g,'changed_cross_table':self.cross,'cross_bits':['pooling','no_pooling','global_scale'],'all_candidate_sets':self.all_sets,'selected_sets':self.selected,'changed_actions':self.changed,'mass':self.mass,
             'global_scale_loss_by_operator':[{key:float(row[i]) if i<2 else int(row[i]) for i,key in enumerate(fields)} for row in loss[3]],
             'note':'All action totals are hypothetical choices at repeated reference states, not a realizable trajectory or cost improvement.'}
        for row in out['g'].values():row['mean']=row['sum']/row['count'] if row['count'] else None
        for key,bit in [('pooling',1),('no_pooling',2)]:
            own=sum(v for m,v in enumerate(self.cross) if m&bit);scale=sum(v for m,v in enumerate(self.cross) if m&4);both=sum(v for m,v in enumerate(self.cross) if m&bit and m&4)
            out[key+'_vs_scale']={'own_changed':own,'scale_changed':scale,'both_changed':both,'own_only':own-both,'scale_only':scale-both,'same_final_choice':sum(self.cross)-(own+scale-2*both),'different_final_choice':own+scale-2*both,'fraction_own_flips_reproduced':both/own if own else None}
        return out
