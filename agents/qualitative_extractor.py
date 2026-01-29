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
        "economic_moat_rationale": "String with newlines:\\nCases For: [Points]\\nCases Against: [Points]\\nConclusion: [Final reasoning]",
        "near_term_growth_rationale": "String with newlines:\\nCases For: [Points]\\nCases Against: [Points]\\nConclusion: [Final reasoning]",
        "revenue_predictability_rationale": "String with newlines:\\nCases For: [Points]\\nCases Against: [Points]\\nConclusion: [Final reasoning]"
    }}

    Rules:
    - Be objective and critical.
    - The rationales must explicitly follow the 'Cases For / Cases Against / Conclusion' format.
    - Return ONLY valid JSON.
    """

    analysis_result = call_llm_with_retry(analysis_prompt, temperature=0.7)

    # 2. Labeling: Assign labels based strictly on the generated analysis
    # Use .get() to avoid KeyErrors if the first step fails to return a key
    moat_rationale = analysis_result.get("economic_moat_rationale", "No rationale provided.")
    growth_rationale = analysis_result.get("near_term_growth_rationale", "No rationale provided.")
    predictability_rationale = analysis_result.get(
        "revenue_predictability_rationale", "No rationale provided."
    )

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
       - Wide: Strong, durable competitive advantages (network effects, high switching costs).
       - Narrow: Some advantages but potentially fleeting or minor.
       - None: No sustainable advantage.

    2. Near-term Growth Label: Choose ["Faster", "Steady", "Slower"] (relative to historical).

    3. Revenue Predictability Label: Choose ["High", "Mid", "Low"].
       - High: Recurring revenue, long-term contracts, backlog.
       - Low: Project-based, cyclical, volatile.

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

    # Post-process rationales to ensure they are strings (DB compatibility)
    def format_rationale(value):
        if isinstance(value, list):
            # Join with newlines and bullet points
            return "\n".join([f"• {item}" for item in value])
        return value

    keys_to_process = [
        "economic_moat_rationale",
        "near_term_growth_rationale",
        "revenue_predictability_rationale",
    ]

    for key in keys_to_process:
        if key in final_result:
            final_result[key] = format_rationale(final_result[key])

    return final_result
