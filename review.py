from categorize import Transaction

CONFIDENCE_THRESHOLD = 0.7

def split_by_confidence(transactions: list[Transaction]):
    """
    Splits transactions into (auto_accepted, needs_review) based on confidence.
    No terminal input here — this is UI-agnostic, meant to work with
    either a terminal prompt or a web form.
    """
    auto_accepted = [t for t in transactions if t.confidence > CONFIDENCE_THRESHOLD]
    needs_review = [t for t in transactions if t.confidence <= CONFIDENCE_THRESHOLD]
    return auto_accepted, needs_review
