Run the NZ tax filing assistant to help with your annual IR3 tax return.

## 用法

```bash
/Users/jason.shao/Documents/GitHub1/claude_code_jshao/.venv/bin/python3 ~/Documents/GitHub1/claude_code_jshao/.claude/commands/nz-tax/nz_tax.py <PDF文件夹路径> [--rental-share 0.5]
```

- `--rental-share` 可选，默认 `1.0`（100%）。若出租房产为联名共有，填持股比例。

**实际用法（联名共有，各50%）：**
```bash
/Users/jason.shao/Documents/GitHub1/claude_code_jshao/.venv/bin/python3 ~/Documents/GitHub1/claude_code_jshao/.claude/commands/nz-tax/nz_tax.py ~/Documents/NZ/tax/JIa\ Shao --rental-share 0.5
```

## 支持的 PDF 类型

把以下所有文件放入同一个文件夹：
- **工资单 (Payslips)** — 从 Crystal Payroll 员工门户下载：https://secure.crystalpayroll.co.nz/
  - 登录后进入 "My Payslips" 下载各期 PDF
  - 脚本识别字段：Gross Earnings、PAYE、KiwiSaver Employee/Employer、ACC Levy
- **租金收入记录** — 租金收入对账单或银行流水
- **租金支出凭证** — 贷款利息单、rates 账单、保险单、维修收据、物业管理费发票
- **ESPP 交易记录** — 如有员工股票购买计划收益，请提供相关对账单
- **PIE 收入凭证** — myIR 年度 PIE 收入汇总 PDF（KiwiSaver 投资收益）或 KiwiSaver 年度对账单（Westpac/ANZ 等）。显示 Gross amount 和 Tax deducted at PIR 两栏。PIE 收入不计入应税收入，但需在 IR3 中申报。

## 输出

每次运行后，必须在对话中输出以下三张完整 Markdown 表格：

### 1. 收入总览
包含：工资总收入、PAYE 已扣税、KiwiSaver 员工/雇主供款、ACC 雇员税、ESPP 收益（如有）、租金收入（含持股比例和全额对比）、租金可抵扣费用、租金净收益/亏损结转、应税总收入。

### 2. 租金支出明细汇总
若为联名持有，显示"全额"和"你的 X% 份额"两列。包含：贷款利息、市政税、保险、维修费、物业管理费、会计费、其他，及合计行。

### 3. 税额计算
包含：应税总收入、所得税（累进税率）、ACC 雇员税（单独列出，注明已含于 PAYE 内）、应缴税额合计、已缴 PAYE（含 ACC）、已缴合计、差额，及退税/补税结论。

**注意**：已缴 PAYE 已包含 ACC levy，不可重复计入已缴合计。

- **报告文件**: `~/Documents/NZTax/YYYY-MM-DD-tax-summary.md`，包含：
  - 收入总览表
  - 租金支出明细
  - IR3 逐字段填写指南
  - 已处理文件清单

## 联名共有房产（Joint Ownership）— 重要

**NZ 税法规定：联名房产的租金收入和费用必须按持股比例分开申报，不能全算一人。**

- 用户（Jia Shao）与太太联名持有出租房产，各 50%
- 每人各自在自己的 IR3 + IR3R 中申报 50% 的收入和费用
- 运行脚本时加 `--rental-share 0.5` 参数，自动只计算用户这一份
- 太太需单独报税，按她自己的税率计算那 50% 的租金收益

验证持股比例：查房产产权证（Certificate of Title），Landonline 或律师可查。

## 注意事项

- 需要设置 `ANTHROPIC_API_KEY` 环境变量
- 报告仅供参考，提交前请核对数字
- 如有 ESPP 收益，需要额外申报（脚本会提取相关数据，但需要人工确认税务处理方式）

---

## ⚠️ 每次运行前必读：核实税率与政策

NZ 税法每年4月1日可能更新。**每次运行此 skill 前，先确认以下信息仍然准确：**

### 1. 个人所得税税率
- 官方来源：https://www.ird.govt.nz/income-tax/income-tax-for-individuals/tax-codes-and-tax-rates-for-individuals/tax-rates-for-individuals
- 当前脚本使用（2025-26，2025年4月1日生效）：
  - 10.5% → $0–$15,600
  - 17.5% → $15,601–$53,500
  - 30% → $53,501–$78,100
  - 33% → $78,101–$180,000
  - 39% → $180,001+
- 若税率有变，更新 `scripts/nz_tax.py` 中的 `TAX_BRACKETS`

### 2. 租金贷款利息抵扣规则
- 官方来源：https://www.ird.govt.nz/property-interest-rules
- 当前规则：2025年4月1日起可抵扣 **100%** 利息（此前有限制）
- 若规则有变，更新脚本中的计算逻辑和报告说明

### 3. 租金亏损环形隔离（Ring-fencing）
- 官方来源：https://www.ird.govt.nz/property/renting-out-residential-property/residential-rental-property-deductions
- 当前规则：租金亏损**不可**抵扣工资等其他收入，只能结转至下年租金收入
- 若规则有变，更新 `calculate_summary()` 中的 `taxable_income` 逻辑

### 4. ESPP / ESS 员工股票计划
- 官方来源：https://www.ird.govt.nz/ess
- 当前规则：折扣收益（市价 - 购买价）在 vesting 日计为雇佣收入，需申报
- 注意：2026年4月起非上市公司有新的递延税务规则，确认是否影响用户情况

### 5. 验证工具
- paye.net.nz（第三方）：https://www.paye.net.nz/calculator/ — 用于交叉验证 PAYE 计算，Advanced settings 可调税率年份
