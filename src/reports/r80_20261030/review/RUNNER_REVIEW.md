# R80 runner静态复核

性能前发现的门禁与分母问题已修复；当前源码静态通过。Root独占runner，本review未改代码、未运行native或root测试。

final固定commit/version、Root输入合同及旧24的ID/SHA零交集已检查；producer最终release/PASS测试与所有固定evaluator依赖已绑定。训练筛选要求new10<1、old16<=1.05、all26worst<=1.25、累计D比<=2，且分母完整16/10/26、baseline D正值，最多2名；该规则已在结果前同步plan。任何格缺失/失败均不产生完整分组或advance。

final逐例含D总成本按同例Naive归一，C或B为0时得0分，固定24例等权；D字段单位μs，累计D之比与同例集合平均D之比相同。训练无Naive则不伪造标准分。最近秩分位数ceil(q*n)。

主runner改为一次性exclusive写入，删除反复覆盖progress路径；继承process helper仍会更新ownership.json，应仅在RELEASED后审读。180秒active timer不含依赖验证/复制binary/import等前置操作，不应写成端到端墙钟上限。

审查runner SHA: `ebfe95a63b954eee4d9208aa9fbdec7916e68d08505e57d8ed71256036381da0`。
