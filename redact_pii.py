import re
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

ENTITIES_TO_REDACT = [
    "CREDIT_CARD",
    "US_SSN",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "IBAN_CODE",
    "BANK_NUMBER",
]

# Backup regex patterns, in case Presidio misses something.
# These specifically target patterns common in bank/credit card statements.
SUSPICIOUS_PATTERNS = [
    re.compile(r'\b(?:\d[ -]*?){13,16}\b'),                     # full 13-16 digit card numbers
    re.compile(r'\b(?:[Xx]{2,4}[\s-]?){2,4}\d{2,4}\b'),         # masked cards like "XXX XXXX XXXX 0123"
    re.compile(r'\b[Xx]{8,}\b'),                                 # long runs of X's (fully masked numbers)
    re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),                       # SSN pattern
    re.compile(r'\b\d{9}\b'),                                    # routing number
    re.compile(r'AccountHolder\s+[A-Za-z]+', re.IGNORECASE),   # catches "AccountHolder JohnA" pattern specifically
]

def redact_text(text: str) -> str:
    """Run Presidio redaction on a single string, excluding safe entity types like dates."""
    results = analyzer.analyze(text=text, language="en")
    filtered_results = [r for r in results if r.entity_type in ENTITIES_TO_REDACT]
    anonymized_result = anonymizer.anonymize(text=text, analyzer_results=filtered_results)
    return anonymized_result.text

def redact_all_lines(lines: list[str]) -> list[str]:
    """Apply redaction to every line in a list."""
    return [redact_text(line) for line in lines]

def is_safe_to_send(lines: list[str]) -> tuple[bool, list[str]]:
    """
    Final safety gate. Checks every (already redacted) line against
    backup regex patterns. Returns (True, []) if clean,
    or (False, [problem lines]) if anything suspicious remains.
    """
    problem_lines = []
    for line in lines:
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(line):
                problem_lines.append(line)
                break  # no need to check other patterns for this line
    is_safe = len(problem_lines) == 0
    return is_safe, problem_lines