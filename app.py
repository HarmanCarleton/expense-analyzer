import streamlit as st
import os
from pipeline import run_pipeline_until_review, finish_pipeline_after_review
from review import split_by_confidence
from merchant_memory import remember_correction
from database import init_db, has_existing_transactions, get_report, get_all_card_names, get_months_for_card
import time
from reporter import generate_monthly_report

from qa import answer_question


MAX_RETRIES = 2

CATEGORIES = [
    "Groceries", "Restaurants", "Transportation", "Shopping",
    "Entertainment", "Subscriptions", "Personal Care",
    "Bills & Utilities", "Travel", "Other"
]

st.set_page_config(page_title="Expense Analyzer", layout="wide")
init_db()

st.title("💳 Personal Expense Analyzer")

# --- Input form ---
st.subheader("Upload a Statement")

if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0
if "show_report" not in st.session_state:
    st.session_state["show_report"] = False
if "qa_key" not in st.session_state:
    st.session_state["qa_key"] = 0

uploaded_file = st.file_uploader("Choose a PDF statement", type=["pdf"],key=f"uploader_{st.session_state['uploader_key']}")
card_name = st.text_input("Card name (e.g. CIBC,Rogers, Amex)", placeholder="All Cards", key=f"card_name_{st.session_state['uploader_key']}")
statement_month = st.text_input("Statement month (format: YYYY-MM)", placeholder="2026-06",key=f"statement_month_{st.session_state['uploader_key']}")

process_button = st.button("Process Statement", type="primary")

if process_button:
    if not uploaded_file:
        st.error("Please upload a PDF first.")
    elif not statement_month:
        st.error("Please enter a statement month.")
    else:
        # Save the uploaded file to our statements folder
        os.makedirs("statements", exist_ok=True)
        save_path = f"statements/{uploaded_file.name}"
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        st.session_state["pending_upload"] = {
            "save_path": save_path,
            "card_name": card_name,
            "statement_month": statement_month,
        }

       # Step 2: this block runs on EVERY rerun, checking session_state instead of
# the transient button — so it still works after the checkbox rerun happens.
if "pending_upload" in st.session_state:
    pending = st.session_state["pending_upload"]
    p_card = pending["card_name"]
    p_month = pending["statement_month"]
    p_path = pending["save_path"]

    if has_existing_transactions(p_card, p_month):
        st.warning(f"Data for {p_card} / {p_month} already exists. Re-processing will overwrite it.")
        confirm_overwrite = st.checkbox("Yes, overwrite existing data", key="confirm_overwrite_checkbox")
        run_now = confirm_overwrite
    else:
        run_now = True

    if run_now:
        with st.spinner("Extracting and categorizing... this may take a minute."):
            categorized = None
            last_error = None

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    categorized = run_pipeline_until_review(p_path)
                    break  # success, exit retry loop
                except Exception as e:
                    last_error = e
                    if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                        st.warning(f"Attempt {attempt} timed out, retrying...")
                        time.sleep(3)
                    else:
                        break  # non-timeout error, don't bother retrying

            if categorized is not None:
                auto_accepted, needs_review = split_by_confidence(categorized)
                st.session_state["review_queue"] = needs_review
                st.session_state["auto_accepted"] = auto_accepted
                st.session_state["review_card"] = p_card
                st.session_state["review_month"] = p_month
            else:
                st.error(f"Failed after {MAX_RETRIES} attempts: {last_error}")

        del st.session_state["pending_upload"]

# --- Human-in-the-loop review section (runs on every rerun) ---
if "review_queue" in st.session_state and len(st.session_state["review_queue"]) > 0:
    st.divider()
    st.subheader("Review Uncertain Transactions")
    st.write(f"{len(st.session_state['review_queue'])} transaction(s) need your input:")

    # Show ONE transaction at a time to keep the UI simple
    current = st.session_state["review_queue"][0]

    st.write(f"**Merchant:** {current.merchant}")
    st.write(f"**Amount:** ${current.amount}")
    st.write(f"**Date:** {current.date}")
    st.write(f"**LLM guess:** {current.category} (confidence: {current.confidence})")

    chosen_category = st.selectbox("Correct category:", CATEGORIES,
                                     index=CATEGORIES.index(current.category),
                                     key=f"category_select_{len(st.session_state['review_queue'])}")

    if st.button("Confirm Category"):
        current.category = chosen_category
        current.confidence = 1.0
        remember_correction(current.merchant, chosen_category)

        st.session_state["auto_accepted"].append(current)
        st.session_state["review_queue"].pop(0)
        st.rerun()  # force immediate rerun to show the next item (or finish)

elif "review_queue" in st.session_state:
    # Queue is empty — finalize and save
    with st.spinner("Saving transactions..."):
        final_transactions = finish_pipeline_after_review(
            st.session_state["auto_accepted"],
            st.session_state["review_card"],
            st.session_state["review_month"],
            overwrite=True,
        )

    with st.spinner("Generating monthly report (this calls the Analyst and Reporter agents)..."):
        report = generate_monthly_report(
            st.session_state["review_month"],
            st.session_state["review_card"],
        )

        st.success(f"All done! Saved {len(final_transactions)} transactions and generated your report.")
        st.session_state["last_processed"] = (st.session_state["review_card"], st.session_state["review_month"])
        st.session_state["show_report"] = True\
        
        # Clean up
        del st.session_state["review_queue"]
        del st.session_state["auto_accepted"]    

st.divider()
st.subheader("Monthly Report")

available_cards = get_all_card_names()

if not available_cards:
    st.info("No reports yet — process a statement above to get started.")
else:
    if "last_processed" in st.session_state:
        default_card, default_month = st.session_state["last_processed"]
    else:
        default_card, default_month = available_cards[0], None

    view_card = st.selectbox(
        "Card",
        available_cards,
        index=available_cards.index(default_card) if default_card in available_cards else 0,
    )

    available_months = get_months_for_card(view_card)

    if not available_months:
        st.info(f"No reports found for {view_card}.")
    else:
        month_index = available_months.index(default_month) if default_month in available_months else 0
        view_month = st.selectbox("Month", available_months, index=month_index)

        if st.button("Show Report"):
            st.session_state["show_report"] = True

        if st.session_state["show_report"]:
            report = get_report(view_month, view_card)

            col1, col2 = st.columns([1, 1])
            with col1:
                st.metric("Total Spent", f"${report['total_spent']:.2f}")
                st.write("**Summary**")
                st.write(report["summary"])
            with col2:
                st.write("**Category Breakdown**")
                st.image(report["chart_path"])

            with st.expander("See detailed analyst insights"):
                st.write(report["insights"])


st.divider()
st.subheader("Ask About Your Spending")

user_question = st.text_input(
    "Ask a question (e.g. 'How much did I spend on Groceries?')",
    key=f"qa_input_{st.session_state['qa_key']}",
)

ask_button = st.button("Ask")

if ask_button and user_question.strip():
    with st.spinner("Thinking..."):
        try:
            answer = answer_question(user_question)
            st.session_state["qa_history"] = st.session_state.get("qa_history", []) + [
                (user_question, answer)
            ]
            st.session_state["qa_key"] += 1  # forces the text_input to reset to empty
            st.rerun()
        except Exception as e:
            st.error(f"Something went wrong: {e}")

# Show conversation history, most recent first
if "qa_history" in st.session_state and st.session_state["qa_history"]:
    st.write("**Recent questions:**")
    for q, a in reversed(st.session_state["qa_history"]):
        st.markdown(f"**Q:** {q}")
        st.markdown(f"**A:** {a}")
        st.write("")

st.divider()
if st.button("Process Another Statement"):
    for key in ["pending_upload", "review_queue", "auto_accepted", "review_card", "review_month", "qa_history"]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state["uploader_key"] += 1
    st.session_state["qa_key"] += 1
    st.session_state["show_report"] = False
    st.rerun()