"""Check published bytes, model structure, and portable source syntax; no solver."""
import ast
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def main():
    manifest = json.loads((HERE/'ARCHIVE_MANIFEST.json').read_text(encoding='utf8'))
    errors = []
    py_count = 0
    models = 0
    for row in manifest['files']:
        path = HERE/row['path']
        if not path.is_file():
            errors.append('missing '+row['path'])
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256'] or len(raw) != row['bytes']:
            errors.append('hash/size '+row['path'])
        if path.suffix == '.py':
            ast.parse(raw, filename=row['path']); py_count += 1
        if path.name == 'model.json':
            model = json.loads(raw)
            if 'layers' in model:
                layers = model['layers']
                dims = [32] + model['hidden'] + [1]
                for a,b,l in zip(dims,dims[1:],layers):
                    assert len(l['weight']) == b and len(l['bias']) == b
                    assert all(len(v) == a for v in l['weight'])
                assert len(layers) == len(dims)-1
                models += 1
    if errors:
        raise RuntimeError('\n'.join(errors))
    print(json.dumps({'status':'PASS','files':len(manifest['files']),'python_syntax_checked':py_count,'layer_models_checked':models,
                      'solver_runs':0,'training_runs':0,'native_runs':0}))

if __name__ == '__main__':
    main()
