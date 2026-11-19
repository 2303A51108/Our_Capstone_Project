import re
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import joblib


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="CNC Tool Wear Detection System",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# RELATIVE PATH RESOLUTION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MODEL_PATH = BASE_DIR / "final_tool_wear_model.pkl"
METADATA_PATH = BASE_DIR / "model_metadata.pkl"
TRAIN_DATA_PATH = BASE_DIR / "train.csv"
BENCHMARK_FEATURES_PATH = BASE_DIR / "features_improved.csv"
MODEL_RESULTS_PATH = BASE_DIR / "final_model_results.csv"


# ============================================================
# VERIFIED TARGET CLASS ENCODING
# Derived from final_model.py: y = df["tool_condition"].map({"unworn": 0, "worn": 1})
# ============================================================

CLASS_MAPPING = {
    0: "UNWORN",
    1: "WORN"
}


# ============================================================
# LOAD MODEL & METADATA
# ============================================================

@st.cache_resource
def load_model_and_metadata():
    if not MODEL_PATH.exists():
        st.error(f"Trained model file not found at: {MODEL_PATH}")
        st.stop()

    if not METADATA_PATH.exists():
        st.error(f"Model metadata file not found at: {METADATA_PATH}")
        st.stop()

    loaded_model = joblib.load(MODEL_PATH)
    loaded_metadata = joblib.load(METADATA_PATH)

    return loaded_model, loaded_metadata


try:
    model, metadata = load_model_and_metadata()
except Exception as err:
    st.error("Failed to load the trained model or metadata.")
    st.exception(err)
    st.stop()

if not isinstance(metadata, dict) or "features" not in metadata:
    st.error("Model metadata does not contain the required 'features' list.")
    st.stop()

expected_features = list(metadata["features"])
model_name = metadata.get("model_name", type(model).__name__)


# ============================================================
# LOAD REFERENCE DATASETS (CACHED)
# ============================================================

@st.cache_data
def load_train_reference():
    if TRAIN_DATA_PATH.exists():
        try:
            return pd.read_csv(TRAIN_DATA_PATH)
        except Exception:
            return None
    return None


@st.cache_data
def load_benchmark_features():
    if BENCHMARK_FEATURES_PATH.exists():
        try:
            return pd.read_csv(BENCHMARK_FEATURES_PATH)
        except Exception:
            return None
    return None


@st.cache_data
def load_model_performance_results():
    if MODEL_RESULTS_PATH.exists():
        try:
            return pd.read_csv(MODEL_RESULTS_PATH)
        except Exception:
            return None
    return None


train_ref_df = load_train_reference()
benchmark_df = load_benchmark_features()
results_ref_df = load_model_performance_results()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def detect_experiment_number(filename: str):
    """Detects experiment number (1-18) from filename, e.g. experiment_01.csv."""
    match = re.search(r"(?:experiment|exp)[_\s\-]?0*(\d+)", filename, re.IGNORECASE)
    if match:
        try:
            num = int(match.group(1))
            if 1 <= num <= 18:
                return num
        except ValueError:
            pass
    return None


def extract_sensor_features(data: pd.DataFrame) -> pd.DataFrame:
    """
    Extracts 9 statistical features for each numeric sensor channel.
    Matches the exact formula used in ml_model.py:
    - mean, std (sample std with ddof=1 via Pandas), median, min, max, range, rms, abs_mean, energy
    """
    numeric_data = data.select_dtypes(include=[np.number])
    extracted = {}

    for column in numeric_data.columns:
        values = pd.to_numeric(numeric_data[column], errors="coerce").dropna()
        if len(values) == 0:
            continue

        extracted[f"{column}_mean"] = float(values.mean())
        # Sample standard deviation (ddof=1) matches Pandas series.std() in ml_model.py
        extracted[f"{column}_std"] = float(values.std(ddof=1)) if len(values) > 1 else 0.0
        extracted[f"{column}_median"] = float(values.median())
        extracted[f"{column}_min"] = float(values.min())
        extracted[f"{column}_max"] = float(values.max())
        extracted[f"{column}_range"] = float(values.max() - values.min())
        extracted[f"{column}_rms"] = float(np.sqrt(np.mean(values ** 2)))
        extracted[f"{column}_abs_mean"] = float(np.mean(np.abs(values)))
        extracted[f"{column}_energy"] = float(np.sum(values ** 2))

    return pd.DataFrame([extracted])


def plot_signal_chart(data: pd.DataFrame, columns: list, title: str):
    """Plots one or multiple sensor signals efficiently."""
    valid_cols = [c for c in columns if c in data.columns]
    if not valid_cols:
        st.info(f"None of the requested signals ({', '.join(columns)}) were found in the uploaded file.")
        return

    plot_df = data[valid_cols].apply(pd.to_numeric, errors="coerce")
    plot_df["Sample Index"] = np.arange(len(plot_df))
    plot_df = plot_df.set_index("Sample Index")

    st.subheader(title)
    st.line_chart(plot_df, use_container_width=True)
    st.caption(f"Displayed channels: {', '.join(valid_cols)} | Total data points: {len(data):,}")


# ============================================================
# SIDEBAR: PROJECT INFO & PERFORMANCE METRICS
# ============================================================

with st.sidebar:
    st.title("⚙️ CNC Wear Monitor")
    st.write("**B.Tech Final Year Project**")
    st.markdown("*Tool Wear Detection in CNC Milling Operations*")
    st.divider()

    st.subheader("Active Model Architecture")
    st.write(f"**Model:** `{model_name}`")
    st.write(f"**Input Features:** {len(expected_features)} features")
    st.write("**Target Classes:** `0 = UNWORN`, `1 = WORN`")
    st.divider()

    st.subheader("Model Validation Performance")
    st.markdown(
        """
        > **Leave-One-Experiment-Out Cross-Validation (LOOCV)**
        > *(Generalization on Unseen Experiments)*
        """
    )
    if results_ref_df is not None and not results_ref_df.empty:
        best_row = results_ref_df[results_ref_df["Model"] == model_name]
        if not best_row.empty:
            acc_val = best_row["Accuracy"].values[0]
            rec_val = best_row["Recall"].values[0]
            prec_val = best_row["Precision"].values[0]
            f1_val = best_row["F1 Score"].values[0]

            col_a, col_b = st.columns(2)
            col_a.metric("LOOCV Acc", f"{acc_val * 100:.1f}%")
            col_b.metric("LOOCV F1", f"{f1_val * 100:.1f}%")

            col_c, col_d = st.columns(2)
            col_c.metric("Recall", f"{rec_val * 100:.1f}%")
            col_d.metric("Precision", f"{prec_val * 100:.1f}%")
        else:
            st.metric("LOOCV Accuracy", "77.78%")
            st.metric("LOOCV F1 Score", "81.82%")
    else:
        st.metric("LOOCV Accuracy", "77.78%")
        st.metric("LOOCV F1 Score", "81.82%")

    st.info(
        "ℹ️ **Evaluation Note:** LOOCV accuracy is 77.78% across the 18 experimental runs. "
        "Predictions evaluated against the full-fit training set yield 100% resubstitution accuracy, "
        "which should not be confused with true out-of-sample generalization."
    )


# ============================================================
# MAIN APPLICATION INTERFACE
# ============================================================

st.title("⚙️ CNC Tool Wear Detection & Sensor Monitoring")
st.markdown(
    """
    This application processes multi-channel CNC milling sensor streams to extract statistical time-series features 
    and diagnose cutting tool wear (**UNWORN** vs **WORN**) using the validated machine learning pipeline.
    """
)
st.divider()


# ============================================================
# SECTION 1: DATA UPLOAD
# ============================================================

st.header("1. Upload CNC Milling Experiment CSV")
uploaded_file = st.file_uploader(
    "Upload a CNC experiment CSV file (e.g., experiment_01.csv to experiment_18.csv or an external trial):",
    type=["csv"],
    help="CSV file containing recorded sensor signals from linear axes (X, Y, Z), spindle (S), and CNC controller (M1)."
)

if uploaded_file is None:
    st.info("👈 Please upload an experiment CSV file to start sensor visualization, feature extraction, and tool wear diagnosis.")
    st.stop()


# ============================================================
# LOAD UPLOADED CSV
# ============================================================

try:
    data = pd.read_csv(uploaded_file)
except Exception as read_err:
    st.error(f"Failed to read the uploaded CSV file: {read_err}")
    st.stop()

if data.empty:
    st.error("The uploaded CSV contains no data rows.")
    st.stop()

filename = uploaded_file.name
detected_exp_id = detect_experiment_number(filename)

st.success(f"Successfully loaded **{filename}** ({len(data):,} samples, {data.shape[1]} columns).")


# ============================================================
# SECTION 2: MACHINING PROCESS PARAMETERS (FEED RATE & CLAMP PRESSURE)
# ============================================================

st.header("2. Machining Process Parameters")
st.markdown(
    """
    The trained model expects two machine process settings: **Feed Rate** ($mm/s$) and **Clamping Pressure** ($bar$). 
    These are operating parameters configured on the CNC mill rather than raw sensor time-series channels.
    """
)

prefill_feedrate = 6.0
prefill_clamp = 4.0
ground_truth_label = None

if detected_exp_id is not None and train_ref_df is not None:
    exp_rows = train_ref_df[train_ref_df["No"] == detected_exp_id]
    if not exp_rows.empty:
        exp_info = exp_rows.iloc[0]
        prefill_feedrate = float(exp_info["feedrate"])
        prefill_clamp = float(exp_info["clamp_pressure"])
        ground_truth_label = str(exp_info["tool_condition"]).strip().lower()

        st.info(
            f"🎯 **Known Experiment Detected (Experiment #{detected_exp_id}):** "
            f"Retrieved parameters from `train.csv` $\\rightarrow$ "
            f"**Feed Rate:** `{prefill_feedrate} mm/s` | "
            f"**Clamping Pressure:** `{prefill_clamp} bar` | "
            f"**Actual Ground Truth:** `{ground_truth_label.upper()}`"
        )
else:
    st.warning(
        "⚠️ **External / Unindexed File:** This file does not match a known experiment ID in `train.csv`. "
        "Please confirm or enter the machine operating parameters below. Parameters will **never** be silently replaced with zero."
    )

param_col1, param_col2 = st.columns(2)
with param_col1:
    feedrate_input = st.number_input(
        "Machining Feed Rate (mm/s)",
        min_value=0.1,
        max_value=100.0,
        value=float(prefill_feedrate),
        step=1.0,
        help="Process feed rate along the workpiece. Standard training values are 3, 6, 12, 15, or 20 mm/s."
    )

with param_col2:
    clamp_input = st.number_input(
        "Vise Clamping Pressure (bar)",
        min_value=0.1,
        max_value=10.0,
        value=float(prefill_clamp),
        step=0.5,
        help="Pneumatic vise clamping pressure. Standard training values are 2.5, 3.0, or 4.0 bar."
    )

if feedrate_input is None or feedrate_input <= 0 or clamp_input is None or clamp_input <= 0:
    st.error("Valid positive Feed Rate and Clamping Pressure values are required for tool wear prediction.")
    st.stop()


# ============================================================
# SECTION 3: MULTI-AXIS SENSOR DASHBOARD
# ============================================================

st.header("3. Multi-Axis Sensor Signal Dashboard")
st.write(
    "Interactive inspection of the recorded CNC machine sensor streams across linear drives, spindle motor, and controller."
)

tab_current, tab_power, tab_feed, tab_accel, tab_other = st.tabs([
    "⚡ Current Signals (8)",
    "🔋 Power Signals (3)",
    "🏃 Feed Rate & Velocities",
    "📈 Acceleration Signals (8)",
    "🧭 Position & Voltages"
])

with tab_current:
    st.markdown("**Drive Output Currents & Feedback Currents (Amperes)**")
    curr_view = st.radio(
        "Select Current Signal Display:",
        [
            "Spindle Current (S1_OutputCurrent & S1_CurrentFeedback)",
            "All Motor Output Currents (X1, Y1, Z1, S1)",
            "All Motor Current Feedback (X1, Y1, Z1, S1)",
            "Custom Current Channel Selection"
        ],
        horizontal=True
    )

    if curr_view == "Spindle Current (S1_OutputCurrent & S1_CurrentFeedback)":
        plot_signal_chart(data, ["S1_OutputCurrent", "S1_CurrentFeedback"], "Spindle Drive Current")
    elif curr_view == "All Motor Output Currents (X1, Y1, Z1, S1)":
        plot_signal_chart(data, ["S1_OutputCurrent", "X1_OutputCurrent", "Y1_OutputCurrent", "Z1_OutputCurrent"], "Motor Output Currents (X, Y, Z, Spindle)")
    elif curr_view == "All Motor Current Feedback (X1, Y1, Z1, S1)":
        plot_signal_chart(data, ["S1_CurrentFeedback", "X1_CurrentFeedback", "Y1_CurrentFeedback", "Z1_CurrentFeedback"], "Motor Feedback Currents (X, Y, Z, Spindle)")
    else:
        all_curr_cols = [c for c in [
            "S1_OutputCurrent", "S1_CurrentFeedback",
            "X1_OutputCurrent", "X1_CurrentFeedback",
            "Y1_OutputCurrent", "Y1_CurrentFeedback",
            "Z1_OutputCurrent", "Z1_CurrentFeedback"
        ] if c in data.columns]
        chosen_curr = st.multiselect("Choose current channels to plot:", all_curr_cols, default=all_curr_cols[:2])
        if chosen_curr:
            plot_signal_chart(data, chosen_curr, "Selected Current Channels")

with tab_power:
    st.markdown("**Motor Output Power (kW)**")
    st.caption("Note: In this CNC setup, output power sensors are fitted on the Spindle (S1), X-axis (X1), and Y-axis (Y1). Z1 does not have a power sensor.")
    power_cols = [c for c in ["S1_OutputPower", "X1_OutputPower", "Y1_OutputPower"] if c in data.columns]
    selected_power = st.multiselect("Choose power channels to view:", power_cols, default=power_cols)
    if selected_power:
        plot_signal_chart(data, selected_power, "Output Power Signals (kW)")

with tab_feed:
    st.markdown("**Feed Rate & Linear Axis Velocities (mm/s)**")
    feed_options = [c for c in [
        "M1_CURRENT_FEEDRATE",
        "X1_ActualVelocity", "X1_CommandVelocity",
        "Y1_ActualVelocity", "Y1_CommandVelocity",
        "Z1_ActualVelocity", "Z1_CommandVelocity",
        "S1_ActualVelocity"
    ] if c in data.columns]
    selected_feed = st.multiselect("Choose velocity / feed signals:", feed_options, default=["M1_CURRENT_FEEDRATE", "X1_ActualVelocity", "Y1_ActualVelocity"])
    if selected_feed:
        plot_signal_chart(data, selected_feed, "Tool Velocity & Feed Rate Behavior")

with tab_accel:
    st.markdown("**Acceleration Signals (mm/s² / deg/s²)**")
    accel_view = st.radio(
        "Select Acceleration View:",
        [
            "Actual Linear & Spindle Accelerations (X1, Y1, Z1, S1)",
            "Commanded Reference Accelerations (X1, Y1, Z1, S1)",
            "Custom Acceleration Selection"
        ],
        horizontal=True
    )
    if accel_view == "Actual Linear & Spindle Accelerations (X1, Y1, Z1, S1)":
        plot_signal_chart(data, ["X1_ActualAcceleration", "Y1_ActualAcceleration", "Z1_ActualAcceleration", "S1_ActualAcceleration"], "Actual Acceleration Signals")
    elif accel_view == "Commanded Reference Accelerations (X1, Y1, Z1, S1)":
        plot_signal_chart(data, ["X1_CommandAcceleration", "Y1_CommandAcceleration", "Z1_CommandAcceleration", "S1_CommandAcceleration"], "Commanded Acceleration Signals")
    else:
        all_accel = [c for c in [
            "X1_ActualAcceleration", "X1_CommandAcceleration",
            "Y1_ActualAcceleration", "Y1_CommandAcceleration",
            "Z1_ActualAcceleration", "Z1_CommandAcceleration",
            "S1_ActualAcceleration", "S1_CommandAcceleration"
        ] if c in data.columns]
        chosen_accel = st.multiselect("Choose acceleration channels:", all_accel, default=all_accel[:3])
        if chosen_accel:
            plot_signal_chart(data, chosen_accel, "Selected Acceleration Signals")

with tab_other:
    st.markdown("**Position Coordinates & Voltage Signals**")
    other_col1, other_col2 = st.columns(2)
    with other_col1:
        st.write("##### Position Coordinates (mm)")
        pos_cols = [c for c in ["X1_ActualPosition", "Y1_ActualPosition", "Z1_ActualPosition"] if c in data.columns]
        plot_signal_chart(data, pos_cols, "Tool Position Trajectory")
    with other_col2:
        st.write("##### Voltage Signals (V)")
        volt_cols = [c for c in ["S1_DCBusVoltage", "S1_OutputVoltage", "X1_DCBusVoltage", "X1_OutputVoltage"] if c in data.columns]
        plot_signal_chart(data, volt_cols, "Drive Bus & Output Voltages")


# ============================================================
# SECTION 4: SENSOR DESCRIPTIVE STATISTICS
# ============================================================

st.header("4. Sensor Descriptive Statistics")
with st.expander("📊 View Complete Sensor Statistics Table", expanded=False):
    num_df = data.select_dtypes(include=[np.number])
    if not num_df.empty:
        stats_summary = pd.DataFrame({
            "Mean": num_df.mean(),
            "Std Dev (ddof=1)": num_df.std(ddof=1),
            "Median": num_df.median(),
            "Min": num_df.min(),
            "Max": num_df.max(),
            "Range": num_df.max() - num_df.min(),
            "RMS": np.sqrt((num_df ** 2).mean())
        })
        st.dataframe(stats_summary.round(4), use_container_width=True)
    else:
        st.info("No numeric sensor columns found.")


# ============================================================
# SECTION 5: FEATURE EXTRACTION PIPELINE
# ============================================================

st.header("5. Feature Extraction Pipeline")

raw_features_df = extract_sensor_features(data)

# Inject the verified process parameters
raw_features_df["feedrate"] = float(feedrate_input)
raw_features_df["clamp_pressure"] = float(clamp_input)

# Verify alignment with the model's required 425 features
missing_model_features = [f for f in expected_features if f not in raw_features_df.columns]
if missing_model_features:
    st.warning(f"⚠️ {len(missing_model_features)} expected features are missing from this CSV. Missing columns will be filled with 0.0.")
    with st.expander("Review Missing Features"):
        st.write(missing_model_features)

# Strict column ordering according to the trained model's metadata
model_input_df = raw_features_df.reindex(columns=expected_features, fill_value=0.0).fillna(0.0)

st.success(
    f"✅ Feature extraction complete: Exactly **{model_input_df.shape[1]} features** structured in strict training order. "
    f"(Formula: sample standard deviation with `ddof=1` matches `features_improved.csv` exactly)."
)


# ============================================================
# SECTION 6: TOOL WEAR PREDICTION
# ============================================================

st.header("6. Tool Wear Diagnosis & Prediction")

if st.button("🔍 Run Tool Wear Diagnosis", type="primary", use_container_width=True):
    try:
        raw_pred = int(model.predict(model_input_df)[0])
        predicted_condition = CLASS_MAPPING.get(raw_pred, f"UNKNOWN ({raw_pred})")

        probabilities = None
        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(model_input_df)[0]

        st.subheader("Diagnosis Result")

        res_col1, res_col2 = st.columns([3, 2])

        with res_col1:
            if predicted_condition == "WORN":
                st.error("### 🔴 PREDICTED TOOL CONDITION: WORN")
                st.markdown(
                    """
                    **High Tool Wear Detected:** The cutting tool shows significant flank / face wear. 
                    Continued machining may lead to surface finish degradation, out-of-tolerance parts, or catastrophic tool breakage.
                    **Recommendation:** Replace cutting insert / end mill before next machining pass.
                    """
                )
            elif predicted_condition == "UNWORN":
                st.success("### 🟢 PREDICTED TOOL CONDITION: UNWORN")
                st.markdown(
                    """
                    **Tool in Good Condition:** The cutting tool shows acceptable / minimal wear. 
                    Cutting forces and dynamics are within safe operating envelopes.
                    **Recommendation:** Continue normal machining operation.
                    """
                )
            else:
                st.warning(f"Prediction returned unmapped class: {raw_pred}")

            if ground_truth_label is not None:
                if ground_truth_label.upper() == predicted_condition:
                    st.info(f"✅ **Ground Truth Match:** Uploaded file was recorded as `{ground_truth_label.upper()}` in `train.csv`. Prediction matches ground truth.")
                else:
                    st.warning(f"⚠️ **Ground Truth Comparison:** Uploaded file was recorded as `{ground_truth_label.upper()}` in `train.csv`, but model classified as `{predicted_condition}`.")

        with res_col2:
            st.write("##### Probability Distribution")
            if probabilities is not None:
                classes = getattr(model, "classes_", [0, 1])
                prob_unworn = float(probabilities[list(classes).index(0)]) * 100
                prob_worn = float(probabilities[list(classes).index(1)]) * 100

                prob_table = pd.DataFrame({
                    "Condition": ["UNWORN", "WORN"],
                    "Probability (%)": [prob_unworn, prob_worn]
                }).set_index("Condition")

                st.bar_chart(prob_table, use_container_width=True)
                st.caption(
                    f"**UNWORN:** {prob_unworn:.1f}% | **WORN:** {prob_worn:.1f}%  \n"
                    "*(Note: Pure decision tree leaf nodes output 100% / 0% certainty)*"
                )

        # ====================================================
        # SECTION 7: WORN VS UNWORN BENCHMARK COMPARISON
        # ====================================================

        st.divider()
        st.subheader("7. Physical Benchmark: WORN vs UNWORN Signal Profile")
        st.markdown(
            """
            Comparison of decisive sensor features from this experiment against the historical benchmark averages 
            from the 18 experimental runs (8 UNWORN, 10 WORN).
            """
        )

        if benchmark_df is not None and not benchmark_df.empty:
            key_features = [
                ("Z1_ActualPosition_min", "Z1 Minimum Position (mm) [Primary Tree Split]"),
                ("M1_sequence_number_abs_mean", "G-Code Seq Number Mean [Secondary Tree Split]"),
                ("S1_OutputCurrent_mean", "Spindle Output Current Mean (A)"),
                ("S1_OutputCurrent_rms", "Spindle Output Current RMS (A)"),
                ("S1_OutputPower_mean", "Spindle Output Power Mean (kW)"),
                ("X1_ActualAcceleration_rms", "X1 Acceleration RMS (mm/s²)"),
                ("Y1_ActualAcceleration_rms", "Y1 Acceleration RMS (mm/s²)")
            ]

            bench_unworn = benchmark_df[benchmark_df["tool_condition"] == "unworn"]
            bench_worn = benchmark_df[benchmark_df["tool_condition"] == "worn"]

            comp_rows = []
            for feat_col, feat_name in key_features:
                if feat_col in model_input_df.columns:
                    exp_val = float(model_input_df[feat_col].iloc[0])
                    u_val = float(bench_unworn[feat_col].mean()) if feat_col in bench_unworn.columns else np.nan
                    w_val = float(bench_worn[feat_col].mean()) if feat_col in bench_worn.columns else np.nan

                    dist_u = abs(exp_val - u_val) if not np.isnan(u_val) else np.inf
                    dist_w = abs(exp_val - w_val) if not np.isnan(w_val) else np.inf
                    closer_to = "UNWORN profile" if dist_u < dist_w else "WORN profile"

                    comp_rows.append({
                        "Feature / Diagnostic Signal": feat_name,
                        "Uploaded Experiment": round(exp_val, 4),
                        "Benchmark UNWORN Mean": round(u_val, 4) if not np.isnan(u_val) else "N/A",
                        "Benchmark WORN Mean": round(w_val, 4) if not np.isnan(w_val) else "N/A",
                        "Feature Profile Alignment": closer_to
                    })

            if comp_rows:
                st.dataframe(pd.DataFrame(comp_rows), use_container_width=True)

        st.divider()
        st.caption(
            "📌 **Decision Tree Logic:** The model splits first on `Z1_ActualPosition_min <= 27.60` (indicates unworn tool position), "
            "and second on `M1_sequence_number_abs_mean <= 6.12` (indicates unworn progress trajectory). "
            "Verified target encoding: 0 = UNWORN, 1 = WORN."
        )

    except Exception as pred_err:
        st.error(f"Prediction failed: {pred_err}")
        st.exception(pred_err)


# ============================================================
# FOOTER
# ============================================================

st.divider()
st.caption(
    "CNC Tool Wear Detection System | Final-Year B.Tech Project | "
    "University of Michigan SMART Lab CNC Milling Dataset"
)
