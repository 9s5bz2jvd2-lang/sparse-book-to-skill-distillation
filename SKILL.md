---
name: 稀疏蒸馏 | Book-to-Skill Sparse Distillation
description: |
  当用户提到“稀疏蒸馏 / 图书蒸馏 / book-to-skill / textbook distillation / 把一本书或长资料蒸馏成 skill / 大型 Skill 库设计 / DeepSeek 稀疏激活 / MoE 式 Skill 调用 / missed-case sweep / 漏诊式扫查 / 预算化引用 / Skill Graph / Orange Book 转 Skill / 方法论蒸馏成可调用技能”时使用。此 skill 指导 agent 把书籍、长文档、课程、仓库文档、研究资料或项目方法论，蒸馏成一个“可稀疏调用、可查漏、可分层预算、可渐进披露、可回流评测”的 Skill 包，而不是普通摘要。核心思想：shared core 常驻，top-k 章节/技能专家稀疏激活，低预算邻域扫查防遗漏，heavy reference 按需加载，route logs 回流改进。严禁复制受版权保护原文、伪造来源、把私有项目细节写入公共 skill。
version: 1.0.0
tags: [skill-authoring, distillation, textbook, sparse-routing, progressive-disclosure, moe, deepseek, missed-case-sweep]
---

# 稀疏蒸馏 | Book-to-Skill Sparse Distillation

> **蒸馏不是把一本书压缩成摘要；蒸馏是把一套知识炼成后来者能稀疏调用、查漏验证、持续回流的 Skill Graph。**

此 skill 融合四条脉络：

1. **图书/教材蒸馏**：把书籍、长文档、课程或方法论变成可学习、可执行、可复用的课程/技能结构。
2. **DeepSeek / MoE 式稀疏激活**：很多专家存在，但每次任务只激活少数最相关专家，同时保留 shared core。
3. **临床营养式漏诊扫查**：先抓主问题，再低预算扫红旗、禁忌、特殊人群、证据边界和相邻误触发，避免“省 token 省出风险”。
4. **LingTai #177 循环流形 / 回返成丹**：分支不算完成，直到它回到可复用的压缩结构；每次调用后的经验要回流成更短的 signature、checklist、gotcha、eval 或 reference brief。

它用于生成一个新的 skill 包，或改造已有 skill，使其从“孤立文件夹”升级为：

> **shared-core + cross-linked top-k routed experts + missed-case sweep + budgeted references + cache-friendly layout + cyclic return-to-cache feedback loop**

一句话：**网给 skill 以通达，环给 skill 以低功耗；分支出去，回流成丹。**

---

## 何时使用

使用此 skill，当人类或任务要求：

- 把一本书、教材、指南、课程、长文档、论文集或仓库资料“蒸馏成 skill”；
- 把 Orange Book / 方法论 / 项目经验变成 agent 可调用技能；
- 设计大型 Skill 库，避免每次调用加载全部内容；
- 基于 DeepSeek / MoE / sparse activation 思路优化 Skill 调用；
- 给 skill 加 ROUTING、GRAPH、CACHE、预算层级、查漏清单、eval；
- 把“读书笔记/摘要”升级成可执行的 agent workflow；
- 需要在医学、营养、法律、财务等高风险领域蒸馏资料，必须既省 token 又防漏项。

## 不要何时使用

不要用此 skill：

- 只是要一段普通摘要、读后感或章节概括；
- 只是问书中一个事实点，直接回答即可；
- 用户想规避购买/阅读，把受版权保护书籍原文完整复刻出来；
- 资料没有授权、没有可引用来源，且任务要求公开分发；
- 当前只是私有项目事实，应写入 knowledge，而非公共 skill；
- 还没有足够材料形成触发条件、流程、红线和验收门。

---

## 输入

最小输入：

```markdown
- 源材料：书籍 / 长文档 / 课程 / 仓库 / 论文集 / 项目经验
- 蒸馏目标：学习课程 / agent skill / workflow / research guide / product playbook
- 目标使用者：人类学习者 / agent / 营养师 / 开发者 / 审稿者 / 运营者
- 可公开边界：可公开 / 仅内部 / 只可抽象方法不得暴露事实
- 风险领域：医学 / 营养 / 法律 / 金融 / 版权 / 隐私 / 普通低风险
```

推荐补充：

```markdown
- 章节目录或资料结构
- 用户最常见任务入口
- 必须保留的核心判断
- 容易遗漏的风险点
- 重复性确定工作是否可脚本化
- 需要生成的资产：templates / schemas / scripts / examples / evals
```

---

## 输出

一个可用 skill 包，推荐结构：

```text
<skill-name>/
├── SKILL.md             # 最小可执行入口：触发、流程、红线、查漏、验收
├── ROUTING.yaml         # 触发词、反触发、邻居、预算、查漏项
├── GRAPH.md             # 上游/下游/相邻/互斥/安全门关系
├── CACHE.md             # stable prefix / variable suffix / on-demand reference 布局
├── reference/
│   ├── source-map.md    # 源材料地图；不复制原文
│   ├── theory.md        # 长理论和解释
│   └── examples.md      # 少量去私有化示例
├── assets/
│   ├── output-template.md
│   └── eval-cases.md
└── scripts/             # 可选：索引、路由、抽取、校验脚本
```

若任务较小，可只交付 `SKILL.md + ROUTING.yaml + assets/output-template.md`。

---

## 核心模型：三层蒸馏

### 1. Source layer：源材料层

回答：**这本书/资料到底有什么结构？**

- 建目录树、主题树、概念表；
- 标注哪些是核心理论、例子、流程、公式、证据、警告；
- 标注来源位置，但不要大段复制原文；
- 区分“可公开复述的概念”和“不能公开再分发的原文/私有数据”。

### 2. Skill layer：可执行技能层

回答：**后来 agent 遇到什么任务时该怎么做？**

- 抽触发条件；
- 抽最小流程；
- 抽分支判断；
- 抽红线/gotchas；
- 抽验收门；
- 把确定性苦力交给 scripts；
- 把长背景放 reference，按需加载。

### 3. Runtime layer：稀疏调用层

回答：**这套 skill 被调用时怎样省 token 而不漏风险？**

- shared core 常驻；
- top-k 专家稀疏激活；
- 邻域低预算查漏；
- heavy reference 只在必要时读；
- route/case 记录回流，改进触发和查漏。

---

## 稀疏蒸馏十步

### Step 1：立边界，先判能不能蒸馏

先问：

1. 源材料是否可合法读取？
2. 目标是学习/复用方法，还是复制原文？
3. 蒸馏结果是给人看，还是给 agent 调用？
4. 是否涉及医学、营养、法律、金融等高风险判断？
5. 是否有私有路径、聊天、客户资料、凭证需要剥离？

若版权或隐私不稳：只做**结构化学习笔记/私有 knowledge**，不要做可分发 skill。

### Step 2：建 source map，不写流水账摘要

把源材料拆成可路由单元：

```markdown
| 单元 | 来源位置 | 主题 | 作用 | 风险 | 可否进公开 skill |
|---|---|---|---|---|---|
| Ch1 | 第1章 | 基础概念 | shared core | 低 | 可抽象复述 |
| Ch4 | 第4章 | 具体案例 | reference/example | 中 | 去私有化后可用 |
| Appx | 附录 | 表格/公式 | script/schema | 低 | 可改写为工具 |
```

关键：source map 是导航，不是复制原文。

### Step 3：抽 shared core

shared core 是每次调用都应知道、但必须极短的内容：

- 核心定义；
- 安全/证据/版权红线；
- 输出原则；
- 本 skill 与相邻 skill 的边界；
- 必须查漏的总清单。

写法：压到 200–800 tokens，稳定、可缓存、少改动。

### Step 4：抽 routed experts

把书/方法论拆成“专家节点”，每个节点对应一类任务，而不是对应机械章节。

示例：一本营养评估书不要只拆成 Ch1/Ch2/Ch3，而应拆成：

```text
anthropometry-expert       # 身体测量/生长曲线
intake-analysis-expert     # 膳食记录分析
medical-red-flag-expert    # 医学转诊/禁忌
behavior-change-expert     # 行为干预沟通
report-writing-expert      # 报告生成
```

每个 expert 都要有：

```yaml
trigger_terms:
anti_triggers:
budget_default:
minimum_workflow:
load_more_if:
missed_case_items:
```

### Step 5：设计 sparse-first activation

每次调用先只选 top-k：

```text
user task → shared core → route candidates → top-k experts → main workflow
```

经验规则：

| 场景 | top-k |
|---|---:|
| 简单低风险任务 | 1 |
| 普通跨章节任务 | 2–3 |
| 高风险医学/营养/法律 | 主 expert 1–2 + safety gate |
| 大型综合产出 | 3–5，但分批处理 |

不要为了“全面”一次加载全书/全库；全面应由查漏和按需加载完成。

### Step 6：设计 missed-case sweep

稀疏激活之后，必须做低预算扫查：

```text
main route done → neighbor/safety sweep → decide whether to load more → final answer
```

通用查漏项：

- 是否误触发了相邻 skill？
- 是否有反触发条件？
- 是否涉及特殊人群/禁忌/红旗？
- 是否缺证据或来源？
- 是否输出过度承诺？
- 是否遗漏用户真正目标？
- 是否需要转人工/建议专业帮助？

医学/营养类额外查漏：

- 不诊断、不替代治疗；
- 药物、慢病、妊娠、儿童、老人；
- 进食障碍/羞耻语言；
- 引用真实可核验；
- 个体化建议的边界。

### Step 7：分配预算层级

不是所有内容都配同样 token。

| 层级 | 用途 | 预算策略 |
|---|---|---|
| shared-core | 常驻原则/红线/路由边界 | 极小、稳定、可缓存 |
| routed-high | 主任务专家 | 中高预算 |
| routed-low | 相邻辅助专家 | 摘要/清单级预算 |
| missed-case-sweep | 查漏、红旗、反触发 | 小预算 checklist |
| heavy-reference | 原理、案例、长表、模板 | 明确需要才读 |
| script/tool | 确定性抽取/统计/校验 | 不烧 LLM token |

### Step 8：写 cache-friendly 布局

把稳定内容放前，变化内容放后：

```text
stable prefix:
  - skill identity
  - shared core
  - routing schema
  - must-not-miss checklist
  - output contract

variable suffix:
  - current user task
  - selected route
  - retrieved excerpts
  - case-specific data
  - draft/output
```

避免把用户私有数据、临时检索结果、长 excerpt 混入稳定前缀。

### Step 9：建立 eval 和 route log

至少设计 5 类测试：

1. **正触发**：该 skill 应被调用；
2. **反触发**：相似但不该调用；
3. **邻域查漏**：主 skill 对，但必须扫某个邻居；
4. **安全红线**：必须拒绝、降级或转介；
5. **预算测试**：不加载 full reference 也能完成最小任务。

建议记录 route log：

```json
{
  "task_type": "diet_record_analysis",
  "selected_experts": ["intake-analysis", "medical-red-flag"],
  "skipped_experts": ["sports-nutrition"],
  "sweep_hits": ["eating-disorder-risk"],
  "loaded_references": ["brief/intake-patterns.md"],
  "budget_tier": "medium",
  "outcome": "needs_followup_questions"
}
```

### Step 10：回流成 Skill Graph

完成后回看：

- 哪些触发词该加入 ROUTING？
- 哪些 missed cases 真的命中？
- 哪些 reference 太重，应拆 brief/full？
- 哪些流程可以脚本化？
- 哪些私有事实应该移出 skill、进入 knowledge？
- 是否应生成 issue/PR 改进上游 skill？

---

## 推荐文件说明

### `SKILL.md`

只放最低必要内容：

- 何时用 / 何时不用；
- 输入 / 输出；
- 最小 workflow；
- 查漏清单；
- 红线；
- 验收标准；
- 需要更多时读什么。

### `ROUTING.yaml`

放结构化路由信息，供 agent、脚本或未来 runtime 使用。

### `GRAPH.md`

说明本 skill 与其他 skill 的关系：上游、下游、邻近、互斥、安全门。

### `CACHE.md`

说明哪些内容适合稳定前缀，哪些必须作为变量后缀或按需 reference。

### `reference/source-map.md`

记录源材料结构与可公开边界，避免未来忘记来源。

### `assets/eval-cases.md`

保存触发/反触发/查漏/安全测试。

---

## 红线

- **不复制原文**：不得把受版权保护书籍、课程、论文大段搬进 skill。
- **不伪造来源**：不知道来源就说不知道；不能编 DOI、书名、章节、年份。
- **不泄露私有事实**：聊天 ID、本地路径、客户资料、项目秘密、凭证不得进入公共 skill。
- **不把摘要当技能**：没有触发、流程、查漏、验收，就不是 skill。
- **不因稀疏而漏安全**：医学/营养等高风险任务即使 top-k 很小，也必须跑 safety sweep。
- **不一次加载全库**：除非人类明确要求做全量审计；日常调用应渐进披露。

---

## 验收门

完成一个稀疏蒸馏 skill 前，逐项检查：

- [ ] frontmatter 有 `name` 和可触发的 `description`；
- [ ] `SKILL.md` 能在不读长 reference 的情况下执行最小任务；
- [ ] 有 `ROUTING.yaml` 或等价路由段：触发、反触发、邻居、预算、查漏；
- [ ] 有 missed-case sweep，且高风险领域有安全/证据门；
- [ ] 长材料被拆到 `reference/`，不是塞满入口；
- [ ] 能区分 shared core、routed expert、heavy reference；
- [ ] 有至少 5 个 eval cases；
- [ ] 没有版权原文、私密路径、token、个人聊天内容；
- [ ] 输出模板清楚说明“来源/边界/下一步”；
- [ ] 写明如何把使用反馈回流到路由和查漏。

---

## 快速模板

最小新 skill 文件夹：

```text
my-sparse-distilled-skill/
├── SKILL.md
├── ROUTING.yaml
└── assets/eval-cases.md
```

`SKILL.md` 最小骨架：

```markdown
---
name: <skill-name>
description: |
  当用户提到 <触发场景>，并需要 <可执行目标> 时使用。此 skill 使用 shared core + top-k routed experts + missed-case sweep 处理任务；长资料按需读取 reference；禁止 <关键红线>。
version: 1.0.0
---

# <skill-name>

## 何时使用

## 不要何时使用

## Shared core

## Sparse route

## Missed-case sweep

## Workflow

## Load more only if needed

## Output contract

## Red lines

## Acceptance checks
```

---

## 一句话口诀

> **先炼核心，再分专家；先中主脉，再扫旁枝；预算分层，重料后置；路由留痕，越用越准。**

或更短：

> **一核常驻，数技稀疏；先抓主症，再查漏诊；重料按需，回流成图。**
