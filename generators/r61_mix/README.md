# R61 新组合数据生成器

Root recipe SHA为`971ceca5ef9caef7da0ffd30b9cf1e9f49d9a6296fccd2547903579e8bf1a91c`。只构造8train＋8原留出，不读模型/求解器输出，不按成绩筛选。实际数据在datasets分支，进入cyanneko0.5.0后总train/eval各40；原留出在R61冻结模型后开放检验，之后作为已观察开发数据，不称官方盲测或全新基本模式家族。

```sh
python generators/r61_mix/generate.py --out NEWDIR
```

NEWDIR必须不存在，输出train/holdout目录及清单；不会自动加入旧64例、成员目录或VERSION。当前发布映射原holdout文件到eval，但保留原文件与meta字节。metadata中的initial split/use是生成时的来源，当前用途见datasets说明和usage记录。

模式严格使用绝对local probe index，第二半不重置；case6阶段重叠，case7全驻留。每算子仅一次BUILD→SWITCH→PROBE，Probe模式反转不是回到BUILD。train为K2/P8/M64MiB，原留出为K3/P16/M96MiB，均满足合法范围；最多3240操作。

原生成器及冻结记录在provenance，原文件字节不改；公开版仅适配审计器/来源文件路径和公开身份检查。输入构造代码不变，发布前须逐个字节复现16输入；公开生成的meta仅允许generator_sha256与原件不同，不替换实际发布的原meta。

public_source_freeze只约束源码/recipe/审计器依赖，明确不包含README；它不是任意未来HEAD的全部文件清单。R61的0.4公共测量和独立8例结果不冒充0.5全40例评分；官方Naive评分基线不变。
