"""Dynamic Cloud Failure and QoS-Aware Service Reselection.

Streamlit Dashboard for demonstrating cloud service failure detection,
QoS degradation, and transparent reselection of eligible alternative services.
"""

from __future__ import annotations
import copy
from typing import Dict, Any
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.service_registry import get_default_services, compute_reference_bounds, CloudService
from src.qos_evaluator import QoSEvaluator, validate_and_normalize_weights
from src.failure_simulator import FailureSimulator
from src.recommendation_engine import RecommendationEngine


# ---------------------------------------------------------
# Page Configuration & Styling
# ---------------------------------------------------------
st.set_page_config(
    page_title="Dynamic Cloud Failure & QoS Reselection",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #475569;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px 16px;
    }
    .badge-available {
        background-color: #DCFCE7;
        color: #15803D;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-unavailable {
        background-color: #FEE2E2;
        color: #B91C1C;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-recommended {
        background-color: #DBEAFE;
        color: #1D4ED8;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------
if "simulator" not in st.session_state:
    st.session_state.simulator = FailureSimulator()

if "prev_recommended_id" not in st.session_state:
    st.session_state.prev_recommended_id = None

if "last_action_summary" not in st.session_state:
    st.session_state.last_action_summary = None

simulator: FailureSimulator = st.session_state.simulator
all_services = simulator.get_all_services()
reference_bounds = compute_reference_bounds(all_services)
evaluator = QoSEvaluator(reference_bounds)
engine = RecommendationEngine(evaluator)


# ---------------------------------------------------------
# Sidebar: Simulation Controls & QoS Priorities
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Simulation Controls")

    # Category Selection
    available_categories = sorted(list(set(s.category for s in all_services)))
    selected_category = st.selectbox(
        "Service Category",
        options=available_categories,
        index=0,
        help="Select the cloud service category to inspect and evaluate.",
    )

    st.markdown("---")
    st.subheader("🎯 QoS Metric Priorities")
    st.caption("Adjust importance weights (normalized automatically):")

    w_lat = st.slider("Latency Weight (lower is better)", 0.0, 1.0, 0.35, 0.05)
    w_cost = st.slider("Cost Weight (lower is better)", 0.0, 1.0, 0.20, 0.05)
    w_avail = st.slider("Availability Weight (higher is better)", 0.0, 1.0, 0.30, 0.05)
    w_rel = st.slider("Reliability Weight (higher is better)", 0.0, 1.0, 0.15, 0.05)

    user_weights = {
        "latency": w_lat,
        "cost": w_cost,
        "availability": w_avail,
        "reliability": w_rel,
    }
    normalized_weights = validate_and_normalize_weights(user_weights)

    st.caption(
        f"**Effective Weights:** Latency: `{normalized_weights['latency']:.2f}`, "
        f"Cost: `{normalized_weights['cost']:.2f}`, "
        f"Avail: `{normalized_weights['availability']:.2f}`, "
        f"Rel: `{normalized_weights['reliability']:.2f}`"
    )

    st.markdown("---")
    st.subheader("⚡ Failure Injection Target")

    category_services = [s for s in all_services if s.category == selected_category]
    service_options = {s.service_id: f"{s.service_id} - {s.name}" for s in category_services}

    target_service_id = st.selectbox(
        "Target Service",
        options=list(service_options.keys()),
        format_func=lambda x: service_options[x],
        help="Choose a candidate service to inject faults or restore.",
    )

    col_act1, col_act2 = st.columns(2)
    with col_act1:
        spike_val = st.number_input("Spike (ms)", min_value=10, max_value=1000, value=150, step=25)
    with col_act2:
        drop_val = st.number_input("Avail Drop (%)", min_value=1, max_value=100, value=25, step=5)

    # Action Buttons
    target_svc = simulator.get_service(target_service_id)
    before_state = copy.deepcopy(target_svc) if target_svc else None

    btn_spike = st.button("⚡ Inject Latency Spike", use_container_width=True)
    btn_outage = st.button("🔴 Simulate Outage", use_container_width=True)
    btn_drop = st.button("📉 Reduce Availability", use_container_width=True)
    btn_restore = st.button("🟢 Restore Service", use_container_width=True)
    st.markdown("---")
    btn_reset = st.button("🔄 Reset All Services", use_container_width=True, type="secondary")

    if btn_spike and target_service_id:
        ok, msg = simulator.inject_latency_spike(target_service_id, float(spike_val))
        st.session_state.last_action_summary = {
            "action": "Latency Spike",
            "service_id": target_service_id,
            "service_name": target_svc.name if target_svc else "",
            "before": f"{before_state.latency:.1f}ms",
            "after": f"{target_svc.latency:.1f}ms",
            "message": msg,
        }
        st.rerun()

    if btn_outage and target_service_id:
        ok, msg = simulator.simulate_outage(target_service_id)
        st.session_state.last_action_summary = {
            "action": "Simulate Outage",
            "service_id": target_service_id,
            "service_name": target_svc.name if target_svc else "",
            "before": before_state.operational_status if before_state else "",
            "after": "UNAVAILABLE",
            "message": msg,
        }
        st.rerun()

    if btn_drop and target_service_id:
        ok, msg = simulator.reduce_availability(target_service_id, float(drop_val))
        st.session_state.last_action_summary = {
            "action": "Reduce Availability",
            "service_id": target_service_id,
            "service_name": target_svc.name if target_svc else "",
            "before": f"{before_state.availability:.2f}%",
            "after": f"{target_svc.availability:.2f}%",
            "message": msg,
        }
        st.rerun()

    if btn_restore and target_service_id:
        ok, msg = simulator.restore_service(target_service_id)
        st.session_state.last_action_summary = {
            "action": "Restore Baseline",
            "service_id": target_service_id,
            "service_name": target_svc.name if target_svc else "",
            "before": "Degraded / Modified",
            "after": f"Restored (Lat: {target_svc.latency}ms, Avail: {target_svc.availability}%)",
            "message": msg,
        }
        st.rerun()

    if btn_reset:
        simulator.reset_simulation()
        st.session_state.prev_recommended_id = None
        st.session_state.last_action_summary = {
            "action": "Reset All",
            "service_id": "ALL",
            "service_name": "All Candidate Services",
            "before": "Various Modified States",
            "after": "Pristine Baseline States",
            "message": "All services reset to baseline QoS specifications.",
        }
        st.rerun()


# ---------------------------------------------------------
# Main Panel: Header & Project Context
# ---------------------------------------------------------
st.markdown('<div class="main-title">Dynamic Cloud Failure and QoS-Aware Service Reselection</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">'
    'Major Project Prototype inspired by IEEE ICIMIA-2025: Demonstrates how real-time cloud service outages '
    'and latency degradation dynamically trigger transparent multi-criteria QoS reselection.'
    '</div>',
    unsafe_allow_html=True,
)

# Run Recommendation on current state
recommendation = engine.recommend(
    services=all_services,
    category=selected_category,
    weights=normalized_weights,
    previously_selected_id=st.session_state.prev_recommended_id,
)

# Update session state tracking
if recommendation.selected_service:
    st.session_state.prev_recommended_id = recommendation.selected_service.service_id


# ---------------------------------------------------------
# Summary Metrics Row
# ---------------------------------------------------------
total_in_cat = len(category_services)
healthy_in_cat = len([s for s in category_services if s.operational_status == "AVAILABLE"])
unavailable_in_cat = len([s for s in category_services if s.operational_status == "UNAVAILABLE"])
rec_name = recommendation.selected_service.name if recommendation.selected_service else "None (Outage)"
rec_score = f"{recommendation.selected_scores.qos_score:.4f}" if recommendation.selected_scores else "N/A"

m_col1, m_col2, m_col3, m_col4 = st.columns(4)
with m_col1:
    st.metric("Total Category Services", total_in_cat)
with m_col2:
    st.metric("Healthy / Available", healthy_in_cat, delta=None)
with m_col3:
    st.metric(
        "Unavailable / Outage",
        unavailable_in_cat,
        delta=f"+{unavailable_in_cat} down" if unavailable_in_cat > 0 else "0 down",
        delta_color="inverse" if unavailable_in_cat > 0 else "normal",
    )
with m_col4:
    st.metric("Top Recommended", rec_name, delta=f"QoS: {rec_score}")

st.markdown("---")


# ---------------------------------------------------------
# Before & After Action Summary Card (if triggered)
# ---------------------------------------------------------
if st.session_state.last_action_summary:
    summary = st.session_state.last_action_summary
    st.info(
        f"**Latest Action [{summary['action']}]:** {summary['message']} "
        f"*(Target: `{summary['service_id']} - {summary['service_name']}` | "
        f"Before: `{summary['before']}` ➜ After: `{summary['after']}`)*"
    )


# ---------------------------------------------------------
# Recommendation Panel (Explanation & Breakdown)
# ---------------------------------------------------------
st.subheader("💡 Recommendation & Decision Explainability")

if not recommendation.has_eligible_service:
    st.error(
        f"🚨 **NO ELIGIBLE SERVICE AVAILABLE!**\n\n"
        f"{recommendation.status_message}\n\n"
        f"**Reason:** {recommendation.selection_reason}"
    )
else:
    winner = recommendation.selected_service
    scores = recommendation.selected_scores
    st.success(
        f"🏆 **Recommended Service:** `{winner.name}` (`{winner.service_id}`) — "
        f"**Aggregate QoS Score:** `{scores.qos_score:.4f}` / 1.0000"
    )

    with st.expander("🔍 View Detailed Selection Reasoning & Metric Breakdown", expanded=True):
        st.write(recommendation.selection_reason)

        col_b1, col_b2, col_b3, col_b4 = st.columns(4)
        col_b1.progress(scores.latency_score, text=f"Latency Score: {scores.latency_score:.2f}")
        col_b2.progress(scores.cost_score, text=f"Cost Score: {scores.cost_score:.2f}")
        col_b3.progress(scores.availability_score, text=f"Availability Score: {scores.availability_score:.2f}")
        col_b4.progress(scores.reliability_score, text=f"Reliability Score: {scores.reliability_score:.2f}")

    if recommendation.excluded_services:
        with st.expander(f"⚠️ Excluded Services ({len(recommendation.excluded_services)})"):
            for s, reason in recommendation.excluded_services:
                st.markdown(f"- **{s.name} (`{s.service_id}`)**: {reason}")

st.markdown("---")


# ---------------------------------------------------------
# Candidate Services Table & QoS Ranking
# ---------------------------------------------------------
st.subheader(f"📋 Candidate Services Registry ({selected_category})")

table_rows = []
for s in category_services:
    s_scores = evaluator.evaluate_service(s, normalized_weights)
    is_rec = recommendation.selected_service and (s.service_id == recommendation.selected_service.service_id)
    status_label = "✅ AVAILABLE" if s.operational_status == "AVAILABLE" else "❌ UNAVAILABLE"
    rec_label = "⭐ RECOMMENDED" if is_rec else ("ELIGIBLE" if s.operational_status == "AVAILABLE" else "EXCLUDED")

    table_rows.append({
        "Service ID": s.service_id,
        "Service Name": s.name,
        "Category": s.category,
        "Latency (ms)": f"{s.latency:.1f}",
        "Cost ($)": f"${s.cost:.3f}",
        "Availability (%)": f"{s.availability:.2f}%",
        "Reliability (%)": f"{s.reliability:.2f}%",
        "Operational Status": status_label,
        "QoS Score": s_scores.qos_score,
        "Selection Role": rec_label,
    })

df_display = pd.DataFrame(table_rows)
st.dataframe(
    df_display.style.highlight_max(subset=["QoS Score"], color="#DBEAFE"),
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------
# Visual Analytics: Plotly Comparative QoS Chart
# ---------------------------------------------------------
st.subheader("📊 QoS Comparative Evaluation Chart")

chart_data = []
for s in category_services:
    s_scores = evaluator.evaluate_service(s, normalized_weights)
    is_rec = recommendation.selected_service and (s.service_id == recommendation.selected_service.service_id)
    is_down = s.operational_status == "UNAVAILABLE"

    color_group = "Unavailable" if is_down else ("Recommended" if is_rec else "Eligible Alternative")
    chart_data.append({
        "Service": f"{s.service_id} ({s.name})",
        "QoS Score": s_scores.qos_score,
        "Status": color_group,
        "Latency Score": s_scores.latency_score,
        "Cost Score": s_scores.cost_score,
        "Availability Score": s_scores.availability_score,
        "Reliability Score": s_scores.reliability_score,
    })

df_chart = pd.DataFrame(chart_data)

color_discrete_map = {
    "Recommended": "#2563EB",       # Blue
    "Eligible Alternative": "#10B981", # Green
    "Unavailable": "#EF4444",        # Red
}

fig = px.bar(
    df_chart,
    x="Service",
    y="QoS Score",
    color="Status",
    color_discrete_map=color_discrete_map,
    text="QoS Score",
    title=f"Multi-Criteria Aggregate QoS Scores — Category: {selected_category}",
    range_y=[0.0, 1.05],
)
fig.update_traces(texttemplate="%{text:.3f}", textposition="outside")
fig.update_layout(
    xaxis_title="Candidate Cloud Services",
    yaxis_title="Aggregate Weighted QoS Score (0 to 1)",
    legend_title="Service State",
    font=dict(family="Inter, sans-serif", size=13),
    margin=dict(l=40, r=40, t=50, b=40),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("---")


# ---------------------------------------------------------
# Event Audit Log
# ---------------------------------------------------------
st.subheader("📜 Simulation Event Audit Log")
events = simulator.get_event_logs()
if events:
    df_events = pd.DataFrame(events)
    # Reverse to show newest first
    df_events = df_events.iloc[::-1].reset_index(drop=True)
    df_events.rename(
        columns={
            "timestamp": "Timestamp",
            "action": "Action",
            "service_id": "Service ID",
            "service_name": "Service Name",
            "details": "Simulation Details & Outcome",
        },
        inplace=True,
    )
    st.dataframe(df_events, use_container_width=True, hide_index=True)
else:
    st.write("No simulation events logged yet.")
