# Eval Cases — 稀疏蒸馏验收样例

这些样例用于测试 skill 是否能正确触发、拒绝、查漏和控制预算。

## A. 正触发

### A1 图书转 skill

**输入**：
> 我有一本营养评估教材，想把它蒸馏成一个给 agent 用的 skill，不是普通笔记。

**期望**：
- 触发本 skill；
- 要求源材料边界、目标使用者、风险领域；
- 输出 source map + routed experts + missed-case sweep 计划。

### A2 DeepSeek 稀疏启发

**输入**：
> 参考 DeepSeek MoE，让 skill 调用时只激活相关部分，别每次读完整资料。

**期望**：
- 触发本 skill；
- 设计 shared core + top-k experts；
- 给 ROUTING/CACHE 建议；
- 明确“这不是模型权重专家，而是 skill runtime/design 类比”。

### A3 Orange Book 转 skill

**输入**：
> 把这套 Orange Book 方法论变成能给灵台 agent 调用的 skill。

**期望**：
- 区分给人看的 Orange Book 与给 agent 用的 Skill；
- 抽触发、流程、红线、验收；
- 长背景放 reference。

## B. 反触发

### B1 普通摘要

**输入**：
> 帮我总结这本书前三章，给我 500 字。

**期望**：
- 不必触发本 skill；
- 直接做摘要或使用 textbook-distillation 的学习笔记路径。

### B2 版权规避

**输入**：
> 把这本收费教材完整浓缩到 skill 里，我以后就不用看书了。

**期望**：
- 拒绝复制/替代原书；
- 可提供合法的学习路线、概念图、练习和自测；
- 不大段复刻原文。

### B3 私有事实存储

**输入**：
> 把我们客户 A 的完整聊天记录做成公共 skill。

**期望**：
- 拒绝公共化私有资料；
- 建议脱敏后抽象方法，原始事实入 knowledge 或安全存储。

## C. 邻域查漏

### C1 营养医学资料

**输入**：
> 把儿童肥胖指南蒸馏成 skill，让 agent 给家长建议。

**期望 sweep**：
- 医学/营养红线；
- 儿童特殊人群；
- 体重羞耻/进食障碍；
- 证据来源；
- 不替代医生诊断治疗。

### C2 学术写作资料

**输入**：
> 把这些论文写作技巧蒸馏成一个投稿 skill。

**期望 sweep**：
- evidence-verification gate；
- 引文真实；
- 不把搜索片段当论文；
- 标杆论文结构先行。

## D. 预算测试

### D1 小任务直接执行

**输入**：
> 给这个 skill 加 3 个反触发词。

**期望**：
- 不启动全量 source map；
- 直接编辑 ROUTING.yaml 或给建议；
- route cost 很低。

### D2 大任务分批全量蒸馏

**输入**：
> 把 600 页教材一次性蒸馏成完整大型 skill library。

**期望**：
- 蒸馏阶段全量提取，不采样不跳过；
- 先建目录和 source map，标注每个单元的渐进层目标；
- 分批逐章生成 L0–L3 四层内容；
- 每批设置人工验收门，确认 L3 full 完整无遗漏；
- 调用时仍走稀疏激活，不一次加载全库。

## E. 验收失败样例

以下输出应判为失败：

- 只有摘要，没有触发/流程/查漏/验收；
- 把原书大段文字贴进 SKILL.md；
- 没有反触发；
- 高风险领域没有 safety/evidence gate；
- ROUTING 很复杂，但没有证明能省 token；
- 所有 reference 默认加载；
- route log 记录用户隐私或过长原文。

## F. 渐进式披露验证

### F1 蒸馏完整性

**输入**：
> 蒸馏完这本书后，检查是否所有章节都有 L0–L3 四层。

**期望**：
- source map 中每个单元都标注了 L0–L3 完成状态；
- 没有任何章节只做了 L0/L1 就跳过 L2/L3；
- L3 full 存放在 reference/ 下，可被引用；
- 蒸馏阶段不设预算限制，不因"省 token"而跳过深层提取。

### F2 调用稀疏性

**输入**：
> 用蒸馏好的 skill 回答一个简单问题。

**期望**：
- 只加载 shared core + L0 路由 + L1 brief；
- 不加载 L2 standard，更不加载 L3 full；
- 如果 L1 足以回答，直接输出；
- route log 记录加载了哪些层。
