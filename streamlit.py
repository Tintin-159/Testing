import json
import os
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

# ==========================================
# 1. CORE BACKEND FUNCTIONS & DATA PERSISTENCE
# ==========================================

DEFAULT_CATEGORIES = ["School", "Work", "Personal", "Study"]


def load_tasks_data():
    """Loads tasks and categories from JSON or initializes them in st.session_state."""
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
    """Saves current state back to the JSON file safely."""
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
    """Calculates an urgency score relative to the current live moment."""
    try:
        due_datetime = datetime.strptime(due_date_str, "%d-%m-%Y %H:%M")
        now = datetime.now()
        time_available = (due_datetime - now).total_seconds() / 3600

        if time_available <= 0:
            return 10.0

        urgency_score = (time_needed_hours / time_available) * 10
        return round(min(10.0, urgency_score), 2)
    except Exception:
        return 0.0


def map_importance_label(value):
    """Maps importance integers back to descriptive text tags."""
    if value >= 9:
        return "Critical"
    elif value >= 7:
        return "Very Important"
    elif value >= 5:
        return "Moderate"
    elif value >= 3:
        return "Low"
    else:
        return "Almost No Value"


# ==========================================
# 2. STREAMLIT APP CONFIG & SETUP
# ==========================================

st.set_page_config(page_title="Task Matrix Manager", page_icon="✅", layout="wide")
load_tasks_data()

st.title("✅ Task Matrix Manager")
st.write("An upgraded priority-driven task tracker built from your terminal core code.")

# ==========================================
# 3. METRICS / STATISTICS SECTION
# ==========================================
st.header("Metrics Dashboard")
if st.session_state.tasks:
    df_metrics = pd.DataFrame(st.session_state.tasks)
    total_tasks = len(df_metrics)
    completed_tasks = df_metrics["completed"].sum() if "completed" in df_metrics else 0
    pending_tasks = total_tasks - completed_tasks

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Tracked", total_tasks)
    col2.metric("Pending Tasks", pending_tasks, delta=f"-{completed_tasks} Completed", delta_color="inverse")

    critical_count = len(df_metrics[df_metrics["priority"] == "Critical"]) if "priority" in df_metrics else 0
    col3.metric("Critical Hazards", critical_count)
else:
    st.info("Add your first task below to populate dashboard metrics!")

st.markdown("---")

# ==========================================
# 4. VIEW & LIVE EDIT TASKS (st.data_editor)
# ==========================================
st.header("Active Workspace")

if st.session_state.tasks:
    # Recalculate Urgency dynamic values right before presenting the grid
    for t in st.session_state.tasks:
        t["urgency"] = calculate_urgency(t["due_date"], t.get("time required", 1.0))

    # Render interactive grid layout
    raw_df = pd.DataFrame(st.session_state.tasks)

    # Re-ordering for visual priority hierarchy
    cols_order = ["completed", "name", "category", "priority", "value", "due_date", "time required", "urgency"]
    raw_df = raw_df[[c for c in cols_order if c in raw_df.columns]]

    st.write("💡 Tip: Double click cells to edit values inline. Mark column checkboxes to complete tasks!")

    edited_df = st.data_editor(
        raw_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "completed": st.column_config.CheckboxColumn("Done?", help="Mark complete"),
            "name": st.column_config.TextColumn("Task Name", required=True),
            "category": st.column_config.SelectboxColumn("Category", options=st.session_state.categories,
                                                         required=True),
            "priority": st.column_config.TextColumn("Tier Status", disabled=True),
            "value": st.column_config.NumberColumn("Importance (1-10)", min_value=1, max_value=10, step=1),
            "due_date": st.column_config.TextColumn("Due Date (DD-MM-YYYY HH:MM)"),
            "time required": st.column_config.NumberColumn("Hours Required", min_value=0.1),
            "urgency": st.column_config.NumberColumn("Calculated Urgency Score", disabled=True)
        }
    )

    # Process modifications done inside the data table grid
    if not edited_df.equals(raw_df):
        # Sync changes and fix text priorities if importance integers were edited manually
        updated_list = edited_df.to_dict(orient="records")
        for item in updated_list:
            item["priority"] = map_importance_label(int(item.get("value", 5)))
        st.session_state.tasks = updated_list
        save_tasks_data()
        st.rerun()

    # Dynamic Task Deletion tool inside sidebar or action tray
    with st.expander("🗑️ Danger Zone - Delete a Task"):
        task_names = [t["name"] for t in st.session_state.tasks]
        target_to_drop = st.selectbox("Select task to remove completely:", task_names)
        if st.button("Confirm Absolute Deletion", type="primary"):
            st.session_state.tasks = [t for t in st.session_state.tasks if t["name"] != target_to_drop]
            save_tasks_data()
            st.success(f"Successfully vaporized task: '{target_to_drop}'")
            st.rerun()
else:
    st.warning("No tasks stored currently.")

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

        # New Category Insertion Option
        custom_cat = st.text_input("🌟 Or type a new category to inject:")

        importance_score = st.slider("Importance Matrix Scale (1=Low, 10=Critical)", min_value=1, max_value=10, value=5)

    with col_right:
        due_day = st.date_input("Target Due Date", value=datetime.now().date())
        due_time = st.time_input("Target Action Time Deadline",
                                 value=datetime.replace(datetime.now(), hour=22, minute=0).time())

        time_qty = st.number_input("Time investment quantity standard unit value", min_value=0.1, value=1.0, step=0.5)
        time_unit = st.selectbox("Duration unit metrics type", ["Minutes", "Hours", "Days", "Weeks"], index=1)

    submitted_btn = st.form_submit_button("Form Complete - Generate Task Profile")

if submitted_btn:
    if not new_name.strip():
        st.error("Task profile creation blocked: Name string cannot be left blank.")
    else:
        # Evaluate Category Injection override
        final_category = chosen_cat
        if custom_cat.strip():
            final_category = custom_cat.strip().capitalize()
            if final_category not in st.session_state.categories:
                st.session_state.categories.append(final_category)

        # Standardize Time Duration values into hours metric
        computed_hours = float(time_qty)
        if time_unit == "Minutes":
            computed_hours /= 60.0
        elif time_unit == "Days":
            computed_hours *= 24.0
        elif time_unit == "Weeks":
            computed_hours *= (24.0 * 7.0)

        # Build execution timestamps
        merged_deadline_str = f"{due_day.strftime('%d-%m-%Y')} {due_time.strftime('%H:%M')}"
        priority_str = map_importance_label(importance_score)
        urgency_score = calculate_urgency(merged_deadline_str, computed_hours)

        # Construct dictionary block
        new_task_payload = {
            "name": new_name.strip(),
            "category": final_category,
            "priority": priority_str,
            "value": int(importance_score),
            "due_date": merged_deadline_str,
            "time required": round(computed_hours, 2),
            "urgency": urgency_score,
            "completed": False
        }

        # Save and Rerun app cycle
        st.session_state.tasks.append(new_task_payload)
        save_tasks_data()
        st.toast(f"Task '{new_name}' logged successfully!", icon="🚀")
        st.rerun()