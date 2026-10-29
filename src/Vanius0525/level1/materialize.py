"""Materialize standalone variants from the common masked-observation template."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def render(name,expression,model=''):
    template=(ROOT/'scheduler_template.cpp.in').read_text()
    text=template.replace('@MODEL@',model).replace('@REUSE@',expression)
    text='\n'.join(line.rstrip() for line in text.splitlines())+'\n'
    assert '@' not in text
    p=ROOT/(name+'.cpp');p.write_text(text);return p

if __name__=='__main__':
    render('observed_recency', '''if (!f[4]) return 0;
        return 1.0 / (1.0 + std::pow(2.0, f[1]*16.0) - 1.0);''')
    render('observed_frequency', '''if (!f[4]) return 0;
        return f[3] / (1.0 + std::pow(2.0,f[1]*16.0) / 64.0);''')
    render('scan_guard', '''if (f[10] >= .75f && f[6] && f[9] > .5f)
            return 1.0 - f[11];
        if (!f[4]) return 0;
        return f[3] / (1.0 + std::pow(2.0,f[1]*16.0) / 64.0);''')
    render('largest_guard', 'return 0;')
