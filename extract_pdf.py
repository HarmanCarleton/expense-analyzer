import pdfplumber
import re

# Loose filter: does this line START with something date-like (3-letter month + day)
# and END with something amount-like (optional minus, digits, decimal)?
# We are NOT extracting fields — just deciding "keep this line" or "discard it."
CANDIDATE_LINE_PATTERN = re.compile(
    r'^[A-Z][a-z]{2}\s?\d{1,2}.*-?[\d,]+\.\d{2}\s*$'
)

def get_all_pages_text(pdf_path):
    all_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        
        for page in pdf.pages:
            page_text = page.extract_text(layout=True)
            if page_text:
                lines = page_text.split("\n")
                all_lines.extend(lines)
    return all_lines

def filter_candidate_lines(lines):
    """Keep only lines that look like they probably contain a transaction."""
    candidates = []
    for line in lines:
        stripped = line.strip()
        if CANDIDATE_LINE_PATTERN.match(stripped):
            candidates.append(stripped)
    return candidates