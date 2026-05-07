"""Custom CSS cho giao diện Streamlit - phong cách minimalist."""

CUSTOM_CSS = """
<style>
/* ============ FONT & BASE ============ */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ============ HEADERS ============ */
h1 {
    font-weight: 700;
    color: #0F172A;
    letter-spacing: -0.02em;
    font-size: 2rem !important;
}

h2, h3 {
    font-weight: 600;
    color: #1E293B;
    letter-spacing: -0.01em;
}

/* ============ MAIN CONTAINER ============ */
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}

/* ============ SIDEBAR ============ */
section[data-testid="stSidebar"] {
    background-color: #F8FAFC;
    border-right: 1px solid #E2E8F0;
}

section[data-testid="stSidebar"] h2 {
    font-size: 1.1rem;
    color: #334155;
    margin-bottom: 0.5rem;
}

/* ============ BUTTONS ============ */
.stButton > button {
    border-radius: 6px;
    border: 1px solid #E2E8F0;
    background-color: #FFFFFF;
    color: #1E293B;
    font-weight: 500;
    font-size: 0.875rem;
    transition: all 0.15s ease;
    padding: 0.5rem 1rem;
}

.stButton > button:hover {
    border-color: #1E40AF;
    color: #1E40AF;
    background-color: #F8FAFC;
}

.stButton > button[kind="primary"] {
    background-color: #1E40AF;
    color: #FFFFFF;
    border-color: #1E40AF;
}

.stButton > button[kind="primary"]:hover {
    background-color: #1E3A8A;
    border-color: #1E3A8A;
}

/* ============ METRICS ============ */
[data-testid="stMetric"] {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 1.25rem;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
}

[data-testid="stMetricLabel"] {
    font-size: 0.8rem;
    color: #64748B;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

[data-testid="stMetricValue"] {
    font-size: 1.75rem;
    font-weight: 700;
    color: #0F172A;
}

[data-testid="stMetricDelta"] {
    font-size: 0.8rem;
    font-weight: 500;
}

/* ============ INPUT FIELDS ============ */
.stTextInput > div > div > input,
.stSelectbox > div > div > div {
    border-radius: 6px;
    border: 1px solid #E2E8F0;
    font-size: 0.9rem;
}

.stTextInput > div > div > input:focus {
    border-color: #1E40AF;
    box-shadow: 0 0 0 3px rgba(30, 64, 175, 0.1);
}

/* ============ ALERTS ============ */
.stAlert {
    border-radius: 6px;
    border: none;
    padding: 0.75rem 1rem;
}

div[data-testid="stAlert"][data-baseweb="notification"] {
    border-left: 3px solid;
}

/* ============ TABS ============ */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 1px solid #E2E8F0;
}

.stTabs [data-baseweb="tab"] {
    height: 40px;
    padding: 0 1.25rem;
    background-color: transparent;
    color: #64748B;
    font-weight: 500;
    font-size: 0.9rem;
    border-radius: 0;
    border-bottom: 2px solid transparent;
}

.stTabs [aria-selected="true"] {
    color: #1E40AF !important;
    border-bottom: 2px solid #1E40AF !important;
    background-color: transparent !important;
}

/* ============ DATAFRAME ============ */
[data-testid="stDataFrame"] {
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    overflow: hidden;
}

/* ============ EXPANDER ============ */
.streamlit-expanderHeader {
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    font-weight: 500;
    color: #334155;
}

/* ============ CONTAINERS WITH BORDER ============ */
[data-testid="stContainer"][data-border="true"] {
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 1.25rem;
    background-color: #FFFFFF;
}

/* ============ DIVIDER ============ */
hr {
    margin: 1.5rem 0;
    border: none;
    border-top: 1px solid #E2E8F0;
}

/* ============ CAPTION ============ */
.stCaption {
    color: #64748B;
    font-size: 0.825rem;
}

/* ============ CODE BLOCK ============ */
code {
    background-color: #F1F5F9;
    color: #1E293B;
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    font-size: 0.85em;
    font-family: 'JetBrains Mono', 'Courier New', monospace;
}

/* ============ HIDE STREAMLIT BRANDING ============ */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.viewerBadge_container__1QSob {display: none !important;}

/* ============ CUSTOM CARD ============ */
.custom-card {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1rem;
}

.custom-card-title {
    font-size: 0.875rem;
    color: #64748B;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
}

.custom-card-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #0F172A;
}

/* ============ SECTION HEADER ============ */
.section-header {
    font-size: 1.125rem;
    font-weight: 600;
    color: #1E293B;
    margin: 1.5rem 0 0.75rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #E2E8F0;
}

/* ============ STATUS BADGE ============ */
.status-badge {
    display: inline-block;
    padding: 0.25rem 0.625rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.status-running {
    background-color: #DCFCE7;
    color: #166534;
}

.status-stopped {
    background-color: #FEE2E2;
    color: #991B1B;
}

.status-pending {
    background-color: #FEF3C7;
    color: #92400E;
}
</style>
"""


def apply_custom_style():
    """Áp dụng custom CSS vào Streamlit app."""
    import streamlit as st
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)