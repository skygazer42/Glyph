# 车辆、育儿/求职及全国金额规则独立核验

核验日期：2026-11-21。结论：本次范围内未发现需要修复的实质政策信息或金额公式错误。未修改实现、YAML或来源数据，仅新增独立金额/边界审计测试及本报告。测试覆盖不等于实际平台受理资格或资金承诺。

## 逐规则核对

|规则|官方标准与核验结果|
|---|---|
|National_Appliance|6类、一级能效/水效、扣各环节优惠后政府补贴前价格15%、1500元封顶、每人每类1件。不是旧2025年的20%/2000元；当前正确。|
|National_Digital|4类含智能眼镜、单件最终价不超过6000元、15%、500元封顶，手表手环同一品类；当前正确。6000元得到500、6000.01拒绝。|
|National_AutoScrap|新能源12%/2万元，燃油10%/1.5万元且<=2.0L；旧新能源不能换燃油获补；燃料首次注册门槛正确，金额向上取整至元。|
|National_AutoReplace|新能源8%/1.5万元，燃油6%/1.3万元且<=2.0L；与报废合计年度一人一次；同省发票登记、旧车所有权日期与凭证校验均明确。|
|Changzhou_AutoScrap、AutoReplace|复用全国比例，增加常州开票、江苏登记、额度核实和纯购新车重复申报人工审核；未凭空新增地方加成。官方常州范围和标准2026-01-30网页在线可读。|
|Changzhou_VehiclePurchaseTax|不含增值税计税价×10%，减税=min(税额×50%,15000)。amount为应缴税款，非补贴；30万元价税额15000、50万元价税额35000，封顶只作用于减税额。换电分开核算开票和有效标识要求在字段说明明确。|
|Changzhou_ChildcareAnnual|2025起出生每次年度3600，不按出生月份折减；首次出生当年或次年，此后连续两个年度申请；仅本次2026申领，不一次发满三年。|
|Changzhou_ChildcareTransition|只算2026归属年度：2023出生按生日月份×300（含满三岁当月），2024出生3600。未将2026延长首次申领直接当成补发所有历史年度；2022历史首次补领明确不在入口。|
|Changzhou_EmploymentJobsearch|2027届、江苏院校相应全日制非定向困难毕业学年生、不限户籍、六类困难身份一人一次1500。窗口2026-09与2027-05；2026-11不误发。|
|Changzhou_TalentSupport|2026-10-01至2030-12-31正式措施仅给最高1600元/月生活租房合计及最高30万房票。返回MANUAL_REVIEW、amount0，参考上限单列，未套用旧学历档位或旧周期。|
|Changzhou_ElectricBicycle|官方2026-01-23问答仅列条件，无有效金额和活动日期；入口人工核验，不套用旧2025年30%/1000元。|

## 在线官方依据

本次实际重新在线读取以下页面并与仓库原文比对；检索了2026变更线索，没有以搜索不到新文件宣称政策完整性获官方认证。

- 商务部2026家电数码通知，第一、四、五条：https://www.mofcom.gov.cn/zfxxgk/fdzdgknr/ztfl/gnmygl/art/2025/art_b0f88c7df21c4d7aa74d7408e84f8860.html
- 商务部汽车2026问答手册（比例、取整、旧车门槛、一次互斥、换电基数）：https://www.mofcom.gov.cn/zwgk/zcfb/art/2025/art_3fbdd57f4f1b4ab78c2d9457f3517569.html
- 常州置换范围：https://swj.changzhou.gov.cn/html/swj/2026/BHDBKPHH_0130/21590.html
- 常州置换标准：https://swj.changzhou.gov.cn/html/swj/2026/BHDBKPHH_0130/21591.html
- 常州报废范围：https://swj.changzhou.gov.cn/html/swj/2026/BHDBKPHH_0130/21586.html
- 常州报废标准：https://swj.changzhou.gov.cn/html/swj/2026/BHDBKPHH_0130/21587.html
- 财政部2023年第10号公告（明确2026—2027减半/限额）：https://hq.mof.gov.cn/tongzhitonggao/202307/t20230704_3894319.htm
- 财政部政策问答明确30万应缴1.5万、50万应缴3.5万：https://www.mof.gov.cn/jrttts/202306/t20230629_3893518.htm
- 江苏政府转载卫健委育儿标准：https://www.js.gov.cn/art/2025/8/8/art_90838_6974.html
- 常州2026-01-07发布会，第63—65行育儿标准及首次申请：https://www.changzhou.gov.cn/ns_news/504176776471710
- 常州2026-09-02求职公告（含两个窗口）：https://www.changzhou.gov.cn/ns_news/423178830957774
- 人才正式措施第12项和有效期：https://www.changzhou.gov.cn/gi_news/575178824994368
- 电动自行车2026条件问答：https://www.changzhou.gov.cn/ns_news/517176956560444

国家卫健委2026-07延长首次申领的最新官方检索记录亦确认续领安排不变：https://www.nhc.gov.cn/rkjcyjtfzs/c100148/202607/6db6c47697544b97bc86bc4ac78d0b32.shtml 。本次没有把该页面检索摘要当作完整新采集正文，也没有扩大现有试算范围。

## 执行路径及保留限制

四条全国YAML调用的是`trade_in_calculations.py`里的2026专用函数，`rule_engine.py`359—361附近显式映射。旧`subsidy_calculations.py`的通用`appliance_subsidy`、`auto_subsidy`、`consumer_coupon`仍可供其他配置调用，但不在这四条规则路径；其可选回调和缺省行为不能算作本次四条规则的信息错误。

2026-09人才旧政策废止替代的完整细则仍未核实，因此当前人才入口诚实停留在上限参考/人工复核；本次没有声称已完成个人学历定额计算。电动车也不计为已实现现金计算。跨年车补申请、实时预算、身份、车辆登记、税务车型电子标识、户籍/学籍/历史发放仍由主管平台核实。

## 验证

新增`tests/test_changzhou_benefit_vehicle_accuracy_audit.py`，67个参数化测试：四种汽车比例/封顶/向上取元、地方冲突与额度、产品6000元边界、购置税减税封顶、12个月出生对照、年末新生儿、求职窗口、人才/电动车不误发、必填事实逐字段删除。独立预期来自上述条文，使用YAML示例仅提供完整事实对象。
