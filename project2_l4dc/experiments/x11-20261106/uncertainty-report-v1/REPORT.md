# X11 配对比值的不确定性补充

原 X11 已被接受的逐档配对比值文件给出中位数和IQR，遗漏了全局F8要求的系统级
bootstrap区间。本补充只给既定点统计增加区间，属于正式数据和原报告完成后的
后补分析。随机种子、重采样规则和重复数在本次分析前写入PROTOCOL.json；不能
将它描述成原先的正式预注册。

点统计仍是：先算同系统同种子的dense/truncated gap比，取每个系统4种子的
中位数，再取8个系统中位数的中位数。8个系统整群有放回重采样5000次，每群
保留4个配对种子。每个(n,m)使用frozen_engine.rng(620,11,n,m)的一套共同
重采样索引，跨所有N和两种ratio_kind复用。区间为逐格95%百分位区间，不能
视为全部曲线的同时置信带或总体成功概率保证。

全部130行的原始字段原样保留，点中位数逐行精确复现；补充字段为CI、重复数、
有效/无效质量和方法标签。所有4160条新/复用的arm-prefix记录均稳定且gap有限，
因此两种比值定义在此补充中一致，全部重复有效。原始拟合/轨迹、原CSV、
样本成本、图表和既有结论均未修改；没有新数据采集、模型求解或训练，GraceSU0。

文件：paired_gap_ratios_by_N_with_CI.csv、PROTOCOL.json、DRAW_IDENTITIES.json、
VERIFIED.json。全部源CSV的原有SHA已按report-v2/REPORT_GENERATED.json核对。
