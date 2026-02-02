"""
Qualitative analysis extraction agent.
Uses LLM's internal knowledge base to assess economic moat, growth, and predictability.
"""

from typing import Any

from agents.extractor_utils import call_llm_with_retry


def extract_qualitative_assessment(ticker: str, company_name: str) -> dict[str, Any]:
    """
    Extracts qualitative assessment (Moat, Growth, Predictability) using LLM's internal knowledge.

    Args:
        ticker: Company ticker symbol
        company_name: Company name

    Returns:
        JSON dictionary with assessment keys or raises exception on failure.
    """
    # 1. Analysis: Generate detailed Cases For/Against/Conclusion
    analysis_prompt = f"""
    You are an expert equity research analyst.
    Analyze the company '{company_name}' (Ticker: {ticker}) based on your broad internal knowledge of the company's business model, industry position, and competitive landscape.

    For each of the three areas below, perform a balanced analysis by weighing the evidence.
    First, consider the "Cases For" (bull case/strengths).
    Second, consider the "Cases Against" (bear case/risks).
    Finally, provide a conclusion based on the weight of the evidence.

    1. Economic Moat: Can the company maintain competitive advantages?
    2. Near-term Growth (Next 5 years): How fast will it grow relative to its historical trend?
    3. Revenue Predictability: How predictable are its future revenues?

    Return a JSON object with the following structure:
    {{
        "economic_moat": {{
             "cases_for": ["point 1", "point 2"],
             "cases_against": ["point 1", "point 2"],
             "conclusion": "Final reasoning"
        }},
        "near_term_growth": {{
             "cases_for": ["point 1", "point 2"],
             "cases_against": ["point 1", "point 2"],
             "conclusion": "Final reasoning"
        }},
        "revenue_predictability": {{
             "cases_for": ["point 1", "point 2"],
             "cases_against": ["point 1", "point 2"],
             "conclusion": "Final reasoning"
        }}
    }}

    Rules:
    - Be objective and critical.
    - Return ONLY valid JSON.
    """

    analysis_raw = call_llm_with_retry(analysis_prompt, temperature=0.7)

    # Convert structured response to flat strings
    def format_analysis_section(data: Any) -> str:
        if isinstance(data, str):
            return data
        if not isinstance(data, dict):
            return str(data)

        lines = []

        # Handle cases_for
        cases_for = data.get("cases_for", [])
        if isinstance(cases_for, list) and cases_for:
            lines.append("Cases For:")
            lines.extend([f"• {item}" for item in cases_for])
        elif isinstance(cases_for, str):
            lines.append(f"Cases For:\n{cases_for}")

        # Handle cases_against
        cases_against = data.get("cases_against", [])
        if isinstance(cases_against, list) and cases_against:
            lines.append("\nCases Against:")
            lines.extend([f"• {item}" for item in cases_against])
        elif isinstance(cases_against, str):
            lines.append(f"\nCases Against:\n{cases_against}")

        # Handle conclusion
        conclusion = data.get("conclusion", "")
        if conclusion:
            lines.append(f"\nConclusion: {conclusion}")

        return "\n".join(lines)

    analysis_result = {}
    analysis_result["economic_moat_rationale"] = format_analysis_section(
        analysis_raw.get("economic_moat", "No rationale.")
    )
    analysis_result["near_term_growth_rationale"] = format_analysis_section(
        analysis_raw.get("near_term_growth", "No rationale.")
    )
    analysis_result["revenue_predictability_rationale"] = format_analysis_section(
        analysis_raw.get("revenue_predictability", "No rationale.")
    )

    # 2. Labeling: Assign labels based strictly on the generated analysis
    moat_rationale = analysis_result["economic_moat_rationale"]
    growth_rationale = analysis_result["near_term_growth_rationale"]
    predictability_rationale = analysis_result["revenue_predictability_rationale"]

    labeling_prompt = f"""
    You are a strict grading assistant. Based ONLY on the provided expert analysis below, assign the correct labels.

    ---
    Economic Moat Analysis:
    {moat_rationale}

    Near-term Growth Analysis:
    {growth_rationale}

    Revenue Predictability Analysis:
    {predictability_rationale}
    ---

    Task:
    1. Economic Moat Label: Choose ["Wide", "Narrow", "None"].
       - Wide: A company with a wide moat possesses structural advantages so powerful they are expected to fend off competitors and sustain excess Return on Invested Capital (ROIC) for 20 years or more. These firms often dominate their industry through massive network effects, high switching costs, or irreplaceable intangible assets that make entry for competitors nearly impossible.
       - Narrow: A narrow moat indicates a company has a clear competitive advantage, but one that is likely to face erosion or increased competition within a 10-to-20-year horizon. While the business is currently outperforming its cost of capital, the "moat" is not deep enough to guarantee long-term protection against aggressive rivals or rapid technological shifts.
       - None: Companies with no moat operate in highly commoditized or intensely competitive industries where they have no sustainable advantage over their peers. These businesses are "price takers" rather than "price makers," and any short-term excess profits are quickly competed away, eventually dragging returns down toward the company WACC.
       - If you know what Morningstar rates the company as, then use that.

    2. Near-term Growth Label: Choose ["Faster", "Steady", "Slower"] (relative to historical).

    3. Revenue Predictability Label: Choose ["High", "Mid", "Low"].
       - High: These companies typically rely on long-term recurring revenue streams, such as multi-year SaaS subscriptions or essential utility services. Because the vast majority of next year income is already "locked in" by contract or necessity, management can forecast performance with extremely high precision and low variance.
       - Mid: This category often includes businesses with high customer loyalty but shorter contract terms or a mix of recurring and transactional sales. While there is a reliable "base" of repeat business, the total revenue is still sensitive to broader economic cycles or moderate changes in customer churn, leading to occasional surprises in quarterly results.
       - Low: These businesses are primarily transactional or project-based, requiring the sales team to "kill what they eat" every single month. Companies in highly cyclical industries, like luxury retail or construction, fall here because their revenue is heavily dependent on external factors like consumer sentiment or fluctuating interest rates.

    Return a JSON object with the following structure:
    {{
        "economic_moat_label": "...",
        "near_term_growth_label": "...",
        "revenue_predictability_label": "..."
    }}

    Rules:
    - Be critical. If a moat argument is weak or eroding, label it "None".
    - Base your decision ONLY on the text provided above.
    - Return ONLY valid JSON.
    """

    label_result = call_llm_with_retry(
        labeling_prompt, temperature=0.0
    )  # Low temp for deterministic labeling

    # Combine results
    final_result = {**analysis_result, **label_result}

    return final_result
