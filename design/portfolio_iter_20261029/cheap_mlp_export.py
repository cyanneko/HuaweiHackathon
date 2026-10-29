"""Pure C++14 route exporter for the cheap numeric + previous-expert mini MLP.

This module has no file IO, compiler, fitter or CLI. The builder must insert the
returned methods into Scheduler.template and retain the model's common layers.
Online and PORTFOLIO_AUDIT routes call one shared float accumulation function.
"""
from __future__ import annotations

import math
import struct


# CHEAP_V2 contains 21 entries INCLUDING f30. Replacing f30 by eight categories
# gives 20 numeric + 8 one-hot inputs, not 29 inputs: h8=304 and h16=600 params.
NUMERIC_FEATURE_IDS = (0, 1, 2, 3, 4, 5, 6, 7, 17, 18, 19, 20, 21, 22,
                       23, 24, 25, 26, 27, 29)


def float32(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('MLP coefficients must be finite numeric scalars')
    answer = struct.unpack('<f', struct.pack('<f', float(value)))[0]
    if not math.isfinite(answer):
        raise ValueError('MLP coefficient is not finite float32')
    return answer


def scalar(value):
    text = format(float32(value), '.9g')
    return text + ('' if '.' in text or 'e' in text else '.0') + 'f'


def validate_model(model):
    """Validate the folded deployment schema and return its checked dimensions."""
    if model.get('kind') != 'cheap_mlp' or model.get('classes') != 8:
        raise ValueError('Expected an eight-class cheap_mlp model')
    features = model.get('numeric_feature_ids')
    if (not isinstance(features, list) or not features or
            any(type(f) is not int or f not in NUMERIC_FEATURE_IDS for f in features) or
            len(set(features)) != len(features)):
        raise ValueError('Numeric features must be unique O(1) cheap IDs, excluding f30')
    hidden = model.get('hidden')
    if type(hidden) is not int or hidden not in (8, 16):
        raise ValueError('This mini MLP supports hidden widths 8 or 16')
    count = len(features)
    if model.get('input_dim') != count + 8 or model.get('feature_count') != 32:
        raise ValueError('Input dimensions do not match numeric features plus eight categories')
    if model.get('previous_expert_encoding') != 'one_hot_8':
        raise ValueError('Expected a categorical previous-expert input')
    weights = model.get('weights', {})

    def vector(name, length):
        values = weights.get(name)
        if not isinstance(values, list) or len(values) != length:
            raise ValueError('Wrong vector dimensions: ' + name)
        for value in values:
            float32(value)

    def matrix(name, rows, columns):
        values = weights.get(name)
        if not isinstance(values, list) or len(values) != rows:
            raise ValueError('Wrong matrix row count: ' + name)
        for row in values:
            if not isinstance(row, list) or len(row) != columns:
                raise ValueError('Wrong matrix column count: ' + name)
            for value in row:
                float32(value)

    matrix('w1_numeric', hidden, count)
    matrix('w1_previous', hidden, 8)
    vector('b1', hidden)
    matrix('w2', 8, hidden)
    vector('b2', 8)
    parameters = hidden * (count + 8) + hidden + 8 * hidden + 8
    if model.get('parameters') != parameters:
        raise ValueError('Declared parameter count differs from actual weights')
    return features, hidden, parameters


def _cheap(feature):
    # Match the historical features(s,...), including f22's same-target double
    # counting and f19's CURRENT size for a pending INSERT. Do not "fix" them.
    mem = 'double(s.memory_limit)'
    size = 'double(bytes)'
    free = 'double(s.memory_limit-s.memory_used)'
    pending = '(s.next_op.type=="PROBE"||s.next_op.type=="INSERT")'
    no = 's.next_op.op_id'
    npart = 'int(s.next_op.key%s.num_partitions)'
    target = 's.operators[' + no + '].partitions[' + npart + ']'
    expressions = {
        0: 'float(double(s.memory_used)/' + mem + ')',
        1: 'float(' + size + '/' + mem + ')',
        2: 'float(std::max(0.0,' + size + '-' + free + ')/' + mem + ')',
        3: 'float(' + free + '/' + mem + ')',
        4: 'float(s.operators.size()/8.0)',
        5: 'float(s.num_partitions/64.0)',
        6: 'float(build)',
        7: 'float(s.operators[o].phase==Phase::PROBE)',
        17: 'float(s.next_op.type=="PROBE")',
        18: 'float(s.next_op.type=="INSERT")',
        19: '(' + pending + '?float(' + target + '.data_size/' + mem + '):0.0f)',
        20: '(' + pending + '?float(' + target + '.in_memory):0.0f)',
        21: '(' + pending + '?float(' + no + '==o):0.0f)',
        22: '(' + pending + '?float((build?s.operators[o].partitions[p].data_size+' + size + ':' + size + ')+' + target + '.data_size<=' + mem + '):0.0f)',
        23: 'float(s.write_bandwidth/10000.0)',
        24: 'float(s.read_bandwidth/10000.0)',
        25: 'float(double(s.miss_count)/double(std::max(uint64_t(1),tick(s))))',
        26: 'float(bounded(double(uint64_t(s.miss_count)+compensated_misses_-epoch_miss_)/double(std::max(uint64_t(1),tick(s)-epoch_))))',
        27: 'cheapMlpTargetHeat(s,o,p)',
        29: 'float(bounded(double(returns_-return_base_)/double(std::max(uint64_t(1),tick(s)-epoch_))))',
    }
    return expressions[feature]


def export_route(model):
    """Return class-member C++ code; does not read/write source or add layers.

    Numeric standardization is already folded into w1_numeric/b1. The eight
    categorical weights are accessed as one previous-expert column, avoiding an
    online one-hot vector. No online exp, softmax or normalization is needed.
    """
    features, hidden, _ = validate_model(model)
    weights = model['weights']
    count = len(features)

    def matrix(name):
        return '{' + ','.join('{' + ','.join(scalar(v) for v in row) + '}'
                              for row in weights[name]) + '}'

    def vector(name):
        return '{' + ','.join(scalar(v) for v in weights[name]) + '}'

    parts = []
    if 27 in features:
        parts.append(
            'float cheapMlpTargetHeat(const SystemState& s,int o,int p) const {'
            'int id=o*s.num_partitions+p;uint64_t now=tick(s),age=now>last_[id]?now-last_[id]:0;'
            'double h=double(heat_[id])/(1.0+double(age)/64.0);return float(h/(1+h));}\n')
    parts.append('static int cheapMlpDecision(const std::array<float,' + str(count) + '>& numeric,int previous) {\n')
    parts.append('    static constexpr float w1[' + str(hidden) + '][' + str(count) + ']=' + matrix('w1_numeric') + ';\n')
    parts.append('    static constexpr float category[' + str(hidden) + '][8]=' + matrix('w1_previous') + ';\n')
    parts.append('    static constexpr float b1[' + str(hidden) + ']=' + vector('b1') + ';\n')
    parts.append('    static constexpr float w2[8][' + str(hidden) + ']=' + matrix('w2') + ';\n')
    parts.append('    static constexpr float b2[8]=' + vector('b2') + ';\n')
    parts.append('    if(previous<0||previous>=8)previous=7;\n')
    parts.append('    std::array<float,' + str(hidden) + '> activation;\n')
    parts.append('    for(int j=0;j<' + str(hidden) + ';++j){float value=b1[j];\n')
    parts.append('        for(int i=0;i<' + str(count) + ';++i){float product=w1[j][i]*numeric[i];value=float(value+product);}\n')
    parts.append('        value=float(value+category[j][previous]);activation[j]=value>0.0f?value:0.0f;}\n')
    parts.append('    int best=0;float best_value=0.0f;\n')
    parts.append('    for(int e=0;e<8;++e){float value=b2[e];\n')
    parts.append('        for(int j=0;j<' + str(hidden) + ';++j){float product=w2[e][j]*activation[j];value=float(value+product);}\n')
    parts.append('        if(e==0||value>best_value){best=e;best_value=value;}}return best;\n}\n')
    parts.append('int route(const SystemState& s,int o,int p,bool build,int64_t bytes) const {\n')
    parts.append('    const std::array<float,' + str(count) + '> numeric={{' + ','.join(_cheap(f) for f in features) + '}};\n')
    parts.append('    return cheapMlpDecision(numeric,selected_expert_);\n}\n')
    parts.append('#ifdef PORTFOLIO_AUDIT\nint routeReference(const std::array<float,32>& x) const {\n')
    parts.append('    const std::array<float,' + str(count) + '> numeric={{' + ','.join('x[' + str(f) + ']' for f in features) + '}};\n')
    parts.append('    int previous=int(double(x[30])*7.0+0.5);return cheapMlpDecision(numeric,previous);\n}\n#endif\n')
    return ''.join(parts)


def export(model):
    """Convenience alias for builders; still a pure string transformation."""
    return export_route(model)
