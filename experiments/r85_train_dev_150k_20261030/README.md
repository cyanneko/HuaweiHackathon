# R85 新面板 1.0.0

18份各150000操作、18条独立seed，12TRAIN/6DEV，无带宽配对，共2,700,000操作、55,241,149B。DEV已开发评测，不称OOD或盲测。动态/IID两个模型分开，shared/staggered与压力等参数有混杂，组差不作因果结论。

inputs.json列新输入/metadata公开路径、原始与公开SHA、配方与曝光状态；原dyna12/final2.1 eval72只固定引用c65，不复制1.64GB。后来的final3.0不混入旧结果。保留生成/全合法性审计和概率CSV/日志；发布者核input/meta/body SHA与N，完整逐操作审计继承冻结材料，无新生成或策略运行。研究面板不注册成员eval，不改旧VERSION/suite，不转DEV为TRAIN。
