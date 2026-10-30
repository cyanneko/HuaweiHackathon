"""Cross-platform dependency-key positive and real-integrity negative tests."""
import copy,json
from pathlib import Path
import inventory as inv
def tests():
    a=dict(cases=[dict(case_id='same',input_sha256='1'*64,parameters=dict(k=8))],dependencies={'tmp\\d70\\manifest.json':'a'*64})
    b=copy.deepcopy(a);b['dependencies']={'tmp/d70/manifest.json':'a'*64}
    assert inv.normalized_inventory(a)==inv.normalized_inventory(b)
    changed=copy.deepcopy(b);changed['dependencies']['tmp/d70/manifest.json']='b'*64
    assert inv.normalized_inventory(a)!=inv.normalized_inventory(changed),'changed real SHA accepted'
    scratch=inv.HERE/'test_scratch';scratch.mkdir(exist_ok=True)
    tiny=scratch/'metadata.json';tiny.write_bytes(b'{"value":1}')
    before=dict(dependencies={'tmp/metadata.json':inv.sha(tiny)})
    tiny.write_bytes(b'{"value":2}')
    after=dict(dependencies={'tmp/metadata.json':inv.sha(tiny)})
    assert inv.normalized_inventory(before)!=inv.normalized_inventory(after),'actual changed-file SHA accepted'
    changed=copy.deepcopy(b);changed['cases'][0]['input_sha256']='2'*64
    assert inv.normalized_inventory(a)!=inv.normalized_inventory(changed),'changed input SHA accepted'
    changed=copy.deepcopy(b);changed['cases'][0]['parameters']['k']=4
    assert inv.normalized_inventory(a)!=inv.normalized_inventory(changed),'changed case parameter accepted'
    collision=copy.deepcopy(a);collision['dependencies'].update(b['dependencies'])
    try:inv.normalized_inventory(collision)
    except AssertionError:pass
    else:raise AssertionError('canonical-key collision silently collapsed')
    for bad in ['/absolute','../outside','tmp/../outside','<LOCAL_PATH>']:
        try:inv.normalized_inventory(dict(dependencies={bad:'a'*64}))
        except AssertionError:pass
        else:raise AssertionError('non-relative dependency accepted')
    return dict(status='PASS',checks=['Windows/POSIX key positive','real dependency SHA difference negative','actual tiny-file byte mutation recomputed SHA negative','input SHA difference negative','case parameter difference negative','duplicate canonical key rejected even if SHA same','non-relative keys rejected'])
if __name__=='__main__':print(json.dumps(tests(),indent=2))
