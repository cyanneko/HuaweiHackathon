# cyanneko · 已发布R48＋R54＋R58数据，eval 0.4.0

**已发布0.4.0：3项测试、两次CLI复现和全64例数据审核、独立发布复核通过。** 共64份输入和64份同名meta，train/eval各32；R58增加8/8。原48输入与48元数据逐文件保留原字节，原0.3.0审核记录不覆盖。

| 来源 | train | eval | 边界 |
| --- | ---: | ---: | --- |
| R48 | 8 | 8 | 历史开发数据；coverage_06..11为均衡分布诊断 |
| R54 v1.1 | 16 | 16 | 原发布输入与元数据，24/32组合案例 |
| R58 | 8 | 8 | 四家族各4例，8/16显式组合；原16例已独立审核 |
| 合计 | 32 | 32 | cyanneko一个有VERSION的成员集合 |

输入合计16,513,143字节，元数据合计2,098,853字节。数据属于合成开发/回归；train/eval共享构造，不是独立盲测、隐藏分布代表或泛化保证。生成参数、模式与q预测仅供离线审核，不进入在线策略。

## 清单和身份

[manifest.json](manifest.json)保存64例路径、来源、input/meta SHA、划分、原0.3.0来源和R58新增来源。旧48条case来源/哈希保留；原48输入和meta逐文件SHA与旧manifest相同。R58的txt/meta按冻结原件复制；新输入raw及modulo-P语义SHA与独立审核相符。

eval/VERSION已发布为0.4.0，个人eval指纹为`d686842e79b18cc4e8351c8d5bfd571c34ad961de470b6d4edd84868ba302f94`。该值由实际32txt＋32meta及VERSION计算，[不可变已发布版本](https://github.com/cyanneko/HuaweiHackathon/blob/875b6b0b99ec1b63ac37c11a99ea7f1a349b83a3/datasets/cyanneko/eval/VERSION)与[当前发布说明](../../docs/R58_PUBLICATION_STATUS.md)给出定位；文件指纹不表示已完成新版本评分。仅train改变时不改eval版本或suite_id。各轮数据不能当多个成员重复算分。

R58生成前spec的planned标签保留历史含义，当前原16例的实际独立审核见 [生成器来源](../../generators/r58/README.md)。原meta的q_observed=null表示生成时未诊断；不从之后结果回填meta或改写源数据。

## 审核状态与复现

[验证汇总](provenance/validation_0.4.0.json)、[全64例公共审核](provenance/public_audit_0.4.0.json)和[去重/头顺序](provenance/dedup_0.4.0.json)记录实际验证范围。原0.3.0的 [公共审核](provenance/public_audit_0.3.0.json) 和 [汇总](provenance/validation_0.3.0.json) 只覆盖原48例，不能替代0.4.0全64例审核。

本次从本分支根目录分别审核全部32eval和32train，未使用allow-small-memory。复核命令如下，输出放输入目录之外：

```sh
python evaluation/scripts/audit_datasets.py --root datasets/cyanneko/eval --out results/cyanneko-eval32-audit.json
python evaluation/scripts/audit_datasets.py --root datasets/cyanneko/train --out results/cyanneko-train32-audit.json
```

本次两报告各为32cases、0errors、0skipped，且与manifest名单精确匹配。独立CLI可能跳过不像输入的txt，且不检查团队额外的头升序约定；完整覆盖、升序与跨旧/新/划分/成员语义去重另做。本次另行验证了64份头升序，raw、完整操作流及modulo-P语义流各64个唯一值；其他成员当前仅有空占位，已记录跳过状态。原48输入/meta、旧审核记录及新16输入/meta的来源字节保持不变。

复现R58的8/8见 [公开生成器](../../generators/r58/README.md)，R54的16/16仍见 [R54入口](../../generators/r54/README.md)。生成器不自动加入R48或创建VERSION。

## 评分迁移

默认只评测各成员已有的非空eval；空成员跳过并记录，不等三人到齐。非空但无合法VERSION/内容错误则失败。成绩绑定实际成员VERSION、文件指纹和suite_id，按参与集合等权平均。

R57旧结果继续对应0.3.0的24eval与原直接程序。旧BF/SF封顶50不能继承到0.4.0；新成绩需冻结程序与数据后，重跑全部实际非空集合及新配对Naive，cyanneko覆盖完整32eval，不只跑新增8例、不拼接旧测量。train不参加集合评分，发布数据本身没有新成绩或性能验证。
