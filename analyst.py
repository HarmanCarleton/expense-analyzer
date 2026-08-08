from crewai import Agent, Task, Crew, LLM
from database import get_transactions_for_month, get_all_months
from collections import defaultdict
import json

llm = LLM(
    model="gpt-4.1-mini",
    temperature=0.3,  # consistent output, good for analysis
    timeout=120
)

analyst_agent = Agent(   # Analyst agent that goes through the total and charts and provide a great feedback.
    role="Personal Finance Spending Analyst",
    goal="Identify spending trends that are genuinely meaningful, prioritizing material changes over noise.",
    backstory="""
    You are an experienced personal finance analyst.
    You understand that percentage changes can be misleading when the underlying dollar amount is small, and that modest percentage changes can still matter when the category is large.
    You focus on changes that would actually help someone understand or manage their spending.
    You avoid calling trivial fluctuations 'notable' and instead highlight only material, sustained, or unusual changes.
    """,
    llm=llm,
    verbose=False,
)

def analyze_trends(current_month: str, previous_month: str | None, card_name: str) -> str:
    comparison = compare_months(current_month, previous_month, card_name)

    analysis_task = Task(
        description=f"""
            You are given a month-over-month spending comparison by category for {card_name}.

            Compare {current_month} to {previous_month or "no previous data available"}:

            {json.dumps(comparison, indent=2)}

            Identify the 3-4 most notable findings.

            What counts as notable:
            - A meaningful increase or decrease in a category.
            - A moderate percentage change in a large-spend category.
            - A large absolute dollar change, even if the percentage change is modest.
            - An unusual or suspicious pattern, such as a large amount in "Other", which may suggest a categorization issue.

            What does not count as notable:
            - Small-dollar changes with large percentage swings.
            - Minor fluctuations that would not matter to a person managing spending.

            Write the findings in plain, friendly language, and explain why each one matters.
            Do not simply restate the raw numbers.
            """,
        expected_output="""
            A bulleted list of 3-4 notable findings in plain, friendly language.
            """,
        agent=analyst_agent,
        )

    crew = Crew(agents=[analyst_agent], tasks=[analysis_task], verbose=False)
    result = crew.kickoff()
    return result.raw



def calculate_category_totals(statement_month: str, card_name: str) -> dict:
    """Returns {category: total_amount} for a given month."""
    transactions = get_transactions_for_month(statement_month, card_name)
    totals = defaultdict(float)
    for t in transactions:
        totals[t["category"]] += t["amount"]
    return dict(totals)

def compare_months(current_month: str, previous_month: str, card_name: str) -> dict:
    """
    Returns a structured comparison: current totals, previous totals,
    and the dollar/percent difference per category.
    """
    current_totals = calculate_category_totals(current_month,card_name)
    previous_totals = calculate_category_totals(previous_month, card_name) if previous_month else {}

    all_categories = set(current_totals.keys()) | set(previous_totals.keys())
    comparison = {}

    for category in all_categories:
        current_amt = current_totals.get(category, 0.0)
        previous_amt = previous_totals.get(category, 0.0)
        diff = current_amt - previous_amt
        pct_change = (diff / previous_amt * 100) if previous_amt > 0 else None

        comparison[category] = {
            "current": round(current_amt, 2),
            "previous": round(previous_amt, 2),
            "difference": round(diff, 2),
            "percent_change": round(pct_change, 1) if pct_change is not None else None
        }

    return comparison

def get_previous_month(statement_month: str) -> str | None:
    """Given the current month, find the most recent prior month we have data for."""
    all_months = get_all_months()
    prior_months = [m for m in all_months if m < statement_month]
    return prior_months[-1] if prior_months else None
