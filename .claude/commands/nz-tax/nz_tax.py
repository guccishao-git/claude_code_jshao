#!/usr/bin/env /Users/jason.shao/Documents/GitHub1/claude_code_jshao/.venv/bin/python3
"""NZ Tax Filing Assistant — IR3 + IR3R Helper (PAYE + Rental + ESPP)"""

import sys
import json
import base64
from pathlib import Path
from datetime import datetime
import anthropic

TAX_YEAR = "2025-26"
OUTPUT_DIR = Path.home() / "Documents" / "NZTax"

# NZ progressive tax rates effective 1 April 2025 (2025-26 year)
# Source: https://www.ird.govt.nz/income-tax/.../tax-rates-for-individuals
TAX_BRACKETS = [
    (15600,  0.105),
    (53500,  0.175),
    (78100,  0.30),
    (180000, 0.33),
    (float("inf"), 0.39),
]

RENTAL_EXPENSE_TYPES = [
    "mortgage_interest",
    "rates",
    "insurance",
    "repairs",
    "property_management",
    "accounting_fees",
    "other",
]


def calculate_tax(taxable_income: float) -> float:
    tax, prev = 0.0, 0
    for threshold, rate in TAX_BRACKETS:
        if taxable_income <= prev:
            break
        tax += (min(taxable_income, threshold) - prev) * rate
        prev = threshold
    return tax


def encode_pdf(pdf_path: Path) -> str:
    with open(pdf_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


EXTRACTION_PROMPT = """Analyze this NZ payroll/tax document and return ONLY a JSON object (no markdown, no explanation).

Document type rules:
- "payslip": any Crystal Payroll doc — payslip, Earning Certificate, Payslip Summary, PAYE Deduction, KiwiSaver History, Deduction History
- "espp": Employee Share Purchase Plan / Share Scheme statement (share purchases or vesting)
- "rental_income": rental income statement or record
- "rental_expense": invoice or receipt for rental property costs (mortgage interest, rates, insurance, repairs, property management, accounting fees)
- "pie_income": PIE (Portfolio Investment Entity) income statement — KiwiSaver annual return, myIR PIE income summary, or PIE income certificate showing gross PIE income and tax deducted at PIR
- "other": everything else

For payslip documents, extract ANNUAL totals (not per-period):
- "Gross Earnings" / "Total Gross" → gross_income
- "PAYE" / "PAYE/WT" / "Income Tax" → paye_withheld
  NOTE: ACC/E.L. often appears as a sub-item under PAYE/WT (e.g. "included E.L. (ACC) $2,527.23").
  Always extract the full PAYE/WT total line as paye_withheld — do NOT subtract the ACC sub-item.
  The ACC amount is already included in the PAYE/WT figure.
- "KiwiSaver Employee" → kiwisaver_employee
- "KiwiSaver Company/Employer" → kiwisaver_employer
- "ACC" / "E.L." / "included E.L. (ACC)" / "Earners Levy" → acc_levy

For rental_expense documents (rates invoices, bills, receipts):
- Extract the AMOUNT ACTUALLY DUE for THIS specific invoice only
- For NZ council rates (Auckland Council etc): look for "Amount Due", "Instalment Amount", "Payment Due", "This Instalment" — this is the quarterly amount (e.g. ~$769), NOT the annual total shown on the bill (e.g. $3,077)
- Do NOT extract the full year annual rates total

For property management statements (e.g. from Regis Property Management, Barfoot, etc.):
- Classify as "rental_income"
- Extract gross rental income → rental_income
- Extract total property management fees (excl. GST) → property_mgmt_fees
- Extract total GST on those fees → property_mgmt_gst
- Do NOT extract repair/invoice pass-through amounts (those come from separate invoice PDFs)

For pie_income documents (myIR PIE summary, KiwiSaver annual statement):
- Extract total gross PIE income → pie_gross
- Extract total tax deducted at PIR → pie_tax_withheld

JSON structure (all amounts NZD, use null if not found):
{"document_type":"...","description":"one line","data":{"gross_income":null,"paye_withheld":null,"kiwisaver_employee":null,"kiwisaver_employer":null,"acc_levy":null,"espp_benefit":null,"espp_tax_withheld":null,"espp_market_value":null,"espp_purchase_price":null,"rental_income":null,"property_address":null,"property_mgmt_fees":null,"property_mgmt_gst":null,"expense_type":null,"amount":null,"period":null,"pie_gross":null,"pie_tax_withheld":null}}"""


def extract_data_from_pdf(client: anthropic.Anthropic, pdf_path: Path) -> dict:
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": encode_pdf(pdf_path),
                    },
                },
                {"type": "text", "text": EXTRACTION_PROMPT},
            ],
        }],
    )
    text = message.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}") + 1
        if start != -1 and end:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return {"document_type": "other", "description": pdf_path.name, "data": {}}


def process_pdfs(folder_path: Path) -> dict:
    client = anthropic.Anthropic()
    results = {
        "payslips": [],
        "rental_income": [],
        "rental_expenses": [],
        "espp": [],
        "pie_income": [],
        "other": [],
    }

    pdf_files = sorted(folder_path.glob("*.[pP][dD][fF]"))
    if not pdf_files:
        print(f"错误: 在 {folder_path} 中找不到 PDF 文件")
        sys.exit(1)

    print(f"找到 {len(pdf_files)} 个 PDF 文件，开始处理...\n")
    for pdf_path in pdf_files:
        print(f"  处理: {pdf_path.name}...")
        extracted = extract_data_from_pdf(client, pdf_path)
        extracted["filename"] = pdf_path.name
        doc_type = extracted.get("document_type", "other")
        # Map singular API return values to plural bucket keys
        bucket_map = {
            "payslip": "payslips",
            "rental_income": "rental_income",
            "rental_expense": "rental_expenses",
            "espp": "espp",
            "pie_income": "pie_income",
        }
        bucket = bucket_map.get(doc_type, "other")
        results[bucket].append(extracted)

    return results


def best_payslip_value(records: list, key: str) -> float:
    """Pick the single largest non-zero value across payroll docs to avoid double-counting.
    Annual summary docs (Earning Certificate etc.) contain full-year totals already,
    so summing multiple docs would multiply the figure."""
    values = [r["data"].get(key) or 0 for r in records]
    return max(values) if values else 0.0


def calculate_summary(data: dict, rental_share: float = 1.0, mortgage_interest_full: float = 0.0,
                      pie_gross_manual: float = 0.0, pie_tax_manual: float = 0.0) -> dict:
    gross_salary = best_payslip_value(data["payslips"], "gross_income")
    paye_withheld = best_payslip_value(data["payslips"], "paye_withheld")
    kiwisaver_employee = best_payslip_value(data["payslips"], "kiwisaver_employee")
    kiwisaver_employer = best_payslip_value(data["payslips"], "kiwisaver_employer")
    acc_levy = best_payslip_value(data["payslips"], "acc_levy")

    # ESPP: taxable benefit is market_value - purchase_price (or use espp_benefit if pre-calculated)
    espp_benefit = 0.0
    espp_tax_withheld = 0.0
    for e in data["espp"]:
        d = e["data"]
        if d.get("espp_benefit"):
            espp_benefit += d["espp_benefit"]
        elif d.get("espp_market_value") and d.get("espp_purchase_price"):
            espp_benefit += d["espp_market_value"] - d["espp_purchase_price"]
        espp_tax_withheld += d.get("espp_tax_withheld") or 0

    pie_gross = sum(r["data"].get("pie_gross") or 0 for r in data.get("pie_income", [])) + pie_gross_manual
    pie_tax_withheld = sum(r["data"].get("pie_tax_withheld") or 0 for r in data.get("pie_income", [])) + pie_tax_manual

    raw_rental_income = sum(r["data"].get("rental_income") or 0 for r in data["rental_income"])
    raw_mgmt_fees = sum((r["data"].get("property_mgmt_fees") or 0) + (r["data"].get("property_mgmt_gst") or 0)
                        for r in data["rental_income"])

    # Normalize expense type variants returned by the model
    EXPENSE_TYPE_MAP = {
        "council_rates": "rates",
        "council rates": "rates",
        "body_corporate_levy": "other",
        "body corporate": "other",
        "body_corporate": "other",
        "strata_levy": "other",
        "appliance servicing": "repairs",
        "general maintenance": "repairs",
        "repairs and maintenance": "repairs",
    }

    raw_expenses = {k: 0.0 for k in RENTAL_EXPENSE_TYPES}
    for e in data["rental_expenses"]:
        raw_type = (e["data"].get("expense_type") or "other").lower()
        exp_type = EXPENSE_TYPE_MAP.get(raw_type, raw_type)
        amount = e["data"].get("amount") or 0
        raw_expenses[exp_type if exp_type in raw_expenses else "other"] += amount
    # Add property management fees from rental income statements (full amounts)
    raw_expenses_full = dict(raw_expenses)
    raw_expenses_full["property_management"] += raw_mgmt_fees
    raw_expenses_full["mortgage_interest"] += mortgage_interest_full

    # Apply ownership share (e.g. 0.5 for 50/50 joint ownership)
    total_rental_income = raw_rental_income * rental_share
    expenses = {k: v * rental_share for k, v in raw_expenses.items()}
    # Property management fees + GST from rental income statements
    expenses["property_management"] += raw_mgmt_fees * rental_share
    # Add manually provided mortgage interest (also split by ownership share)
    expenses["mortgage_interest"] += mortgage_interest_full * rental_share
    total_expenses = sum(expenses.values())
    rental_net = total_rental_income - total_expenses

    # Ring-fencing: rental losses cannot offset salary/ESPP income (IRD rule).
    # Only add rental profit to taxable income; carry losses forward separately.
    taxable_income = gross_salary + espp_benefit + max(rental_net, 0)
    income_tax = calculate_tax(taxable_income)
    # ACC earners' levy is withheld alongside PAYE and is part of total tax obligation
    tax_liability = income_tax + acc_levy

    # paye_withheld already includes ACC levy — do not add again
    total_tax_paid = paye_withheld + espp_tax_withheld
    tax_difference = total_tax_paid - tax_liability  # positive = refund

    return {
        "gross_salary": gross_salary,
        "paye_withheld": paye_withheld,
        "kiwisaver_employee": kiwisaver_employee,
        "kiwisaver_employer": kiwisaver_employer,
        "acc_levy": acc_levy,
        "espp_benefit": espp_benefit,
        "espp_tax_withheld": espp_tax_withheld,
        "rental_share": rental_share,
        "raw_rental_income": raw_rental_income,
        "rental_income": total_rental_income,
        "raw_rental_expenses": raw_expenses_full,
        "rental_expenses": expenses,
        "total_rental_expenses": total_expenses,
        "rental_net": rental_net,
        "rental_loss_carried_forward": abs(min(rental_net, 0)),
        "taxable_income": taxable_income,
        "income_tax": income_tax,
        "tax_liability": tax_liability,
        "total_tax_paid": total_tax_paid,
        "tax_difference": tax_difference,
        "pie_gross": pie_gross,
        "pie_tax_withheld": pie_tax_withheld,
    }


def fmt(n: float) -> str:
    return f"${n:,.2f}"


def generate_report(summary: dict, data: dict) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    diff = summary["tax_difference"]
    conclusion = f"**退税 {fmt(diff)}**" if diff >= 0 else f"**补税 {fmt(abs(diff))}**"
    conclusion_detail = (
        f"IRD 将退还给你约 {fmt(diff)}"
        if diff >= 0
        else f"你需要向 IRD 补缴约 {fmt(abs(diff))}"
    )
    share_note = f"（租金按 {summary['rental_share']*100:.0f}% 持股比例计算）" if summary["rental_share"] < 1.0 else ""
    share = summary["rental_share"]
    exp = summary["rental_expenses"]
    raw_exp = summary["raw_rental_expenses"]
    lines = [
        f"# NZ 税务总结报告 — {TAX_YEAR}",
        f"*生成日期: {today}{share_note}*",
        "",
        "---",
        "",
        "## 一、收入总览",
        "",
        "| 项目 | 金额 (NZD) | 说明 |",
        "|------|-----------|------|",
        f"| 工资总收入 (Gross Salary) | {fmt(summary['gross_salary'])} | 税前工资合计 |",
        f"| PAYE 已扣税 | {fmt(summary['paye_withheld'])} | 雇主代扣，已缴 IRD |",
        f"| KiwiSaver 员工供款 | {fmt(summary['kiwisaver_employee'])} | 从工资扣除，不计税 |",
        f"| KiwiSaver 雇主供款 | {fmt(summary['kiwisaver_employer'])} | 雇主额外缴纳 |",
        f"| ACC 雇员税 (E.L.) | {fmt(summary['acc_levy'])} | 从工资扣除 |",
        f"| ESPP 折扣收益（应税） | {fmt(summary['espp_benefit'])} | 视为雇佣收入 |",
        f"| 租金收入（{share*100:.0f}%份额） | {fmt(summary['rental_income'])} | 全年全额 {fmt(summary['raw_rental_income'])} |",
        f"| 租金可抵扣费用（{share*100:.0f}%份额） | {fmt(summary['total_rental_expenses'])} | |",
        f"| 租金净收益 | {fmt(max(summary['rental_net'], 0))} | 亏损不可抵扣工资 |",
    ]
    if summary["rental_loss_carried_forward"] > 0:
        lines.append(f"| 租金亏损（结转下年） | ({fmt(summary['rental_loss_carried_forward'])}) | Ring-fencing，不抵当年工资 |")
    lines += [
        f"| **应税总收入** | **{fmt(summary['taxable_income'])}** | 工资 + ESPP + 租金净收益 |",
        "",
        "---",
        "",
        "## 二、租金支出明细",
        "",
    ]
    if share < 1.0:
        lines += [
            f"| 费用类型 | 全额 (NZD) | 你的份额 {share*100:.0f}% (NZD) | 备注 |",
            "|---------|-----------|-----------|------|",
            f"| 贷款利息 (Mortgage Interest) | {fmt(raw_exp['mortgage_interest'])} | {fmt(exp['mortgage_interest'])} | 2025年4月起100%可抵扣 |",
            f"| 市政税 (Rates) | {fmt(raw_exp['rates'])} | {fmt(exp['rates'])} | |",
            f"| 保险 (Insurance) | {fmt(raw_exp['insurance'])} | {fmt(exp['insurance'])} | |",
            f"| 维修费 (Repairs & Maintenance) | {fmt(raw_exp['repairs'])} | {fmt(exp['repairs'])} | 注意：装修/改建不可抵扣 |",
            f"| 物业管理费 (Property Management) | {fmt(raw_exp['property_management'])} | {fmt(exp['property_management'])} | |",
            f"| 会计/税务费用 (Accounting Fees) | {fmt(raw_exp['accounting_fees'])} | {fmt(exp['accounting_fees'])} | |",
            f"| 其他 (Other) | {fmt(raw_exp['other'])} | {fmt(exp['other'])} | |",
            f"| **合计** | **{fmt(sum(raw_exp.values()))}** | **{fmt(summary['total_rental_expenses'])}** | |",
        ]
    else:
        lines += [
            "| 费用类型 | 金额 (NZD) | 备注 |",
            "|---------|-----------|------|",
            f"| 贷款利息 (Mortgage Interest) | {fmt(exp['mortgage_interest'])} | 2025年4月起100%可抵扣 |",
            f"| 市政税 (Rates) | {fmt(exp['rates'])} | |",
            f"| 保险 (Insurance) | {fmt(exp['insurance'])} | |",
            f"| 维修费 (Repairs & Maintenance) | {fmt(exp['repairs'])} | 注意：装修/改建不可抵扣 |",
            f"| 物业管理费 (Property Management) | {fmt(exp['property_management'])} | |",
            f"| 会计/税务费用 (Accounting Fees) | {fmt(exp['accounting_fees'])} | |",
            f"| 其他 (Other) | {fmt(exp['other'])} | |",
            f"| **合计** | **{fmt(summary['total_rental_expenses'])}** | |",
        ]
    lines += [
        "",
        "> ⚠️ **不可抵扣**: 贷款本金还款、装修改建、房产购买/出售中介费、土地/建筑物折旧、个人劳动报酬",
        "",
        "---",
        "",
        "## 三、ESPP 员工股票计划",
        "",
    ]
    if summary["espp_benefit"] > 0:
        lines += [
            "| 项目 | 金额 (NZD) |",
            "|------|-----------|",
            f"| 应税折扣收益（市价 - 购买价） | {fmt(summary['espp_benefit'])} |",
            f"| 雇主已代扣税款 | {fmt(summary['espp_tax_withheld'])} |",
            "",
            "> ESPP 折扣收益按 vesting/购买日市场价计算，视为雇佣收入。",
            "> 若雇主未代扣，需在 IR3 中自行申报。",
        ]
    else:
        lines.append("*本年度未检测到 ESPP 文件，如有请补充。*")
    lines += [
        "",
        "---",
        "",
        "## 四、PIE 投资收入（KiwiSaver）",
        "",
    ]
    if summary["pie_gross"] > 0:
        lines += [
            "| 项目 | 金额 (NZD) |",
            "|------|-----------|",
            f"| PIE 总收入（Gross PIE Income） | {fmt(summary['pie_gross'])} |",
            f"| 已扣 PIR 税（Tax Deducted at PIR） | {fmt(summary['pie_tax_withheld'])} |",
            "",
            "> PIE 收入按 PIR 税率最终预扣，**不计入个人应税收入**，无需再缴进所得税。",
            "> 在 IR3 的「Portfolio investment entity (PIE) income」栏填写以上数据。",
            "> 若 myIR 已自动预填，核对数字一致即可。",
        ]
    else:
        lines.append("*本年度未检测到 PIE 收入文件，如有请补充 myIR 年度 PIE 汇总 PDF 或 KiwiSaver 年度对账单。*")
    lines += [
        "",
        "---",
        "",
        "## 五、税额计算",
        "",
        "**2025-26 税率**（2025年4月1日生效）:",
        "| 收入区间 | 税率 |",
        "|---------|------|",
        "| $0 – $15,600 | 10.5% |",
        "| $15,601 – $53,500 | 17.5% |",
        "| $53,501 – $78,100 | 30% |",
        "| $78,101 – $180,000 | 33% |",
        "| $180,001+ | 39% |",
        "",
        "| 计算项 | 金额 (NZD) | 说明 |",
        "|------|-----------|------|",
        f"| 应税总收入 | {fmt(summary['taxable_income'])} | |",
        f"| 　所得税 (Income Tax) | {fmt(summary['income_tax'])} | 累进税率计算 |",
        f"| 　ACC 雇员税 | {fmt(summary['acc_levy'])} | 随 PAYE 代扣缴 IRD |",
        f"| **应缴税额合计** | **{fmt(summary['tax_liability'])}** | |",
        f"| 已缴 PAYE（含 ACC） | {fmt(summary['paye_withheld'])} | 雇主代扣 |",
        f"| 已缴 ESPP 代扣税 | {fmt(summary['espp_tax_withheld'])} | |",
        f"| 已缴合计 | {fmt(summary['total_tax_paid'])} | |",
        f"| **差额** | **{fmt(summary['tax_difference'])}** | 正数=退税，负数=补税 |",
        "",
        f"### 结论：{conclusion}",
        "",
        conclusion_detail,
        "",
        "---",
        "",
        "## 六、IR3 / IR3R 填写指南",
        "",
        "**IR3（个人税表）关键字段：**",
        "",
        "| 字段 | 填写值 | 说明 |",
        "|-----|-------|------|",
        f"| 工资收入 | {fmt(summary['gross_salary'])} | 税前工资总额 |",
        f"| PAYE 已扣税 | {fmt(summary['paye_withheld'])} | 工资单合计 |",
        f"| ESS 收益 | {fmt(summary['espp_benefit'])} | 若雇主已申报可核对 |",
        f"| 租金净收益 | {fmt(max(summary['rental_net'], 0))} | 亏损填 0，亏损额结转 |",
        f"| PIE 总收入 | {fmt(summary['pie_gross'])} | myIR「PIE income」栏（通常自动预填） |",
        f"| PIR 已扣税 | {fmt(summary['pie_tax_withheld'])} | 核对 myIR 自动填入值 |",
        "",
        "**IR3R（租金收入附表）关键字段：**",
        "",
        "| 字段 | 填写值 |",
        "|-----|-------|",
        f"| 租金总收入 | {fmt(summary['rental_income'])} |",
        f"| 贷款利息 | {fmt(exp['mortgage_interest'])} |",
        f"| 市政税 Rates | {fmt(exp['rates'])} |",
        f"| 保险费 | {fmt(exp['insurance'])} |",
        f"| 维修费 | {fmt(exp['repairs'])} |",
        f"| 物业管理费 | {fmt(exp['property_management'])} |",
        f"| 会计费 | {fmt(exp['accounting_fees'])} |",
        f"| 其他费用 | {fmt(exp['other'])} |",
        f"| 总费用 | {fmt(summary['total_rental_expenses'])} |",
        f"| 净收益/亏损 | {fmt(summary['rental_net'])} |",
        "",
        "---",
        "",
        "## 七、处理的文件清单",
        "",
    ]

    def file_section(title, records, fields):
        if not records:
            return []
        section = [f"### {title}"]
        for r in records:
            d = r["data"]
            parts = [f"`{r['filename']}`"]
            for label, key in fields:
                val = d.get(key)
                if val is not None:
                    parts.append(f"{label}: {fmt(val) if isinstance(val, (int, float)) else val}")
            section.append("- " + " — ".join(parts))
        section.append("")
        return section

    lines += file_section("工资单", data["payslips"], [
        ("期间", "period"), ("税前收入", "gross_income"), ("PAYE", "paye_withheld"),
        ("KiwiSaver员工", "kiwisaver_employee"), ("KiwiSaver雇主", "kiwisaver_employer"),
        ("ACC", "acc_levy"),
    ])
    lines += file_section("ESPP 对账单", data["espp"], [
        ("期间", "period"), ("折扣收益", "espp_benefit"), ("代扣税", "espp_tax_withheld"),
        ("市价", "espp_market_value"), ("购入价", "espp_purchase_price"),
    ])
    lines += file_section("租金收入记录", data["rental_income"], [
        ("期间", "period"), ("租金收入", "rental_income"),
        ("物业管理费(excl.GST)", "property_mgmt_fees"), ("管理费GST", "property_mgmt_gst"),
        ("物业地址", "property_address"),
    ])
    lines += file_section("租金支出凭证", data["rental_expenses"], [
        ("费用类型", "expense_type"), ("金额", "amount"), ("期间", "period"),
    ])
    lines += file_section("PIE 收入凭证", data.get("pie_income", []), [
        ("期间", "period"), ("PIE 总收入", "pie_gross"), ("PIR 已扣税", "pie_tax_withheld"),
    ])

    if data["other"]:
        lines.append("### 其他文件（未分类）")
        for o in data["other"]:
            lines.append(f"- `{o['filename']}` — {o.get('description', '未识别')}")
        lines.append("")

    lines += [
        "---",
        "",
        "> **免责声明**: 本报告由 AI 生成，仅供参考，不构成税务建议。提交前请核对所有数字。",
        "> **验证税额**: 可用 [paye.net.nz](https://www.paye.net.nz/calculator/) 交叉核对 PAYE 计算（Advanced settings 可调税率年份）。",
        "> **官方资料**: [IRD 租金收入](https://www.ird.govt.nz/property/renting-out-residential-property) | "
        "[ESS 税务](https://www.ird.govt.nz/ess) | "
        "[个人税率](https://www.ird.govt.nz/income-tax/income-tax-for-individuals/tax-codes-and-tax-rates-for-individuals/tax-rates-for-individuals)",
        "",
    ]

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="NZ Tax Filing Assistant")
    parser.add_argument("folder", help="PDF 文件夹路径")
    parser.add_argument("--rental-share", type=float, default=1.0,
                        help="你的租金持股比例，如联名共有各50%%填 0.5（默认 1.0）")
    parser.add_argument("--mortgage-interest", type=float, default=0.0,
                        help="全年贷款利息总额（NZD），脚本会按 --rental-share 自动分摊")
    parser.add_argument("--pie-gross", type=float, default=0.0,
                        help="PIE 总收入（NZD），无 PDF 时手动输入 myIR 上的 Gross amount")
    parser.add_argument("--pie-tax-withheld", type=float, default=0.0,
                        help="PIR 已扣税（NZD），无 PDF 时手动输入 myIR 上的 Tax deducted")
    args = parser.parse_args()

    folder_path = Path(args.folder).expanduser().resolve()
    if not folder_path.is_dir():
        print(f"错误: 找不到文件夹 {folder_path}")
        sys.exit(1)

    rental_share = args.rental_share

    print(f"\nNZ 报税助手 — {TAX_YEAR}")
    print("=" * 40)

    if not (0 < rental_share <= 1.0):
        print("错误: --rental-share 必须在 0 到 1 之间，例如 0.5")
        sys.exit(1)
    if rental_share < 1.0:
        print(f"  租金持股比例: {rental_share*100:.0f}%（联名共有）")
    if args.mortgage_interest > 0:
        print(f"  贷款利息（手动）: NZD ${args.mortgage_interest:,.2f}（全年），你的份额: ${args.mortgage_interest * rental_share:,.2f}")
    if args.pie_gross > 0:
        print(f"  PIE 收入（手动）: Gross ${args.pie_gross:,.2f}，PIR 已扣税 ${args.pie_tax_withheld:,.2f}")

    extracted = process_pdfs(folder_path)
    summary = calculate_summary(extracted, rental_share, args.mortgage_interest,
                                args.pie_gross, args.pie_tax_withheld)
    report = generate_report(summary, extracted)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = OUTPUT_DIR / f"{today}-tax-summary.md"
    output_path.write_text(report, encoding="utf-8")

    diff = summary["tax_difference"]
    exp = summary["rental_expenses"]
    raw_exp = summary["raw_rental_expenses"]
    share = summary["rental_share"]

    def row(label, value, note=""):
        note_str = f"  {note}" if note else ""
        print(f"  {label:<34} {value:>14}{note_str}")

    def divider(char="─", width=60):
        print("  " + char * width)

    print(f"\n处理完成！")
    print()

    # ── 一、收入总览 ──────────────────────────────────────
    print("  ┌─ 一、收入总览 " + "─" * 44 + "┐")
    row("工资总收入 (Gross Salary)", fmt(summary['gross_salary']))
    row("PAYE 已扣税", fmt(summary['paye_withheld']), "雇主代扣")
    row("KiwiSaver 员工供款", fmt(summary['kiwisaver_employee']), "从工资扣除")
    row("KiwiSaver 雇主供款", fmt(summary['kiwisaver_employer']), "雇主额外缴纳")
    row("ACC 雇员税 (E.L.)", fmt(summary['acc_levy']), "从工资扣除")
    if summary['espp_benefit'] > 0:
        row("ESPP 折扣收益（应税）", fmt(summary['espp_benefit']), "视为雇佣收入")
    divider("·")
    if share < 1.0:
        row(f"租金收入（{share*100:.0f}%份额）", fmt(summary['rental_income']),
            f"全年全额 {fmt(summary['raw_rental_income'])}")
        row(f"租金可抵扣费用（{share*100:.0f}%份额）", f"-{fmt(summary['total_rental_expenses'])}")
    else:
        row("租金收入", fmt(summary['rental_income']))
        row("租金可抵扣费用", f"-{fmt(summary['total_rental_expenses'])}")
    row("租金净收益", fmt(max(summary['rental_net'], 0)))
    if summary['rental_loss_carried_forward'] > 0:
        row("租金亏损（结转下年）", f"({fmt(summary['rental_loss_carried_forward'])})", "Ring-fencing")
    divider()
    row("应税总收入", fmt(summary['taxable_income']))
    print("  └" + "─" * 59 + "┘")
    print()

    # ── 二、租金支出明细 ──────────────────────────────────
    if share < 1.0:
        print(f"  ┌─ 二、租金支出明细（全额 → 你的{share*100:.0f}%份额）" + "─" * 21 + "┐")
        def rent_row(label, full, share_val):
            print(f"  {label:<30} {fmt(full):>12}  →  {fmt(share_val):>12}")
        rent_row("贷款利息 (Mortgage Interest)", raw_exp['mortgage_interest'], exp['mortgage_interest'])
        rent_row("市政税 (Rates)", raw_exp['rates'], exp['rates'])
        rent_row("保险 (Insurance)", raw_exp['insurance'], exp['insurance'])
        rent_row("维修费 (Repairs)", raw_exp['repairs'], exp['repairs'])
        rent_row("物业管理费", raw_exp['property_management'], exp['property_management'])
        rent_row("会计/税务费用", raw_exp['accounting_fees'], exp['accounting_fees'])
        rent_row("其他 (Other)", raw_exp['other'], exp['other'])
        divider()
        rent_row("合计", sum(raw_exp.values()), summary['total_rental_expenses'])
    else:
        print("  ┌─ 二、租金支出明细 " + "─" * 40 + "┐")
        row("贷款利息 (Mortgage Interest)", fmt(exp['mortgage_interest']))
        row("市政税 (Rates)", fmt(exp['rates']))
        row("保险 (Insurance)", fmt(exp['insurance']))
        row("维修费 (Repairs)", fmt(exp['repairs']))
        row("物业管理费", fmt(exp['property_management']))
        row("会计/税务费用", fmt(exp['accounting_fees']))
        row("其他 (Other)", fmt(exp['other']))
        divider()
        row("合计", fmt(summary['total_rental_expenses']))
    print("  └" + "─" * 59 + "┘")
    print()

    # ── 三、税额计算 ──────────────────────────────────────
    print("  ┌─ 三、税额计算 " + "─" * 44 + "┐")
    row("应税总收入", fmt(summary['taxable_income']))
    row("  └ 所得税 (Income Tax)", fmt(summary['income_tax']))
    row("  └ ACC 雇员税", fmt(summary['acc_levy']))
    row("应缴税额合计", fmt(summary['tax_liability']))
    divider("·")
    row("已缴 PAYE（含 ACC）", fmt(summary['paye_withheld']), "含 ACC $" + f"{summary['acc_levy']:,.2f}")
    if summary['espp_tax_withheld'] > 0:
        row("已缴 ESPP 代扣税", fmt(summary['espp_tax_withheld']))
    row("已缴合计", fmt(summary['total_tax_paid']))
    divider()
    if diff >= 0:
        print(f"\n  ★  预计退税: NZD {fmt(diff)}  ★")
    else:
        print(f"\n  ▶  需要补税: NZD {fmt(abs(diff))}  ◀")
    print("  └" + "─" * 59 + "┘")
    print()

    # ── 文件清单 ──────────────────────────────────────────
    print("  ┌─ 处理文件清单 " + "─" * 44 + "┐")
    for bucket, label in [("payslips","工资单"), ("rental_income","租金收入"), ("rental_expenses","租金支出"), ("espp","ESPP"), ("other","其他")]:
        if extracted[bucket]:
            print(f"  【{label}】")
            for r in extracted[bucket]:
                d = r["data"]
                details = []
                for k, zh in [("gross_income","税前"), ("paye_withheld","PAYE"), ("rental_income","租金"),
                               ("amount","金额"), ("expense_type","类型"), ("period","期间"),
                               ("property_mgmt_fees","管理费"), ("espp_benefit","收益")]:
                    v = d.get(k)
                    if v is not None:
                        details.append(f"{zh}: {fmt(v) if isinstance(v,(int,float)) else v}")
                detail_str = "  |  ".join(details) if details else "无详细数据"
                print(f"    · {r['filename']}")
                print(f"      {detail_str}")
    print("  └" + "─" * 59 + "┘")
    print(f"\n详细报告: {output_path}")


if __name__ == "__main__":
    main()
