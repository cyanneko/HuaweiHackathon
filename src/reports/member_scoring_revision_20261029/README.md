# 已有历史记录的成员等权未封顶重算

仅重新归约原normalization.cases，没有新solver、编译或训练；原raw报告字节不改。这三份历史记录当时都只有cyanneko一个非空成员，所以score_final等于该成员的未封顶逐例sum。R62为旧0.4/32，R63为旧0.5/40；不得跨不同集合/例数直接排名，也不把这些数字当当前两成员576例成绩。当前规则见公共evaluation/MEMBER_SCORING.md。

[
  {
    "method": "R62_soft",
    "frozen_version": "0.4.0",
    "n": 32,
    "single_member_score_final": 84.83593240697122,
    "raw_capped_average_score": 50.0,
    "report_sha256": "ac8ee90dbc964bb1d92a204017bd03ff8de384753d45d0197b9f8b659e695090"
  },
  {
    "method": "R62_pair8",
    "frozen_version": "0.4.0",
    "n": 32,
    "single_member_score_final": 77.6321824221594,
    "raw_capped_average_score": 50.0,
    "report_sha256": "1f51977e7ba0d10d4be11f28c28fcdde2106a28e43cec56423de6551d8732417"
  },
  {
    "method": "R63_ghost",
    "frozen_version": "0.5.0",
    "n": 40,
    "single_member_score_final": 149.75772370549234,
    "raw_capped_average_score": 50.0,
    "report_sha256": "07a3086c56972465a8c14f5e59c94101bce25828a0520cdba0456bc6f00dca42"
  }
]
