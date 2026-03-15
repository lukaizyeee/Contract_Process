# 合同智能审计需求实现计划 (Implementation Plan for Contract Audit)

本文档基于 `需求-260211.txt`，详细描述了如何将现有的基于规则（Regex）的审计系统升级为基于语义理解（Semantic Search/RAG）的智能审计系统，并实现具体的修订与批注要求。注意，所有的合同变更都需要以修订模式留下痕迹，即所有的变更都需要在合同中以绿色下划线或红色删除线的形式展示。

## 1. 核心变更 (Core Changes)

1. **审计主体变更**:
   - 默认批注作者名称统一修改为 **"Dacheng"**。
   - 需先识别合同中的“我方”身份（Party A 或其他称呼），默认 Party A 为我方。
2. **技术路线升级**:
   - **现状**: 主要依赖正则表达式匹配关键词（如 `+86`, `invoice`）。
   - **目标**: 引入 **语义检索 (RAG)** 技术。先通过 Embedding 模型检索出与审计点相关的条款（如“付款条款”、“争议解决”、“通知条款”），再结合规则或 LLM（未来）进行判定，以提高准确率并减少误报。
3. **修订方式增强**:
   - 敏感信息（电话/邮箱）及签字人问题 -> **插入批注** (`[批注: ...]`)。
   - 条款缺失（发票、退款、银行变更、争议解决、代扣税） -> **插入新条款** (绿色下划线)。
   - 不利条款（罚息） -> **删除** (红色删除线)。

***

## 2. 详细需求对照与实现方案 (Detailed Requirements Mapping)

### 2.0 基础设置

- **需求**: 批注名称为“Dacheng”。
- **实现**: 修改 `TrackChangesHelper` 的默认 `author` 参数为 `"Dacheng"`。
- **需求**: 识别我方身份（默认 Party A）。
- **实现**: 在 `WordProcessor` 初始化时，增加一个简单的逻辑扫描首部定义（"This Agreement... between..."），提取 Party A 的指代。目前阶段可先硬编码默认逻辑，后续通过语义提取优化。

### 2.1 全文识别 (Global Check)

| 需求点              | 检索策略 (Search Strategy) | 判定逻辑 (Logic)            | 处理动作 (Action) | <br />                   |
| :--------------- | :--------------------- | :---------------------- | :------------ | :----------------------- |
| **1. 中国电话**      | 全文正则扫描 \`(+86          | 0086)?\s?1\[3-9]\d{9}\` | 命中即违规         | **批注**: `Please confirm` |
| **2. 126/163邮箱** | 全文正则扫描 \`@(126         | 163).com\`              | 命中即违规         | **批注**: `Please confirm` |
| **3. 邮件一致性**     | (暂不实现)                 | 需邮件输入接口，目前仅处理合同本体       | 预留接口          | <br />                   |

### 2.2 文首/文末 (Header/Footer)

| 需求点                  | 检索策略                | 判定逻辑                                          | 处理动作                     |
| :------------------- | :------------------ | :-------------------------------------------- | :----------------------- |
| **1. 代表人/权签人为中国人姓名** | 语义检索  "权签人", "代表人"  | 将相关度最高的几个给llm判断                               | **批注**: `Please confirm` |
| **2. 代表人/权签人没有职位信息** | 语义检索 "代表人/权签人的职位信息" | 给llm判断，是不是没有要求填写title，或者herein represented by | **批注**: `Please clarify` |

<br />

<br />

### 2.3 正文部分 (Body) - 核心业务逻辑

此处采用 **RAG (Retrieval-Augmented Generation)** 思路：先用语义向量召回相关段落，再进行精细规则判断或llm判断。

#### **1. 发票条款 (Invoice)**

- **需求**: 付款方式需明确是“先开发票后付款”。如果没有，需要补充一段话。
- **检索 Query**: "付款方式", "payment terms", "payment schedule"
- **判定**:
  1. 检索 Top-3 相关段落。
  2. 将段落给llm，让llm判断是否符合需求。
  3. 若未包含，则视为缺失。
- **动作**: 在付款条款段落末尾 **插入**: `Party B shall issue a valid and lawful invoice of the corresponding amount to Party A prior to each payment made by Party A.`

#### **2. 退款条款 (Refund)**

- **需求**: 如果付款方式是预付款，需要说明：若合同解除，对方需退还我方付款但未使用的额度。如果未提及，需要补充一段话。
- **检索 Query**: "prepayment", "advance payment", "termination refund"
- **判定**:
  1. 检索 Top-3 相关段落。
  2. 将段落给llm，让llm判断是否符合需求。
  3. 若未包含，则视为缺失。
- **动作**: 在预付款/终止条款后 **插入**: `Upon expiration or early termination of this Agreement, Party B shall return any unused portion of the prepayment and issue a reverse invoice of the corresponding amount to Party A.`

#### **3. 银行账户变更 (Bank Account Change)**

- **需求**: 是否有银行账户信息，如果没有需以某种形式标注出来。如果有银行账户信息，需要识别是否有“银行账户信息变更需要双方确认”的表述，如果没有的话，在银行账户信息下面添加一段话。
- **检索 Query**: "银行账户信息"
- **判定**:
  1. 若未检索到银行信息 -> **批注**: `Missing bank account details`。
  2. 若检索到，让llm检查周围是否有 “银行账户信息变更需要双方确认”的表述。
- **动作**: 若缺失变更限制，在账户信息后 **插入**: `Any changes to the above bank account shall be subject to the prior written consent by both Parties.`

#### **4. 罚息/违约金 (Penalty)**

- **需求**: 检测是否有延期付款违约金/罚息相关内容。
- **检索 Query**: "late payment penalty", "interest on overdue payment", "default interest"
- **判定**: 相关度前3。
- **动作**: 标注出来，`Please check`。

#### **5. 争议解决 (Dispute Resolution)**

- **需求**: 规定法律适用（我方所在地）及管辖法院（我方所在地）。
- **检索 Query**: "governing law", "dispute resolution", "jurisdiction", "arbitration"
- **判定**:
  1. 若无此条款 -> 在文末或通用条款处新增。
  2. 若有但内容不符（如适用他国法律） -> 替换。
- **动作**: **替换/新增**: `This Agreement shall be governed by and construed in accordance with the laws of [My Country]. Any dispute arising out of or in connection with this Agreement shall be submitted to the exclusive jurisdiction of the competent courts located in the jurisdiction of Party A.`

#### **6. 代扣税 (Withholding Tax)**

- **需求**: 若双方地址在 菲律宾/巴基斯坦/墨西哥/香港/印度尼西亚，付款条款相关内容下面添加代扣税条款。
- **前置检查**: 扫描找到文首/文末地址信息，使用llm判断国家/地区。识别付款条款的位置
- **检索 Query**: "付款条款"
- **动作**: 若满足地域条件，在付款条款后 **插入**: `The withholding tax arising under this Agreement shall be withheld and remitted to the government authorities by Party A in accordance with applicable tax laws and regulations/ in the following month with a valid TDS Certificate provided.`

***

## 3. 代码改造步骤 (Refactoring Steps)

1. **更新** **`WordProcessor`** **初始化**:
   - 引入 `SemanticSearchEngine` 单例，用于执行段落检索。
   - 加载 `config` 以获取“我方国家”等配置。
2. **重构** **`audit_and_fix`**:
   - **Step 1: 文档切片 (Ingestion)**: 使用 `DocProcessor` 将文档切分为段落级 Chunks。
   - **Step 2: 向量化 (Embedding)**: 调用 `SemanticSearchEngine.load_document` 对当前文档进行临时索引。
   - **Step 3: 语义审计 (Semantic Audit)**:
     - 针对每个需求点（Invoice, Refund, Penalty...），构造 Query 进行 `engine.search`。
     - 获取 Top-K 段落及其索引（`original_index`）。
     - 在 `WordProcessor` 中根据索引定位 `doc.paragraphs` 中的具体段落对象。
   - **Step 4: 执行修订**:
     - 使用 `TrackChangesHelper` 对定位到的段落执行 Insert/Delete/Comment 操作。
3. **优化** **`TrackChangesHelper`**:
   - 确保所有操作默认作者为 `"Dacheng"`。
   - 增强 `add_comment` 的稳健性。



