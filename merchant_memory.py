import json
import os

MEMORY_PATH = "merchant_memory.json"

def load_memory() -> dict:
    """Load merchant -> category corrections from disk. Returns {} if unavailable."""
    if not os.path.exists(MEMORY_PATH):
        return {}

    try:
        with open(MEMORY_PATH, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_memory(memory: dict):
    """Save the merchant -> category dictionary back to disk."""
    with open(MEMORY_PATH, "w") as f:
        json.dump(memory, f, indent=2)

def remember_correction(merchant: str, category: str):
    """Add or update a single merchant's confirmed category."""
    memory = load_memory()
    memory[merchant.upper().strip()] = category
    save_memory(memory)

def lookup_merchant(merchant: str) -> str | None:
    """Check if we already know this merchant's category. Returns None if unknown."""
    memory = load_memory()
    return memory.get(merchant.upper().strip())