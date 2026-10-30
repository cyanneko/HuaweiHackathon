"""Stdlib C++14 dense scorer; arbitrary frozen hidden layers, no runtime."""
import json
from pathlib import Path
import struct


def f32(value):return struct.unpack('<f',struct.pack('<f',float(value)))[0]


def score_sequential(model, x):
    original=[f32(v) for v in x];h=original[:]
    for i in model['zero_columns']:h[i]=0.
    for idx,layer in enumerate(model['layers']):
        out=[]
        for weights,bias in zip(layer['weight'],layer['bias']):
            value=f32(bias)
            for weight,input_value in zip(weights,h):value=f32(value+f32(weight*input_value))
            out.append(max(0.,value) if idx+1<len(model['layers']) else value)
        h=out
    value=max(-1.,min(1.,h[0]))
    return f32(value+original[13]) if model['base_skip'] else f32(value)


def literal(v):
    value=format(float(v),'.9g')
    return value+('f' if '.' in value or 'e' in value else '.0f')


def scorer(model):
    text=['#include <cmath>','#include <limits>',
          'inline float r70_score(const float x[32]) {',
          ' for(int i=0;i<32;++i)if(!std::isfinite(x[i]))return std::numeric_limits<float>::infinity();',
          ' float h0[32];for(int i=0;i<32;++i)h0[i]=x[i];']
    for i in model['zero_columns']:text.append(' h0[%d]=0.0f;'%i)
    width=32
    for idx,layer in enumerate(model['layers']):
        n=len(layer['bias']);assert all(len(w)==width for w in layer['weight'])
        rows=','.join('{'+','.join(map(literal,w))+'}' for w in layer['weight'])
        text.append(' static const float w%d[%d][%d]={%s};'%(idx,n,width,rows))
        text.append(' static const float b%d[%d]={%s};'%(idx,n,','.join(map(literal,layer['bias']))))
        text.append(' float h%d[%d];'%(idx+1,n))
        activation='if(v<0)v=0;' if idx+1<len(model['layers']) else ''
        text.append(' for(int j=0;j<%d;++j){float v=b%d[j];for(int i=0;i<%d;++i)v+=w%d[j][i]*h%d[i];%sh%d[j]=v;}'%(n,idx,width,idx,idx,activation,idx+1))
        width=n
    assert width==1
    text.append(' float z=h%d[0];z=z<-1?-1:(z>1?1:z);'%len(model['layers']))
    if model['base_skip']:text.append(' z+=x[13];')
    text.append(' return std::isfinite(z)?z:std::numeric_limits<float>::infinity();\n}\n')
    return '\n'.join(text)


def export(model_path, out, ws):
    model=json.loads(Path(model_path).read_text());out=Path(out);out.mkdir(parents=True,exist_ok=False)
    score=scorer(model);(out/'score.hpp').write_text(score,encoding='utf8')
    shared=(ws/'hashjoin_lab/reports/collaboration_20261020/round66_offline_oracle/shared_pool.hpp').read_text()
    policy=(ws/'tmp/r70_nn_pipeline/policy.hpp').read_text().replace('#include "shared_pool.hpp"','').replace('#include "tiny_score.hpp"','')
    source=shared+'\n'+score+'\n'+policy
    (out/'MySpillScheduler.cpp').write_text(source,encoding='utf8')
    return source
