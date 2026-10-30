"""Same-state scale attribution; no fitted parameters, rewards, or solver."""
class CoscaleAttribution:
    def __init__(self):
        self.all_pairs=0;self.clipped=0;self.groups={name:self.empty() for name in ('g_lt_1','g_eq_1','g_gt_1')}

    @staticmethod
    def empty():
        return dict(count=0,changed=0,old_alt=0,new_alt=0,g_min=None,g_max=None,g_sum=0.,
                    neff_min=None,neff_max=None,neff_sum=0.,margin_old_sum_us=0.,margin_new_sum_us=0.,
                    margin_change_abs_max_us=0.,changed_less_write=0,changed_more_write=0,changed_same_write=0,
                    changed_fewer_victims=0,changed_more_victims=0,changed_same_victims=0,
                    changed_current_write_delta_us=0.,changed_excess_delta_bytes=0,changed_victim_delta=0)

    def pair(self,g,unclipped,neff,immediate,future,risk,old_choice,freed,cards,need,write):
        self.all_pairs+=1
        assert g>0 and risk>=0 and neff>=0 and len(freed)==len(cards)==2
        assert all(x>=need for x in freed)
        if not unclipped:
            self.clipped+=1
            return
        old_margin=immediate+future+risk;new_margin=immediate+future+g*risk
        assert old_choice==int(old_margin<0)
        new_choice=int(new_margin<0)
        name='g_lt_1' if g<1 else 'g_gt_1' if g>1 else 'g_eq_1'
        if g<1:assert new_choice>=old_choice
        elif g>1:assert new_choice<=old_choice
        else:assert new_choice==old_choice
        a=self.groups[name];a['count']+=1;a['old_alt']+=old_choice;a['new_alt']+=new_choice
        for label,value in (('g',g),('neff',neff)):
            a[label+'_min']=value if a[label+'_min'] is None else min(a[label+'_min'],value)
            a[label+'_max']=value if a[label+'_max'] is None else max(a[label+'_max'],value)
            a[label+'_sum']+=value
        a['margin_old_sum_us']+=old_margin;a['margin_new_sum_us']+=new_margin
        a['margin_change_abs_max_us']=max(a['margin_change_abs_max_us'],abs(new_margin-old_margin))
        if old_choice!=new_choice:
            a['changed']+=1;dw=(freed[new_choice]-freed[old_choice])/write
            dc=cards[new_choice]-cards[old_choice]
            a['changed_less_write']+=dw<0;a['changed_more_write']+=dw>0;a['changed_same_write']+=dw==0
            a['changed_fewer_victims']+=dc<0;a['changed_more_victims']+=dc>0;a['changed_same_victims']+=dc==0
            a['changed_current_write_delta_us']+=dw
            a['changed_excess_delta_bytes']+=freed[new_choice]-freed[old_choice]
            a['changed_victim_delta']+=dc

    def export(self):
        assert self.all_pairs==self.clipped+sum(a['count'] for a in self.groups.values())
        return {'all_pairs':self.all_pairs,'clipped_pairs':self.clipped,
                'unclipped_pairs':self.all_pairs-self.clipped,'groups':self.groups,
                'changed_pairs':sum(a['changed'] for a in self.groups.values()),
                'teacher_labels_used':0,'performance_effectiveness_evaluated':False,
                'scope':'Only the fixed U versus gU contrast at existing reference states; margins/current writes are not rollout costs.'}
