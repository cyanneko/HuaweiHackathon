from pathlib import Path
import re,json,hashlib
ROOT=Path(__file__).resolve().parent
text=(ROOT/'topic_20_current.txt').read_text('utf8')
start=text.index('#include <iostream>');end=text.index('参赛者实现指引',start)
cpp=text[start:end].replace('\xa0',' ').replace('\u200b','')
(ROOT/'reference_current.cpp').write_text(cpp,encoding='utf8')
marker='/* ===== 执行引擎 ===== */'
if marker not in cpp:
    marker='class HashJoinEngine'
cut=cpp.index(marker)
(ROOT/'reference_types.hpp').write_text('#pragma once\n'+cpp[:cut],encoding='utf8')
# Reference program with only the permitted scheduler substitution for integration QA.
integration=cpp[:cut]+'\n#include "MySpillScheduler.cpp"\n'+cpp[cut:]
integration=integration.replace('std::make_unique<NaiveSpillScheduler>()','std::make_unique<MySpillScheduler>()')
(ROOT/'integration_check.cpp').write_text(integration,encoding='utf8')
print('Extracted official code:',len(cpp),'chars; prefix:',cut)
