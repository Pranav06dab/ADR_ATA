"""
Clinical Decision Support System (CDSS) — Adverse Drug Reaction (ADR) Detector
================================================================================
Streamlit dashboard for the baseline TF-IDF + Random Forest ADR classifier.

Run from the project root (D:\\adr-detection-project\\) with:
    streamlit run app.py

Expected artifacts (produced by notebooks/02_baseline_model.ipynb):
    models/baseline_random_forest.joblib
    models/tfidf_vectorizer.joblib
"""

import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import streamlit as st

# --------------------------------------------------------------------------- #
# Page configuration — must be the first Streamlit call
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="ADR Detection — Clinical Decision Support",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
MODEL_PATH = Path("models/baseline_random_forest.joblib")
VECTORIZER_PATH = Path("models/tfidf_vectorizer.joblib")

# --------------------------------------------------------------------------- #
# Sample clinical sentences (for one-click demo population)
# --------------------------------------------------------------------------- #
SAMPLE_SENTENCES = {
    "Select a sample...": "",
    "🔴 ADR Example 1 — Angioedema": (
        "The patient developed acute angioedema of the lips and tongue "
        "shortly after initiation of lisinopril therapy."
    ),
    "🔴 ADR Example 2 — Hepatotoxicity": (
        "Elevated liver enzymes and jaundice were observed following "
        "prolonged use of high-dose acetaminophen, consistent with "
        "drug-induced hepatotoxicity."
    ),
    "🟢 Control Example 1 — Routine Follow-up": (
        "The patient reports feeling well and tolerating the current "
        "medication regimen without any new complaints."
    ),
    "🟢 Control Example 2 — Stable Vitals": (
        "Blood pressure and heart rate remained stable throughout the "
        "visit, and no adverse symptoms were reported."
    ),
}

# --------------------------------------------------------------------------- #
# Text preprocessing — MUST mirror the cleaning logic used in Notebook 01
# --------------------------------------------------------------------------- #
def clean_text(text: str) -> str:
    """
    Apply the exact preprocessing pipeline used during training so that
    inference-time text matches the distribution the vectorizer was fit on.
    """
    if not isinstance(text, str):
        return ""

    text = text.lower()
    # Strip bracketed text / citation markers, e.g. "[1]" or "[see note]"
    text = re.sub(r"\[.*?\]", "", text)
    # Strip non-alphabetical characters (keep spaces)
    text = re.sub(r"[^a-zA-Z\s]", " ", text)
    # Normalize multiple spaces down to a single space and trim
    text = re.sub(r"\s+", " ", text).strip()

    return text


# --------------------------------------------------------------------------- #
# Cached artifact loading
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner="Loading model artifacts...")
def load_artifacts():
    """
    Load the trained Random Forest model and fitted TF-IDF vectorizer.
    Cached via st.cache_resource so this runs once per session, not on
    every widget interaction / rerun.

    Returns:
        (model, vectorizer, error_message)
        error_message is None on success, otherwise a human-readable string.
    """
    if not MODEL_PATH.exists() or not VECTORIZER_PATH.exists():
        missing = [
            str(p) for p in (MODEL_PATH, VECTORIZER_PATH) if not p.exists()
        ]
        return None, None, (
            "Required model artifact(s) not found: "
            f"{', '.join(missing)}. "
            "Please run notebooks/02_baseline_model.ipynb first to generate "
            "the model and vectorizer files."
        )

    try:
        model = joblib.load(MODEL_PATH)
        vectorizer = joblib.load(VECTORIZER_PATH)
        return model, vectorizer, None
    except Exception as exc:  # defensive: corrupted file, version mismatch, etc.
        return None, None, f"Failed to load model artifacts: {exc}"


model, vectorizer, load_error = load_artifacts()

# --------------------------------------------------------------------------- #
# Sidebar — model metadata & disclaimer
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("📋 Model Information")

    st.markdown(
        """
        | Attribute | Value |
        |---|---|
        | **Algorithm** | Random Forest Classifier |
        | **Feature Extractor** | TF-IDF (unigrams + bigrams) |
        | **Baseline Accuracy** | 89% |
        | **Class 1 Precision** | 86% |
        """
    )

    st.divider()

    st.subheader("⚠️ Disclaimer")
    st.caption(
        "This application is an **academic prototype** built for a Natural "
        "Language Processing portfolio project. It is **not** a certified "
        "medical device and must **not** be used for real clinical "
        "diagnosis, triage, or treatment decisions. Always consult a "
        "qualified healthcare professional and validated clinical systems "
        "for patient care."
    )

    st.divider()
    st.caption("Baseline model — TF-IDF + Random Forest · v1.0")

# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.title("🩺 Adverse Drug Reaction (ADR) Detection")
st.markdown(
    "##### Clinical Decision Support — NLP Screening Tool for Medical Text"
)
st.info(
    "Paste a clinical note, discharge summary, or sentence below and click "
    "**Analyze Clinical Text** to screen for language indicating a "
    "potential adverse drug reaction. Use the sample selector to try "
    "pre-built examples.",
    icon="ℹ️",
)

# Stop early with a clear warning if artifacts failed to load — no point
# rendering the rest of the interactive UI if inference cannot run.
if load_error:
    st.error(load_error, icon="🚫")
    st.stop()

# --------------------------------------------------------------------------- #
# Input section
# --------------------------------------------------------------------------- #
st.subheader("📝 Clinical Text Input")

col_sample, col_spacer = st.columns([2, 3])
with col_sample:
    selected_sample = st.selectbox(
        "Load a sample sentence (optional):",
        options=list(SAMPLE_SENTENCES.keys()),
    )

# Pre-populate the text area if a sample was chosen; otherwise leave blank
default_text = SAMPLE_SENTENCES.get(selected_sample, "")

user_input = st.text_area(
    "Enter medical note / discharge summary / sentence:",
    value=default_text,
    height=180,
    placeholder=(
        "e.g. The patient developed a severe rash and swelling after "
        "starting the new antibiotic course..."
    ),
)

analyze_clicked = st.button("🔍 Analyze Clinical Text", type="primary")

st.divider()

# --------------------------------------------------------------------------- #
# Inference & results
# --------------------------------------------------------------------------- #
if analyze_clicked:
    if not user_input or not user_input.strip():
        st.warning("Please enter or select some clinical text to analyze.", icon="⚠️")
    else:
        try:
            # 1. Preprocess exactly as done at training time
            cleaned = clean_text(user_input)

            if not cleaned:
                st.warning(
                    "After preprocessing, no analyzable text remained "
                    "(input may contain only numbers/symbols). Please "
                    "revise the input.",
                    icon="⚠️",
                )
            else:
                # 2. Vectorize using the FITTED training vectorizer (transform only)
                vectorized_input = vectorizer.transform([cleaned])

                # 3. Predict class + probabilities
                prediction = model.predict(vectorized_input)[0]
                probabilities = model.predict_proba(vectorized_input)[0]

                # Guard against a model that only saw one class at fit time
                class_index = list(model.classes_).index(prediction)
                confidence = probabilities[class_index] * 100

                prob_no_reaction = (
                    probabilities[list(model.classes_).index(0)] * 100
                    if 0 in model.classes_ else 0.0
                )
                prob_adr = (
                    probabilities[list(model.classes_).index(1)] * 100
                    if 1 in model.classes_ else 0.0
                )

                st.subheader("📊 Analysis Result")
                result_col, prob_col = st.columns([2, 1])

                with result_col:
                    if prediction == 1:
                        st.error(
                            f"### 🚨 Adverse Reaction Detected\n"
                            f"**Confidence: {confidence:.1f}%**\n\n"
                            "The model detected language patterns "
                            "consistent with a potential adverse drug "
                            "reaction. Recommend clinical review.",
                            icon="🚨",
                        )
                    else:
                        st.success(
                            f"### ✅ No Adverse Reaction Detected\n"
                            f"**Confidence: {confidence:.1f}%**\n\n"
                            "The model did not detect language patterns "
                            "typically associated with an adverse drug "
                            "reaction.",
                            icon="✅",
                        )

                with prob_col:
                    st.metric("P(Adverse Reaction)", f"{prob_adr:.1f}%")
                    st.metric("P(No Reaction)", f"{prob_no_reaction:.1f}%")

                # ----------------------------------------------------- #
                # Signal highlights — top TF-IDF terms present in input
                # ----------------------------------------------------- #
                st.subheader("🔑 Signal Highlights")
                st.caption(
                    "Top terms from your input that the TF-IDF vectorizer "
                    "recognized (ranked by TF-IDF weight in this document)."
                )

                feature_names = np.array(vectorizer.get_feature_names_out())
                row = vectorized_input.toarray().flatten()
                nonzero_idx = np.nonzero(row)[0]

                if nonzero_idx.size == 0:
                    st.write(
                        "No recognized vocabulary terms were found in this "
                        "input — the model's vocabulary may not cover the "
                        "wording used."
                    )
                else:
                    top_n = min(10, nonzero_idx.size)
                    top_idx = nonzero_idx[np.argsort(row[nonzero_idx])[::-1][:top_n]]

                    highlight_df = pd.DataFrame(
                        {
                            "Term": feature_names[top_idx],
                            "TF-IDF Weight": np.round(row[top_idx], 4),
                        }
                    ).reset_index(drop=True)

                    st.dataframe(
                        highlight_df,
                        use_container_width=True,
                        hide_index=True,
                    )

                with st.expander("View preprocessed text sent to the model"):
                    st.code(cleaned, language="text")

        except Exception as exc:
            # Defensive catch-all so a single bad input never crashes the app
            st.error(f"An error occurred during analysis: {exc}", icon="🚫")

else:
    st.caption(
        "Results will appear here after you click **Analyze Clinical Text**."
    )
