# R58 已发布状态与文档作用域

2026-10-29，以下三个提交已正常推送并由双方独立读取远端确认。本页只澄清当前说明，不修改数据、算法或历史证据。

| 分支 | 不可变已发布提交 | 内容 |
| --- | --- | --- |
| main | [5203ed4](https://github.com/cyanneko/HuaweiHackathon/commit/5203ed4070e471ed48c9d013a2be40c176c5b7b8) | 公共生成器、说明与审核来源 |
| datasets | [875b6b0](https://github.com/cyanneko/HuaweiHackathon/commit/875b6b0b99ec1b63ac37c11a99ea7f1a349b83a3) | cyanneko eval0.4.0，train/eval各32 |
| source/cyanneko | [5a87f8c](https://github.com/cyanneko/HuaweiHackathon/commit/5a87f8c6fa3e1df50be80e17ff8e9a6e0966c587) | 公共副本；个人源码和R57结果未变 |

[版本文件](https://github.com/cyanneko/HuaweiHackathon/blob/875b6b0b99ec1b63ac37c11a99ea7f1a349b83a3/datasets/cyanneko/eval/VERSION)、[数据清单](https://github.com/cyanneko/HuaweiHackathon/blob/875b6b0b99ec1b63ac37c11a99ea7f1a349b83a3/datasets/cyanneko/manifest.json)和[已验证生成器源码](https://github.com/cyanneko/HuaweiHackathon/blob/5203ed4070e471ed48c9d013a2be40c176c5b7b8/generators/r58/generate.py)均固定到已发布提交。

数据共64txt＋64meta；R48 8/8、R54 16/16、R58 8/8。原48对及新增16对原字节保留。个人eval指纹为`d686842e79b18cc4e8351c8d5bfd571c34ad961de470b6d4edd84868ba302f94`；当前仅cyanneko非空时suite_id为`6b10c17d9f898fcf0966ef118596ecc2c6ee957062323018edb5fccc9c950175`。空成员跳过，成员/版本变化后以实际评测身份为准。

**0.4.0尚未完成全部实际非空集合的完整评分。** R57仍绑定0.3.0的24eval和原直接程序；R58对旧24与新8分别测量，不能拼成0.4.0完整成绩，不继承旧cap50。数据审核通过不等于性能验证。

## 历史审阅冻结

[旧release_freeze.json](https://github.com/cyanneko/HuaweiHackathon/blob/5203ed4070e471ed48c9d013a2be40c176c5b7b8/generators/r58/provenance/release_freeze.json) SHA256为`ea2eb45954fc7d919e7acc59bd41002099ed0570161af79fbae002c57ffd930c`，保持原字节。它的files数组只约束上表发布快照中的14个来源文件；主分支的generators/r58树为`379326a75182e70dfbebac4e62de5fcfc7ee6d97`。文件中的pending_push、proposed等值是审阅时的状态，不能作为当前是否已发布的判断。

覆盖的说明文件只有旧[生成器README](https://github.com/cyanneko/HuaweiHackathon/blob/5203ed4070e471ed48c9d013a2be40c176c5b7b8/generators/r58/README.md)和[DESIGN](https://github.com/cyanneko/HuaweiHackathon/blob/5203ed4070e471ed48c9d013a2be40c176c5b7b8/generators/r58/DESIGN.md)。当前生成器README为纠正发布事实而更新；DESIGN及其他冻结文件保持不变。核对历史清单时读取上述不可变提交中的文件，不能将旧README SHA套到当前HEAD，也不能静默改写旧清单使其适配新文档。

## 当前说明

[R58_CURRENT_DOCUMENTS.json](R58_CURRENT_DOCUMENTS.json)单列本次当前说明的路径、分支作用域和SHA256，包括四份公共Markdown及datasets专属README；清单不包含自身。它只记录文档字节，不是新数据或生成器发布冻结。输入/meta、VERSION、数据manifest、旧成绩、算法、生成器/spec/测试、原审核证据和旧release_freeze均未改动；无需重新生成或跑分。
