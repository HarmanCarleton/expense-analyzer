from extract_pdf import get_all_pages_text, filter_candidate_lines
from redact_pii import redact_all_lines, is_safe_to_send
from categorize import categorize_transactions

from database import save_transactions, has_existing_transactions, delete_transactions_for_month


def run_pipeline_until_review(pdf_path: str):
    """Runs extraction through categorization, stops before human review."""
    all_lines = get_all_pages_text(pdf_path)
    candidates = filter_candidate_lines(all_lines)
    redacted = redact_all_lines(candidates)

    safe, problems = is_safe_to_send(redacted)
    if not safe:
        raise ValueError(f"Unsafe data detected: {problems}")
   
    categorized = categorize_transactions(redacted) #Calls the Categorization Agent
    return categorized

def finish_pipeline_after_review(reviewed_transactions, card_name, statement_month, overwrite=False):
    """Takes fully-reviewed transactions and saves them."""
    if has_existing_transactions(card_name, statement_month):  # This function checks if there are already entries present for this card_name + statement_month

        if not overwrite:
            raise ValueError( f"Transactions for {card_name} / {statement_month} already exist. " )
        else:
            delete_transactions_for_month(card_name, statement_month) # Deletes all the rows from the database that matches card name and statement_month

    save_transactions(reviewed_transactions, card_name, statement_month) # Save the transaction lines into the database

    return reviewed_transactions
