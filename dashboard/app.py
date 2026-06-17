"""
Customer Satisfaction Dashboard — Nappa Milano AI Customer Service
Run from project root: streamlit run dashboard/app.py
"""

import sqlite3
import re
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
from datetime import datetime

# ── Config ─────────────────────────────────────────────────────────────────────
DB_PATH = "data/bot.db"

# Bilingual stopwords (Indonesian + English) for keyword extraction
STOPWORDS = {
    # Indonesian
    "yang", "dan", "di", "ke", "dari", "ini", "itu", "dengan",
    "adalah", "tidak", "ada", "juga", "saya", "aku", "kamu", "dia",
    "kami", "kita", "mereka", "untuk", "pada", "dalam", "oleh",
    "sudah", "bisa", "akan", "ada", "jadi", "tapi", "atau",
    "ya", "pak", "bu", "mas", "mbak", "gan",
    # English
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "is", "was", "are", "were",
    "be", "been", "have", "has", "had", "do", "did", "does",
    "i", "you", "he", "she", "it", "we", "they", "my", "your",
    "his", "her", "its", "our", "their", "me", "him", "us", "them",
    "this", "that", "these", "those", "not", "no", "so", "very",
    "can", "could", "would", "should", "will", "just", "too",
    "more", "also", "than", "when", "how", "what", "which",
    "all", "any", "some", "up", "out", "there", "one", "get",
}

# ── Data loaders ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_data() -> dict:
    conn = sqlite3.connect(DB_PATH)

    ratings = pd.read_sql_query("""
        SELECT r.rating_id, r.conv_id, r.score, r.feedback_text,
               r.sentiment, r.rated_at,
               c.user_id, c.started_at, c.ended_at, c.message_count
        FROM ratings r
        JOIN conversations c ON r.conv_id = c.conv_id
    """, conn)

    messages = pd.read_sql_query("""
        SELECT m.content, m.role, m.intent_label, m.sent_at, c.user_id
        FROM messages m
        JOIN conversations c ON m.conv_id = c.conv_id
        WHERE m.role = 'user'
    """, conn)

    conn.close()

    if not ratings.empty:
        ratings["rated_at"]   = pd.to_datetime(ratings["rated_at"])
        ratings["started_at"] = pd.to_datetime(ratings["started_at"])

    return {"ratings": ratings, "messages": messages}


def preprocess_keywords(texts: pd.Series) -> list[str]:
    """Clean text, remove stopwords, return flat token list."""
    tokens = []
    for text in texts.dropna():
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        for word in text.split():
            if word not in STOPWORDS and len(word) > 2:
                tokens.append(word)
    return tokens


# ── Page setup ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Nappa Milano · CS Dashboard",
    page_icon="👟",
    layout="wide",
)

# ── Inline CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  /* Metric cards */
  [data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
    padding: 20px 24px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  }
  [data-testid="stMetricValue"] { color: #1e293b; font-weight: 700; }
  [data-testid="stMetricLabel"] { color: #64748b; font-size: 0.78rem; }

  /* Sidebar */
  [data-testid="stSidebar"] {
    background: #f8fafc;
    border-right: 1px solid #e2e8f0;
  }

  /* Page background */
  .stApp { background-color: #f1f5f9; }

  /* Section header */
  .section-header {
    font-size: 1.05rem;
    font-weight: 600;
    color: #4f46e5;
    margin-top: 1.5rem;
    margin-bottom: 0.4rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    border-left: 3px solid #4f46e5;
    padding-left: 10px;
  }

  /* Divider */
  hr { border-color: #e2e8f0 !important; }

  /* Keyword pills */
  .kw-pills { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 0.6rem; }
  .kw-pill {
    background: #ede9fe;
    color: #4338ca;
    font-size: 0.82rem;
    font-weight: 500;
    padding: 5px 14px;
    border-radius: 999px;
    border: 1px solid #c4b5fd;
    white-space: nowrap;
  }
  .kw-pill span { color: #7c3aed; font-weight: 700; margin-left: 6px; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Nappa_milano_logo.png/240px-Nappa_milano_logo.png",
             width=140, use_container_width=False)
    st.markdown("## 👟 Nappa Milano")
    st.markdown("**Customer Satisfaction Dashboard**")
    st.markdown("---")
    st.markdown("### 🔍 Filters")

    sentiment_filter = st.multiselect(
        "Sentiment",
        options=["Positive", "Neutral", "Negative"],
        default=["Positive", "Neutral", "Negative"],
    )
    score_filter = st.slider("Min. Rating Score", min_value=1, max_value=5, value=1)
    st.markdown("---")
    st.caption("Data refreshes every 30 s.")
    if st.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.rerun()

# ── Load data ──────────────────────────────────────────────────────────────────
data    = load_data()
ratings = data["ratings"].copy()
msgs    = data["messages"].copy()

if ratings.empty:
    st.warning("⚠️ No ratings data found. Run `python dashboard/seed_dummy.py` first.")
    st.stop()

# Apply filters
filtered = ratings[
    (ratings["sentiment"].isin(sentiment_filter)) &
    (ratings["score"] >= score_filter)
]

# ── Title ─────────────────────────────────────────────────────────────────────
st.title("📊 Customer Satisfaction · AI Customer Service")
st.caption(f"Showing {len(filtered):,} of {len(ratings):,} ratings  •  Last updated: {datetime.now().strftime('%H:%M:%S')}")
st.markdown("---")

# ── KPI Row ───────────────────────────────────────────────────────────────────
avg_score   = filtered["score"].mean()
total_users = filtered["user_id"].nunique()
pos_pct     = (filtered["sentiment"] == "Positive").sum() / len(filtered) * 100 if len(filtered) else 0
neg_pct     = (filtered["sentiment"] == "Negative").sum() / len(filtered) * 100 if len(filtered) else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("⭐ Avg Rating",       f"{avg_score:.2f} / 5.00")
k2.metric("💬 Total Ratings",    f"{len(filtered):,}")
k3.metric("👤 Unique Users",     f"{total_users:,}")
k4.metric("😊 Positive Rate",    f"{pos_pct:.1f}%")
k5.metric("😟 Negative Rate",    f"{neg_pct:.1f}%")

st.markdown("---")

# ── Row 1: Sentiment Donut  |  Score Distribution ─────────────────────────────
col1, col2 = st.columns([1, 1.4])

with col1:
    st.markdown('<p class="section-header">Sentiment Distribution</p>', unsafe_allow_html=True)
    sentiment_counts = filtered["sentiment"].value_counts().reset_index()
    sentiment_counts.columns = ["Sentiment", "Count"]

    COLOR_MAP = {
        "Positive": "#22c55e",
        "Neutral":  "#facc15",
        "Negative": "#f87171",
    }

    fig_donut = go.Figure(go.Pie(
        labels=sentiment_counts["Sentiment"],
        values=sentiment_counts["Count"],
        hole=0.58,
        marker=dict(
            colors=[COLOR_MAP.get(s, "#888") for s in sentiment_counts["Sentiment"]],
            line=dict(color="#ffffff", width=3),
        ),
        textinfo="percent+label",
        textfont=dict(size=13, color="#1e293b"),
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Share: %{percent}<extra></extra>",
    ))
    fig_donut.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#1e293b",
        margin=dict(t=20, b=20, l=0, r=0),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle", y=0.5,
            xanchor="left",   x=1.02,
            font=dict(size=13),
        ),
        annotations=[dict(
            text=f"<b>{len(filtered)}</b><br>ratings",
            x=0.5, y=0.5,
            font_size=16,
            font_color="#1e293b",
            showarrow=False,
        )],
        height=300,
    )
    st.plotly_chart(fig_donut, use_container_width=True)

with col2:
    st.markdown('<p class="section-header">Rating Score Distribution</p>', unsafe_allow_html=True)
    score_dist = filtered["score"].value_counts().sort_index().reset_index()
    score_dist.columns = ["Score", "Count"]
    score_dist["Label"] = score_dist["Score"].apply(lambda x: "⭐" * x)

    fig_bar = px.bar(
        score_dist, x="Score", y="Count",
        color="Score",
        color_continuous_scale=["#f87171", "#fb923c", "#facc15", "#4ade80", "#22c55e"],
        text="Count",
    )
    fig_bar.update_traces(
        textposition="outside",
        textfont=dict(color="#1e293b", size=13),
        marker_line_width=0,
    )
    fig_bar.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#1e293b",
        margin=dict(t=20, b=20, l=0, r=0),
        showlegend=False,
        coloraxis_showscale=False,
        xaxis=dict(
            title="Rating Score",
            tickvals=[1, 2, 3, 4, 5],
            ticktext=["1 ⭐", "2 ⭐", "3 ⭐", "4 ⭐", "5 ⭐"],
            gridcolor="#e2e8f0",
        ),
        yaxis=dict(title="Number of Ratings", gridcolor="#e2e8f0"),
        height=300,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

# ── Row 2: Rating over Time  |  Sentiment over Time ──────────────────────────
col3, col4 = st.columns(2)

with col3:
    st.markdown('<p class="section-header">Average Rating Over Time</p>', unsafe_allow_html=True)
    time_df = filtered.copy()
    time_df["date"] = time_df["rated_at"].dt.date
    daily_avg = time_df.groupby("date")["score"].mean().reset_index()
    daily_avg.columns = ["Date", "Avg Score"]

    fig_line = px.line(
        daily_avg, x="Date", y="Avg Score",
        markers=True,
        color_discrete_sequence=["#818cf8"],
    )
    fig_line.add_hline(y=4.0, line_dash="dash", line_color="#16a34a",
                       annotation_text="Good threshold (4.0)",
                       annotation_font_color="#16a34a")
    fig_line.update_traces(
        line=dict(width=2.5),
        marker=dict(size=7, color="#4f46e5", line=dict(color="#ffffff", width=1.5)),
    )
    fig_line.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#1e293b",
        margin=dict(t=20, b=20, l=0, r=0),
        xaxis=dict(gridcolor="#e2e8f0"),
        yaxis=dict(gridcolor="#e2e8f0", range=[0.5, 5.5]),
        height=280,
    )
    st.plotly_chart(fig_line, use_container_width=True)

with col4:
    st.markdown('<p class="section-header">Sentiment Trend Over Time</p>', unsafe_allow_html=True)
    time_df["date"]  = time_df["rated_at"].dt.date
    sent_trend = (
        time_df.groupby(["date", "sentiment"])
        .size()
        .reset_index(name="count")
    )
    fig_area = px.area(
        sent_trend, x="date", y="count", color="sentiment",
        color_discrete_map=COLOR_MAP,
        groupnorm="percent",
    )
    fig_area.update_traces(line=dict(width=1.5))
    fig_area.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#1e293b",
        margin=dict(t=20, b=20, l=0, r=0),
        xaxis=dict(gridcolor="#e2e8f0"),
        yaxis=dict(gridcolor="#e2e8f0", title="% Share"),
        legend=dict(title="Sentiment"),
        height=280,
    )
    st.plotly_chart(fig_area, use_container_width=True)

st.markdown("---")

# ── Row 3: Keyword Extraction  |  Per-User Sentiment ─────────────────────────
col5, col6 = st.columns([1.2, 1])

with col5:
    st.markdown('<p class="section-header">Top 10 Keywords from User Messages</p>', unsafe_allow_html=True)
    all_tokens = preprocess_keywords(msgs["content"])
    kw_counter = Counter(all_tokens)
    top_kw     = kw_counter.most_common(10)

    if top_kw:
        # Horizontal bar chart
        kw_df = pd.DataFrame(top_kw, columns=["Keyword", "Frequency"])

        fig_kw = px.bar(
            kw_df.sort_values("Frequency"), x="Frequency", y="Keyword",
            orientation="h",
            color="Frequency",
            color_continuous_scale=["#c4b5fd", "#7c3aed", "#4338ca"],
            text="Frequency",
        )
        fig_kw.update_traces(
            textposition="outside",
            textfont=dict(color="#1e293b", size=12),
            marker_line_width=0,
        )
        fig_kw.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#1e293b",
            margin=dict(t=10, b=10, l=0, r=40),
            showlegend=False,
            coloraxis_showscale=False,
            xaxis=dict(gridcolor="#e2e8f0", title="Frequency"),
            yaxis=dict(gridcolor="#e2e8f0", title=""),
            height=340,
        )
        st.plotly_chart(fig_kw, use_container_width=True)

        # Pill display
        pills_html = '<div class="kw-pills">'
        for word, count in top_kw:
            pills_html += f'<div class="kw-pill">{word}<span>×{count}</span></div>'
        pills_html += '</div>'
        st.markdown(pills_html, unsafe_allow_html=True)
    else:
        st.info("No message data available for keyword extraction.")

with col6:
    st.markdown('<p class="section-header">Per-User Sentiment Score</p>', unsafe_allow_html=True)
    st.caption("Score = (Positive×5 + Neutral×3 + Negative×1) / num_ratings")

    user_sent = (
        filtered.groupby(["user_id", "sentiment"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for col in ["Positive", "Neutral", "Negative"]:
        if col not in user_sent.columns:
            user_sent[col] = 0

    user_sent["total"]       = user_sent["Positive"] + user_sent["Neutral"] + user_sent["Negative"]
    user_sent["satisfaction_score"] = (
        (user_sent["Positive"] * 5 + user_sent["Neutral"] * 3 + user_sent["Negative"] * 1)
        / user_sent["total"]
    ).round(2)
    user_sent = user_sent.sort_values("satisfaction_score", ascending=False)

    fig_user = px.bar(
        user_sent.head(20),
        x="satisfaction_score",
        y="user_id",
        orientation="h",
        color="satisfaction_score",
        color_continuous_scale=["#f87171", "#facc15", "#22c55e"],
        range_color=[1, 5],
        text="satisfaction_score",
    )
    fig_user.update_traces(
        textposition="outside",
        textfont=dict(color="#1e293b", size=10),
        marker_line_width=0,
    )
    fig_user.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#1e293b",
        margin=dict(t=10, b=10, l=0, r=40),
        showlegend=False,
        coloraxis_showscale=False,
        xaxis=dict(gridcolor="#e2e8f0", title="Satisfaction Score (1–5)", range=[0, 5.5]),
        yaxis=dict(gridcolor="#e2e8f0", title="User ID", autorange="reversed"),
        height=400,
    )
    st.plotly_chart(fig_user, use_container_width=True)

st.markdown("---")

# ── Row 4: Satisfaction bucket & recent feedback ──────────────────────────────
col7, col8 = st.columns([1, 1.4])

with col7:
    st.markdown('<p class="section-header">Satisfaction Buckets</p>', unsafe_allow_html=True)

    def bucket(score):
        if score >= 4:  return "😊 Satisfied (4–5)"
        if score == 3:  return "😐 Neutral (3)"
        return "😟 Unsatisfied (1–2)"

    filtered["bucket"] = filtered["score"].apply(bucket)
    bucket_counts = filtered["bucket"].value_counts().reset_index()
    bucket_counts.columns = ["Bucket", "Count"]
    bucket_counts["pct"] = (bucket_counts["Count"] / bucket_counts["Count"].sum() * 100).round(1)

    BUCKET_COLORS = {
        "😊 Satisfied (4–5)":   "#22c55e",
        "😐 Neutral (3)":       "#facc15",
        "😟 Unsatisfied (1–2)": "#f87171",
    }
    fig_bucket = px.pie(
        bucket_counts, values="Count", names="Bucket",
        color="Bucket",
        color_discrete_map=BUCKET_COLORS,
        hole=0,
    )
    fig_bucket.update_traces(
        textinfo="percent+label",
        textfont=dict(size=12, color="#1e293b"),
        marker=dict(line=dict(color="#ffffff", width=2)),
    )
    fig_bucket.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#1e293b",
        margin=dict(t=10, b=10, l=0, r=0),
        showlegend=True,
        legend=dict(font=dict(size=11)),
        height=300,
    )
    st.plotly_chart(fig_bucket, use_container_width=True)

    # Bucket table
    for _, row in bucket_counts.iterrows():
        st.markdown(
            f"<span style='color:{BUCKET_COLORS.get(row['Bucket'], '#fff')}'>"
            f"**{row['Bucket']}**</span>: {row['Count']} ({row['pct']}%)",
            unsafe_allow_html=True
        )

with col8:
    st.markdown('<p class="section-header">Recent Feedback</p>', unsafe_allow_html=True)
    recent = (
        filtered[filtered["feedback_text"].notna()]
        .sort_values("rated_at", ascending=False)
        .head(8)[["rated_at", "user_id", "score", "sentiment", "feedback_text"]]
    )

    def sentiment_badge(s):
        colors = {"Positive": "#22c55e", "Neutral": "#facc15", "Negative": "#f87171"}
        return f"<span style='color:{colors.get(s,'#888')};font-weight:600'>{s}</span>"

    for _, row in recent.iterrows():
        st.markdown(
            f"<div style='background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;"
            f"padding:12px 16px;margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,0.06);'>"
            f"<div style='display:flex;justify-content:space-between;margin-bottom:6px;'>"
            f"<span style='color:#64748b;font-size:0.78rem;'>"
            f"👤 {row['user_id']}  •  {row['rated_at'].strftime('%Y-%m-%d %H:%M')}</span>"
            f"<span>{'⭐'*int(row['score'])}  {sentiment_badge(row['sentiment'])}</span>"
            f"</div>"
            f"<div style='color:#1e293b;font-size:0.9rem;'>{row['feedback_text']}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

st.markdown("---")
st.caption("Nappa Milano AI Customer Service · Internal Dashboard")
