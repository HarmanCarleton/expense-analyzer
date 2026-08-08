import matplotlib.pyplot as plt
from analyst import calculate_category_totals
import os

def generate_category_chart(statement_month: str, card_name: str,save_path: str = None) -> str:
    """
    Generates a bar chart of spending by category for the given month.
    Saves it as a PNG and returns the file path.
    """
    totals = calculate_category_totals(statement_month,card_name)

    # Sort by amount descending, for a cleaner-looking chart
    sorted_items = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    categories = [item[0] for item in sorted_items]
    amounts = [item[1] for item in sorted_items]

    if save_path is None:
        os.makedirs("reports", exist_ok=True)
        save_path = f"reports/chart_{card_name,"_",statement_month}.png"

    plt.figure(figsize=(10, 6))
    plt.bar(categories, amounts, color="#4A90D9")
    plt.title(f"Spending by Category — {statement_month}")
    plt.xlabel("Category")
    plt.ylabel("Amount ($)")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()  # important: frees memory, avoids overlapping charts across runs

    return save_path

if __name__ == "__main__":
    path = generate_category_chart("2026-06")
    print(f"Chart saved to: {path}")