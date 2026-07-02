import json
import os
from datetime import datetime
import pandas as pd
import streamlit as st
import altair as alt

# ==========================================
# 1. CORE BACKEND FUNCTIONS & DATA PERSISTENCE
# ==========================================

DEFAULT_CATEGORIES = ["School", "Work", "Personal", "Study"]

def load_tasks_data():
    if "tasks" not in st.session_state or "categories" not in st.session_state:
        try:
            with open("tasks.json", "r") as file:
                data = json.load(file)
                if isinstance(data, list):
                    st.session_state.tasks = data
                    st.session_state.categories = DEFAULT_CATEGORIES
                else:
                    st.session_state.tasks = data.get("tasks", [])
                    st.session_state.categories = data.get("categories", DEFAULT_CATEGORIES)
        except (FileNotFoundError, json.JSONDecodeError):
            st.session_state.tasks = []
            st.session_state.categories = DEFAULT_CATEGORIES

def save_tasks_data():
    temp_file = "tasks.json.tmp"
    data = {
        "categories": st.session_state.categories,
        "tasks": st.session_state.tasks
    }
    try:
        with open(temp_file, "w") as file:
            json.dump(data, file, indent=4)
        if os.path.exists(temp_file):
            os.replace(temp_file, "tasks.json")
    except Exception as e:
        st.error(f"Error saving tasks: {e}")

def calculate_urgency(due_date_str, time_needed_hours):
    """Calculates a timezone-safe, exponential urgency pressure score."""
    try:
        due_datetime = datetime.strptime(due_date_str, "%d-%m-%Y %H:%M")
        now = datetime.now()
        time_available = (due_datetime - now).total_seconds() / 3600

        if time_available <= 0 or time_needed_hours >= time_available:
            return 10.0

        time_consumption_ratio = time_needed_hours / time_available
        urgency_score = (time_consumption_ratio ** 0.7) * 10
        
        return round(min(10.0, max(0.0, urgency_score)), 2)
    except Exception:
        return 0.0

def map_importance_label(value):
    if value >= 9: return "Critical"
    elif value >= 7: return "Very Important"
    elif value >= 5: return "Moderate"
    elif value >= 3: return "Low"
    else: return "Almost No Value"

def is_overdue(due_date_str):
    try:
        due_datetime = datetime.strptime(due_date_str, "%d-%m-%Y %H:%M")
        return datetime.now() > due_datetime
    except:
        return False

def highlight_overdue(row):
    """Applies a soft red background highlight to items that have passed their deadline."""
    if not row["completed"] and is_overdue(row["due_date"]):
        return ["background-color: #b33939; color: #ffffff;"] * len(row)
    return [""] * len(row)

# ==========================================
# 2. STREAMLIT APP CONFIG & SETUP
# ==========================================

st.set_page_config(page_title="Task Matrix Manager", page_icon="✅", layout="wide")
load_tasks_data()

st.title("✅ Task Matrix Manager")

# Live Data Processing
if st.session_state.tasks:
    for t in st.session_state.tasks:
        t["urgency"] = calculate_urgency(t["due_date"], t.get("time required", 1.0))
        t["final_score"] = round((t["urgency"] * 0.6) + (int(t.get("value", 5)) * 0.4), 2)
    
    raw_df = pd.DataFrame(st.session_state.tasks)
    raw_df = raw_df.sort_values(by=["final_score", "urgency"], ascending=[False, False]).reset_index(drop=True)
else:
    raw_df = pd.DataFrame()

# ==========================================
# 3. METRICS / STATISTICS SECTION
# ==========================================
st.header("Metrics Dashboard")
if not raw_df.empty:
    total_tasks = len(raw_df)
    completed_tasks = raw_df["completed"].sum() if "completed" in raw_df else 0
    pending_tasks = total_tasks - completed_tasks
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Tracked", total_tasks)
    col2.metric("Pending Tasks", pending_tasks, delta=f"-{completed_tasks} Completed", delta_color="inverse")
    critical_count = len(raw_df[raw_df["priority"] == "Critical"]) if "priority" in raw_df else 0
    col3.metric("Highest Threat Tasks", critical_count)
else:
    st.info("Add your first task below to populate dashboard metrics!")

st.markdown("---")

# ==========================================
# 4. ACTIVE WORKSPACE (Tabs + Overdue Highlight)
# ==========================================
st.header("Active Workspace")

if not raw_df.empty:
    cols_order = ["completed", "name", "category", "priority", "value", "due_date", "time required", "urgency", "final_score"]
    
    pending_df = raw_df[raw_df["completed"] == False].reset_index(drop=True)
    completed_df = raw_df[raw_df["completed"] == True].reset_index(drop=True)
    
    tab_pending, tab_completed = st.tabs(["⏳ Pending Tasks", "🎉 Completed Tasks"])
    
    with tab_pending:
        if not pending_df.empty:
            grid_pending = pending_df[[c for c in cols_order if c in pending_df.columns]]
            styled_pending = grid_pending.style.apply(highlight_overdue, axis=1)
            
            edited_pending = st.data_editor(
                styled_pending,
                use_container_width=True,
                hide_index=True,
                key="pending_editor",
                column_config={
                    "completed": st.column_config.CheckboxColumn("Done?", help="Mark complete"),
                    "name": st.column_config.TextColumn("Task Name", required=True),
                    "category": st.column_config.SelectboxColumn("Category", options=st.session_state.categories, required=True),
                    "priority": st.column_config.TextColumn("Tier Status", disabled=True),
                    "value": st.column_config.NumberColumn("Importance (1-10)", min_value=1, max_value=10, step=1),
                    "due_date": st.column_config.TextColumn("Due Date (DD-MM-YYYY HH:MM)"),
                    "time required": st.column_config.NumberColumn("Hours Required", min_value=0.1),
                    "urgency": st.column_config.NumberColumn("Urgency Score", disabled=True),
                    "final_score": st.column_config.NumberColumn("Final Combined Score", disabled=True)
                }
            )
            
            # FIXED: Removed the invalid .to_dataframe() call
            if not edited_pending.equals(grid_pending):
                updated_pending = edited_pending.to_dict(orient="records")
                for item in updated_pending:
                    item["priority"] = map_importance_label(int(item.get("value", 5)))
                
                st.session_state.tasks = updated_pending + completed_df.to_dict(orient="records")
                save_tasks_data()
                st.rerun()
        else:
            st.success("All caught up! No pending tasks left. 🙌")
            
    with tab_completed:
        if not completed_df.empty:
            grid_completed = completed_df[[c for c in cols_order if c in completed_df.columns]]
            edited_completed = st.data_editor(
                grid_completed,
                use_container_width=True,
                hide_index=True,
                key="completed_editor",
                column_config={
                    "completed": st.column_config.CheckboxColumn("Done?", help="Uncheck to reopen task"),
                    "name": st.column_config.TextColumn("Task Name", required=True),
                    "category": st.column_config.SelectboxColumn("Category", options=st.session_state.categories, required=True),
                    "priority": st.column_config.TextColumn("Tier Status", disabled=True),
                    "value": st.column_config.NumberColumn("Importance (1-10)", min_value=1, max_value=10, step=1),
                    "due_date": st.column_config.TextColumn("Due Date (DD-MM-YYYY HH:MM)"),
                    "time required": st.column_config.NumberColumn("Hours Required", min_value=0.1),
                    "urgency": st.column_config.NumberColumn("Urgency Score", disabled=True),
                    "final_score": st.column_config.NumberColumn("Final Combined Score", disabled=True)
                }
            )
            
            if not edited_completed.equals(grid_completed):
                updated_completed = edited_completed.to_dict(orient="records")
                for item in updated_completed:
                    item["priority"] = map_importance_label(int(item.get("value", 5)))
                
                st.session_state.tasks = pending_df.to_dict(orient="records") + updated_completed
                save_tasks_data()
                st.rerun()
        else:
            st.info("Completed tasks will show up archived here!")

    with st.expander("🗑️ Danger Zone - Delete a Task"):
        task_names = [t["name"] for t in st.session_state.tasks]
        if task_names:
            target_to_drop = st.selectbox("Select task to remove completely:", task_names)
            if st.button("Confirm Absolute Deletion", type="primary"):
                st.session_state.tasks = [t for t in st.session_state.tasks if t["name"] != target_to_drop]
                save_tasks_data()
                st.success(f"Vaporized task: '{target_to_drop}'")
                st.rerun()

st.markdown("---")

# ==========================================
# 5. STREAMLIT INPUT FORM (ADD TASK)
# ==========================================
st.header("➕ Add New Task")

with st.form("new_task_form", clear_on_submit=True):
    col_left, col_right = st.columns(2)
    
    with col_left:
        new_name = st.text_input("What needs to be done?", placeholder="e.g., Study for Calculus Exam")
        chosen_cat = st.selectbox("Category Group Assignment", st.session_state.categories)
        custom_cat = st.text_input("🌟 Or type a new category to inject:")
        importance_score = st.slider("Importance Matrix Scale (1=Low, 10=Critical)", min_value=1, max_value=10, value=5)

    with col_right:
        due_day = st.date_input("Target Due Date", value=datetime.now().date())
        # FIXED: Explicitly defaults back to 22:00
        due_time = st.time_input("Target Action Time Deadline", value=datetime.replace(datetime.now(), hour=22, minute=0).time())
        time_qty = st.number_input("Time investment quantity", min_value=0.1, value=1.0, step=0.5)
        time_unit = st.selectbox("Duration unit metrics type", ["Minutes", "Hours", "Days", "Weeks"], index=1)

    submitted_btn = st.form_submit_button("Form Complete - Generate Task Profile")

if submitted_btn:
    if not new_name.strip():
        st.error("Task profile creation blocked: Name string cannot be left blank.")
    else:
        final_category = chosen_cat
        if custom_cat.strip():
            final_category = custom_cat.strip().capitalize()
            if final_category not in st.session_state.categories:
                st.session_state.categories.append(final_category)

        computed_hours = float(time_qty)
        if time_unit == "Minutes": computed_hours /= 60.0
        elif time_unit == "Days": computed_hours *= 24.0
        elif time_unit == "Weeks": computed_hours *= (24.0 * 7.0)

        merged_deadline_str = f"{due_day.strftime('%d-%m-%Y')} {due_time.strftime('%H:%M')}"
        priority_str = map_importance_label(importance_score)

        new_task_payload = {
            "name": new_name.strip(),
            "category": final_category,
            "priority": priority_str,
            "value": int(importance_score),
            "due_date": merged_deadline_str,
            "time required": round(computed_hours, 2),
            "completed": False
        }

        st.session_state.tasks.append(new_task_payload)
        save_tasks_data()
        st.toast(f"Task '{new_name}' logged successfully!", icon="🚀")
        st.rerun()

st.markdown("---")

# ==========================================
# 6. GRAPH VISUALIZATIONS SECTION (Bottom)
# ==========================================
st.header("📊 Visualization Matrix & Breakdowns")

if not raw_df.empty:
    plot_df = raw_df[raw_df["completed"] == False].copy() if "completed" in raw_df else raw_df.copy()
    
    if not plot_df.empty:
        graph_col1, graph_col2 = st.columns([1, 1])
        
        with graph_col1:
            st.subheader("🎯 Priority Matrix Mapping")
            scatter_chart = (
                alt.Chart(plot_df)
                .mark_circle(size=140, opacity=0.85)
                .encode(
                    x=alt.X("urgency:Q", title="Urgency (Time Pressure)", scale=alt.Scale(domain=[0, 10], clamp=True)),
                    y=alt.Y("value:Q", title="Importance (Value)", scale=alt.Scale(domain=[0, 10], clamp=True)),
                    color=alt.Color("category:N", title="Category"),
                    tooltip=[
                        alt.Tooltip("name:N", title="Task"),
                        alt.Tooltip("category:N", title="Category"),
                        alt.Tooltip("due_date:N", title="Due Date"),
                        alt.Tooltip("urgency:Q", title="Urgency Score"),
                        alt.Tooltip("value:Q", title="Importance Value"),
                        alt.Tooltip("final_score:Q", title="Final Weighted Score")
                    ]
                )
                .properties(height=350)
            )
            st.altair_chart(scatter_chart, use_container_width=True)
            
        with graph_col2:
            st.subheader("🍰 Dynamic Proportion Analysis")
            chart_mode = st.radio(
                "Slice chart breakdown data by:",
                options=["Task Categories", "Priority Tier Status"],
                horizontal=True
            )
            
            if chart_mode == "Task Categories":
                pie_chart = (
                    alt.Chart(plot_df)
                    .mark_arc(innerRadius=40)
                    .encode(
                        theta=alt.Theta("count()", type="quantitative"),
                        color=alt.Color("category:N", title="Category"),
                        tooltip=["category:N", "count()"]
                    )
                    .properties(height=300)
                )
            else:
                pie_chart = (
                    alt.Chart(plot_df)
                    .mark_arc(innerRadius=40)
                    .encode(
                        theta=alt.Theta("count()", type="quantitative"),
                        color=alt.Color("priority:N", title="Tier Status", 
                                        sort=["Critical", "Very Important", "Moderate", "Low", "Almost No Value"]),
                        tooltip=["priority:N", "count()"]
                    )
                    .properties(height=300)
                )
            st.altair_chart(pie_chart, use_container_width=True)
    else:
        st.success("No active tasks remaining to map out! 🌟")
else:
    st.info("Charts will construct dynamically here once tasks are logged.")
