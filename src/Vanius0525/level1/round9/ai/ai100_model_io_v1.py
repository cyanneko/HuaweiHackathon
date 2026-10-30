"""Read the deployed decimal constants, preserve IEEE754 doubles, export C++14."""
import json,math,re,struct
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def bits32(x):return struct.unpack('<I',struct.pack('<f',x))[0]
def bits64(x):return struct.unpack('<Q',struct.pack('<d',x))[0]
def frombits32(x):return struct.unpack('<f',struct.pack('<I',x))[0]
def function_span(source,name='neural'):
    start=source.index('    double '+name+'(');brace=source.index('{',start);depth=0
    for end in range(brace,len(source)):
        depth+=(source[end]=='{')-(source[end]=='}')
        if depth==0:return start,end+1
    raise AssertionError('unclosed function')
def read_model(source):
    start,end=function_span(source);body=source[start:end];arrays={};declarations=[]
    for name,shape in [('W0',[12,16]),('B0',[16]),('W1',[16])]:
        pat=r'static const double '+name+r'((?:\[\d+\])+)' +r'\s*=\s*(\{.*?\});'
        found=re.search(pat,body,re.S);assert found
        assert list(map(int,re.findall(r'\d+',found[1])))==shape
        value=json.loads(found[2].replace('{','[').replace('}',']'))
        assert len(value)==shape[0] and (len(shape)==1 or all(len(v)==shape[1] for v in value))
        arrays[name]=value;declarations.append(found[0])
    bias=re.search(r'double y = ([+\-\d.eE]+);',body);assert bias
    return {**arrays,'b':float(bias[1]),'feature_input':'IEEE754 float32 then double arithmetic','architecture':[12,16,1]},declarations,bias[1]
def flat(model):return [v for row in model['W0'] for v in row]+model['B0']+model['W1']+[model['b']]
def forward(model,features,raw=False):
    f=[f32(x) for x in features];v=model['B0'].copy()
    for i in range(12):
        x=float(f[i])
        for j in range(16):v[j]+=x*model['W0'][i][j]
    y=model['b']
    for j in range(16):
        if v[j]>0:y+=v[j]*model['W1'][j]
    return (y,v) if raw else max(0.,min(1.,y))
def literal(value):
    if isinstance(value,list):return '{'+','.join(literal(x) for x in value)+'}'
    return format(value,'.17g')
def declarations(model):
    return ['static const double W0[12][16] = '+literal(model['W0'])+';',
            'static const double B0[16] = '+literal(model['B0'])+';',
            'static const double W1[16] = '+literal(model['W1'])+';']
def export(model):
    return '// Same frozen ai100 double weights; generated from Python, no retraining.\ninline double ai100_exported_neural(const float* f) {\n'+\
      '\n'.join('    '+s for s in declarations(model))+\
      '\n    double v[16];for(int j=0;j<16;++j)v[j]=B0[j];\n    for(int i=0;i<12;++i){const double x=f[i];for(int j=0;j<16;++j)v[j]+=x*W0[i][j];}\n    double y='+literal(model['b'])+';\n    for(int j=0;j<16;++j)if(v[j]>0)y+=v[j]*W1[j];\n    return std::max(0.0,std::min(1.0,y));\n}\n'
def features(c):
    q=c['q'];last=c['last'];previous=c['previous'];age=1000000. if last<0 else max(0,q-last)
    gap=1000000. if previous<0 else last-previous
    return [f32(c['size']/c['memory']),f32(min(16.,math.log2(1+age))/16),f32(min(16.,math.log2(1+gap))/16),
      f32(min(1.,c['count']/16)),float(last>=0),float(c['phase']),float(c['same_context']),f32(c['need']/c['memory']),
      f32(c['used']/c['memory']),f32(min(1.,c['observed']/max(1,q))),f32(f32(min(8,c['streak']))/8),
      f32(f32(c['distance'] if c['streak']>=3 else c['p'])/c['p'])]
