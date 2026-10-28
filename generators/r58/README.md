# R58 固定构造数据生成器（已发布）

本目录是 R58 研究生成器的公开路径/输出适配。**已发布：cyanneko eval0.4.0，train/eval各32；3项测试、两次CLI复现、全64例数据审核和独立复核通过。新版本尚无完整评分，不表示性能有效。** 原件与固定参数已保留，不读任何求解器结果，不按结果挑选种子。

## 生成与范围

在仓库根目录，Python 3.10+，仅标准库：

```sh
python generators/r58/generate.py --out NEWDIR
python generators/r58/tests/test_generate.py
```

NEWDIR 必须不存在；仅向指定新目录写 train/eval 各 8 对 txt/meta、source_freeze.json 与 generation_report.json，不覆盖现有输入。该命令只复现 R58 的 16 例，不包含 R48/R54、不创建成员目录或 VERSION。实际共享数据只在 datasets 分支。

四个家族 positive_cycles、low_opportunity_mix、temporal_alignment_mix、no_op_controls 各含 variant0/1 与 train/eval，两类 mix 合计8/16。全部固定种子与精确参数见 [原 spec](case_specs_proposal.json)，构造与预测边界见[发布前设计快照](https://github.com/cyanneko/HuaweiHackathon/blob/5203ed4070e471ed48c9d013a2be40c176c5b7b8/generators/r58/DESIGN.md)。同家族构造被 train/eval 共享，属于合成开发/回归数据，不作盲测、隐藏分布或泛化保证。

原 spec 的 DESIGN_ONLY_NOT_GENERATED、planned_not_generated 等标签，以及冻结件的 before/outcome 字段，是生成前的历史快照。实际原始16例已生成并由独立脚本核对，见 [原生成报告](provenance/generation_report.json) 和 [独立数据审核](provenance/root_data_review.json)；原报告与公开适配验证是不同证据；后者见 [实际复现记录](provenance/public_reproduction.json)，更新后的32eval+32train公共审核存于datasets分支。

## 来源与适配

- [原生成器](provenance/generate.original.py) SHA256：`f6b9c8b257e3dd2b1f357aa0452d5b0424e7f52795e128901b24be90fbeddee3`。原件依赖研究目录布局且固定写 data，不能在这里原样运行。
- [原测试](provenance/test_generate.original.py)、[原冻结身份](provenance/source_freeze.original.json) 与 [生成前 spec 冻结](provenance/pre_execution_spec_freeze.original.json) 保留原字节。[原发布审阅清单](https://github.com/cyanneko/HuaweiHackathon/blob/5203ed4070e471ed48c9d013a2be40c176c5b7b8/generators/r58/provenance/release_freeze.json)分列原件/适配版与数据来源身份，作用域是该不可变提交的14个文件；当前README由独立的[当前文档清单](../../docs/R58_CURRENT_DOCUMENTS.json)记录。
- 公开版只调整 audit_datasets 的导入/来源路径、从原冻结记录读取历史设计/矩阵身份，以及 --out 和 UTF-8/LF 输出位置。generate_case 主体逐字符一致；seed、随机调用、操作构造和划分未改。公开版输出的 source_freeze 标为复现，不冒称在原实验结果之前冻结。
- 两次公开复现的16份meta互相字节一致，与原meta的JSON完全相同；原件/公开输出仅有CRLF→LF差异，逐例SHA见复现记录。datasets中16份meta保留原字节，不以公开输出覆盖原件。原 meta 的 q_observed=null 保留生成时含义，诊断结果另存结果包。
- 公开版依赖 [独立公共校验器](../../evaluation/scripts/audit_datasets.py)，原16 meta 的 audit source SHA 与它相同。原生成时审核、独立输入审核、公开入口复现和完整64例审核是不同证据。

## 已完成验证与评分边界

已运行3项测试与两次CLI生成：每次16txt精确匹配原件，公开meta双次字节相同且与原件JSON一致。全部32eval和32train公共审核各0错误/0跳过，精确覆盖、64份头升序与跨批次/划分/已有成员的raw/操作流/modulo-P语义去重通过；旧48对原字节不变。[独立发布复核](provenance/publication_review.json)已通过；本次数据与生成器已推送发布；当前完整数据为32eval＋32train。数据发布不产生新成绩；R57仍绑定旧0.3.0，新0.4.0成绩需重跑所有实际非空集合。

## 冻结清单的提交作用域

旧`provenance/release_freeze.json`保持原字节，SHA256为`ea2eb45954fc7d919e7acc59bd41002099ed0570161af79fbae002c57ffd930c`，校验对象是main提交`5203ed4070e471ed48c9d013a2be40c176c5b7b8`及其同步发布快照，不是任意后续HEAD。其14项包含旧版README和DESIGN；本README现已修正发布状态，不能拿旧README哈希校验当前说明。原DESIGN、原件、源码、spec、测试和审核证据均未改写。详见[发布状态与作用域](../../docs/R58_PUBLICATION_STATUS.md)，当前说明按新的文档清单核对；这不产生新的生成器或数据版本。
