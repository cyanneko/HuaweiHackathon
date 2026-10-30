# 离线教师与有限状态诊断交接

`workspace/` 按原仓库相对路径保存源码和脱敏小报告。合并到总交接目录时，把其内容放在统一 workspace 根；根路径由脚本自身位置推导。纯 Python 离线方法只依赖标准库。此组件未执行求解、native、编译、训练或网络操作。

## 最小方法依赖

- `round66_offline_oracle/core.py`：输入读取、物理状态、整数写/读/miss账、参考回放。
- `round67_offline_quality/future_rollouts.py`：严格未来 PROBE 索引和 FIF/cost-aware/size-time spill优先级。
- `round70_offline_optimization/teacher_portfolio.py` + `tmp/r70_interval/interval_teacher.py`：三个旧完整构造；全局静态 BUILD→PROBE 输入另支持 density/short/sqrt_time 区间保留。INSERT出现在任意PROBE后时拒绝区间规则。
- `round70_offline_optimization/dynamic_teacher.py`：六组固定(alpha,beta,gamma)参数控制，按未来下一次PROBE时的绝对大小计Cnum，用整数交叉乘积排序；独立于旧AI标签。

上述 round 目录均在 `hashjoin_lab/reports/collaboration_20261020/` 下。它们使用完整未来，只有离线教师语义；并非在线调度器或OPT。状态动作域为溢出spill-only、miss需求LOAD-last、周期空动作。

## 输入恢复和身份

`provenance/offline_required_inputs.json` 明列56个原始输入的恢复相对路径、原始SHA和字节数：R70 train24/dev8/holdout8、corner stage0 train8、R78 100k train8；另列40份R70输入metadata身份。此组件不重复保存数据正文。总交接清单负责将它们映射到已发布固定数据提交。R70 config与3份generated manifest已包含，供AI组件`pipeline.inventory()`读取。

`provenance/offline_component_manifest.json` 分别记录冻结原件SHA与实际公开字节SHA。仅脱敏机器路径并规范JSON相对路径分隔符，不伪造旧文件SHA。原执行脚本中的冻结source/config SHA仍指原件；脱敏报告只能作为证据引用，不能假定所有旧冻结脚本可原样启动。

## 未来接手人运行的调用形状

以下示例在**合并后的workspace根**执行，需先按清单恢复并核对对应输入；这里没有执行它。`complete_rollout`只做Python参考计算，不产生官方验证通过的声明。

```python
from pathlib import Path
import sys
root = Path.cwd()
sys.path.insert(0, str(root / 'hashjoin_lab/reports/collaboration_20261020/round70_offline_optimization'))
from teacher_portfolio import Case, Context, complete_rollout
case = Case.read(root / 'tmp/r70_inputs/data/train/train_uniform_01.txt')
context = Context(case)
print(context.supported_methods())
state = complete_rollout(case, 'cost_aware_greedy', context=context)
print({'G': state.g, 'simulated_io_plus_miss': state.g / (case.w * case.r),
       'write_bytes': state.write, 'read_bytes': state.read, 'misses': state.miss,
       'formal_D': None, 'official_replay_verified': False})
# Independent fixed dynamic control, same input:
# import dynamic_teacher
# state = dynamic_teacher.complete_rollout(case, 'a0_b1_g1')
```

完整新实验必须用新输出目录、重新冻结运行身份和预算，再保存完整路径并独立回放。旧`tmp/r70/run_train.py --freeze`、`--execute`及`--worker CASE --seconds N`展示批次结构，含禁止覆盖的冻结检查，不能拿当前脱敏配置覆盖历史目录。R70输入生成的原命令形状为`python tmp/r70_inputs/run.py --split train --execute`，只应针对新受控目录/配置使用，不能覆盖已发布输入。

独立官方兼容回放依赖`round69_offline_scale/compact_harness.py`、R49冻结框架、R65 frozen_helpers/policy；`prepare()`原实现调用Windows的WSL Ubuntu与`g++ -std=c++14 -O2`。Linux原生使用者需另作受审适配，不能把该平台适配当作已验证。组件包含源码，不分发二进制。R69 store还间接依赖R67 baselines/official_harness和R66 shared_pool；已保留。

`worker_student48`、`worker_corner_r75`和`r78_scale_teacher`代码保留算法、选择、计账与验证逻辑；历史运行需要未分发的私有完整trace/witness和原生可执行文件，因此不是完整逐字节历史重跑包。AI组件提供pipeline、模型/协议/选择和已交付训练标签；这里不重复标签。新实验应从公开输入重新生成自己的运行证据，而非索取本地私有轨迹。

## 已有结论与证据边界

R70的24个train完整教师路径均优于actual VanBest，逐例等权平均模拟成本下降44.1609%，10/24优于旧三规则。只含IO+miss罚项，不含D；只有最终选中路径完成compact官方验证，不代表全分区全状态逐步一致、NN收益或OPT。

学生新状态批次实为46行、1152条完整分支，91条分支独立官方compact回放，剩余1061条为reference-only；fixed/finite-H后缀比较不是Q*或学生闭环收益。详细协议/报告保留，标签由AI组件交接。

Corner stage0为8个N8000 train输入、4条seed谱系、16个锚89条分支；12/16存在同一真实R75续跑下更好的当前动作，1行全tie应零权。16个原动作control复现完整轨迹/精确账。局部后缀差不能相加为整例加速，也不代表AI已超过R75。报告中的当时“尚未做100k门”是历史时点结论；后续R78另列。

R78只对4个100k train层各选1锚，共11条分支（含4control），3/4有局部改进；7个替代动作是4好、2差、1平。独立轻量review PASS限于保存证据/整数账/control核对，没有重走全部大trace以独立验证全局minhash，没有完整FAST suffix逐步轨迹一致性证明。辅助R65因果观察器不等同R75私有history。未训练或读dev，不能推断部署闭环收益。

`G = write_bytes*R + read_bytes*W + misses*penalty*W*R`，物理模拟成本为`G/(W*R)`。miss锚prefix已含触发miss，后缀不能再罚一次。插桩/离线墙时不是正式D。R79新数学候选与本组件旧AI监督来源独立，不混入标签。

后续先恢复固定数据、核对公开SHA并与AI组件合并；若做新规模/闭环实验，应保留train/dev/holdout边界、明确特征白名单，并在部署比较中计入实际D。本交接不启动新实验。
