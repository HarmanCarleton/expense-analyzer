from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Literal
from merchant_memory import load_memory
import re
from crewai import Agent, Task, Crew, LLM

llm = LLM(
    model="gpt-4.1-mini",
    temperature=0.3,  # more consistent output, good for categorization
    timeout=120
)

load_dotenv()

CATEGORIES = [
    "Groceries", "Restaurants", "Transportation", "Shopping",
    "Entertainment", "Subscriptions", "Personal Care",
    "Bills & Utilities", "Travel", "Other"
]

DATE_PATTERNS = [
    r'^([A-Z][a-z]{2}\s?\d{1,2})',        # Jun28, Jun 28
    r'^(\d{4}-\d{2}-\d{2})',               # 2026-07-18
    r'^(\d{1,2}/\d{1,2}/\d{4})',           # 07/18/2026
]

class Transaction(BaseModel):   # Pydantic model that forces the output to follow this structure
    date: str
    merchant: str
    amount: float
    category: Literal[
        "Groceries", "Restaurants", "Transportation", "Shopping",
        "Entertainment", "Subscriptions", "Personal Care",
        "Bills & Utilities", "Travel", "Other"
    ]
    confidence: float = Field(description="0.0 to 1.0, how confident the categorization is")
    from_memory: bool = False  # tracks whether this came from saved memory, not the LLM


class TransactionListInternal(BaseModel):
    transactions: list[Transaction] # A list of Transactions (all the transaction lines)

def check_memory_for_line(line: str, memory: dict):
    """
    Checks if any known merchant name appears in this raw line.
    Returns (matched_merchant_name, category) if found, otherwise None.
    """
    line_upper = line.upper()
    for known_merchant, category in memory.items():
        if known_merchant in line_upper:
            return known_merchant, category
    return None


def parse_date_and_amount(line: str):  # Used to extract the Date and Amount from the lines that are not sent to LLM, instead came from memory
    stripped = line.strip()

    date = "Unknown"
    for pattern in DATE_PATTERNS:
        match = re.match(pattern, stripped)
        if match:
            date = match.group(1)
            break

    amount_match = re.search(r'(-?[\d,]+\.\d{2})\s*$', stripped)
    amount = float(amount_match.group(1).replace(",", "")) if amount_match else 0.0

    return date, amount

def categorize_transactions(transaction_lines: list[str]) -> list[Transaction]: # Main function that calls the LLM for categorizing the lines and also responsible for structuring the memory lines
    memory = load_memory()

    memory_matched = []      # (line, merchant_name, category)
    needs_llm = []

    for line in transaction_lines:
        if memory:
            match = check_memory_for_line(line, memory)
            if match:
                merchant_name, category = match
                memory_matched.append((line, merchant_name, category))
            else:
                needs_llm.append(line)
        else:
            needs_llm.append(line)

    llm_results = []
    if needs_llm:
        llm_results = categorize_with_crew(needs_llm) # Calls the CrewAI's agent to categorize the lines

    memory_transactions = []
    for line, merchant_name, category in memory_matched:
        date, amount = parse_date_and_amount(line)
        memory_transactions.append(Transaction(
            date=date,
            merchant=merchant_name,   # clean name, straight from memory — no parsing needed
            amount=amount,
            category=category,
            confidence=1.0,
            from_memory=True
        ))

    return memory_transactions + llm_results


categorizer_agent = Agent( # Categorizer Agent that goes through all the required lines and categorizes
    role = "Credit Card Transaction Categorizer",
    goal = "Assign each credit card transaction to the most accurate standard spending category with calibrated confidence.",
    backstory="""You are a meticulous financial analyst who has reviewed
    thousands of credit card statements. You are careful to flag genuine
    uncertainty with a lower confidence score rather than guessing
    confidently when a merchant name is ambiguous.""",
    llm=llm,
    verbose =False
)

def categorize_with_crew(transaction_lines: list[str]) -> list[Transaction]:
    joined_lines = "\n".join(transaction_lines)

    categorize_task = Task(
    description=f"""Categorize each of the following transaction lines.
        Each line contains a date, a merchant description, and an amount:


        {joined_lines}


        For each line, extract: date (just the first date if two are present), a cleaned-up merchant name (remove
        store numbers, location codes), the amount, a category from
        {", ".join(CATEGORIES)}, and a confidence score (0.0-1.0, lower
        when the merchant is ambiguous).""",
    expected_output="A JSON object matching the TransactionListInternal schema.",
    agent=categorizer_agent,
    output_pydantic=TransactionListInternal,
    )
    

    crew = Crew(agents=[categorizer_agent], tasks=[categorize_task], verbose=False)
    result = crew.kickoff()

    return result.pydantic.transactions
    