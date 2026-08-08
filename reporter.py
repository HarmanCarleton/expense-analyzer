from crewai import Agent, Task, Crew, LLM
from analyst import calculate_category_totals, analyze_trends, get_previous_month
from charts import generate_category_chart
from datetime import datetime
from database import init_db, save_report


llm = LLM(
    model="gpt-4.1-mini",
    temperature=0.6,  # lower = more consistent/deterministic output, good for categorization & analysis
    timeout=120
)

reporter_agent = Agent( # Reporter Agent that summarizez the Monthly expenditure
    role="Personal Finance Reporter",
    goal="Write a clear, concise monthly spending summary that highlights the most important takeaways for a non-technical reader.",
    backstory="""
        You write monthly financial summaries for everyday people, not analysts.
        You avoid jargon, keep explanations simple, and lead with the most important takeaway first.
        You focus on what changed, what matters, and what the reader should notice.
        You write like a knowledgeable friend: clear, practical, and easy to skim.
        """,
    llm=llm,
    verbose=False,
)

def generate_monthly_report(statement_month: str, card_name: str) -> dict:
    init_db()

    previous_month = get_previous_month(statement_month)

    totals = calculate_category_totals(statement_month,card_name)
    total_spent = sum(totals.values())

    chart_path = generate_category_chart(statement_month,card_name)

    insights = analyze_trends(statement_month, previous_month,card_name)

    # Writing final report...
    report_task = Task(
        description=f"""Write a monthly spending summary for {statement_month}.

        Total spent this month: ${total_spent:.2f}

        Category breakdown: {totals}

        Analyst's notable findings:
        {insights}

        Write a short, friendly summary (3-5 sentences) that leads with the
        most important takeaway, mentions the total spent, and highlights
        1-2 of the most notable findings in plain language. Do not just
        list every number — synthesize it into a narrative.""",
        expected_output="A friendly 3-5 sentence monthly spending summary.",
        agent=reporter_agent,
    )

    crew = Crew(agents=[reporter_agent], tasks=[report_task], verbose=False)
    result = crew.kickoff()
    summary_text = result.raw

    report = {
        "statement_month": statement_month,
        "total_spent": round(total_spent, 2),
        "category_totals": totals,
        "insights": insights,
        "summary": summary_text,
        "chart_path": chart_path,
        "generated_at": datetime.now().isoformat(),
    }
    save_report(report, card_name)  # Saves the report in database
   
    return report