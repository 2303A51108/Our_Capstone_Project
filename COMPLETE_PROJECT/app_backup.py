import streamlit as st
import pandas as pd
import numpy as np
import joblib
from pathlib import Path


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="CNC Tool Wear Detection",
    page_icon="⚙️",
    layout="wide"
)


# ============================================================
# MODEL FILE PATHS
# Keep both model files in the same folder as app.py
# ============================================================

MODEL_PATH = Path("final_tool_wear_model.pkl")
METADATA_PATH = Path("model_metadata.pkl")


# ============================================================
# CHECK MODEL FILES
# ============================================================

if not MODEL_PATH.exists():
    st.error(
        f"Model file not found: {MODEL_PATH.resolve()}"
    )
    st.stop()

if not METADATA_PATH.exists():
    st.error(
        f"Metadata file not found: {METADATA_PATH.resolve()}"
    )
    st.stop()


# ============================================================
# LOAD MODEL
# ============================================================

@st.cache_resource
def load_model_and_metadata():

    loaded_model = joblib.load(MODEL_PATH)
    loaded_metadata = joblib.load(METADATA_PATH)

    return loaded_model, loaded_metadata


try:

    model, metadata = load_model_and_metadata()

except Exception as error:

    st.error("Unable to load the trained model or metadata.")
    st.exception(error)
    st.stop()


if not isinstance(metadata, dict):
    st.error("Invalid model metadata format.")
    st.stop()

if "features" not in metadata:
    st.error("The metadata does not contain expected features.")
    st.stop()


expected_features = list(metadata["features"])

model_name = metadata.get(
    "model_name",
    type(model).__name__
)


if not expected_features:
    st.error("No expected model features were found.")
    st.stop()


# ============================================================
# FEATURE EXTRACTION
# ============================================================

def extract_features(data):

    numeric_data = data.select_dtypes(
        include=[np.number]
    )

    features = {}

    for column in numeric_data.columns:

        values = pd.to_numeric(
            numeric_data[column],
            errors="coerce"
        ).dropna().to_numpy(dtype=float)

        if len(values) == 0:
            continue

        features[f"{column}_mean"] = np.mean(values)

        features[f"{column}_std"] = np.std(values)

        features[f"{column}_median"] = np.median(values)

        features[f"{column}_min"] = np.min(values)

        features[f"{column}_max"] = np.max(values)

        features[f"{column}_range"] = (
            np.max(values) - np.min(values)
        )

        features[f"{column}_rms"] = np.sqrt(
            np.mean(values ** 2)
        )

        features[f"{column}_abs_mean"] = np.mean(
            np.abs(values)
        )

        features[f"{column}_energy"] = np.sum(
            values ** 2
        )

    return pd.DataFrame([features])


# ============================================================
# FIND SENSOR COLUMNS
# ============================================================

def find_column(data, possible_names):

    for name in possible_names:

        if name in data.columns:
            return name

    return None


def find_acceleration_columns(data):

    return [
        column
        for column in data.columns
        if (
            "acceleration" in column.lower()
            or "accel" in column.lower()
        )
    ]


# ============================================================
# DISPLAY SENSOR GRAPHS
# ============================================================

def show_signal(data, column, title):

    values = pd.to_numeric(
        data[column],
        errors="coerce"
    ).dropna()

    if values.empty:

        st.info(
            f"No numeric values available for {column}."
        )
        return

    chart_data = pd.DataFrame({

        "Sample": np.arange(len(values)),

        column: values.to_numpy()

    }).set_index("Sample")

    st.subheader(title)

    st.line_chart(
        chart_data,
        use_container_width=True
    )

    st.caption(
        f"Sensor column: {column} | "
        f"Valid samples: {len(values)}"
    )


# ============================================================
# CLASS LABEL MAPPING
# ============================================================

def normalize_label(value):

    text = str(value).strip().lower()

    if text in {"worn", "wear", "1", "true"}:
        return "WORN"

    if text in {"unworn", "not worn", "0", "false"}:
        return "UNWORN"

    return None


def get_metadata_label_mapping(meta):

    for key in (
        "label_mapping",
        "class_mapping",
        "target_mapping"
    ):

        mapping = meta.get(key)

        if isinstance(mapping, dict):

            normalized = {}

            for class_value, label in mapping.items():

                condition = normalize_label(label)

                if condition:

                    normalized[class_value] = condition
                    normalized[str(class_value)] = condition

            if normalized:
                return normalized

    return {}


def class_to_condition(class_value, mapping):

    if class_value in mapping:
        return mapping[class_value]

    if str(class_value) in mapping:
        return mapping[str(class_value)]

    direct_label = normalize_label(class_value)

    if direct_label in {"WORN", "UNWORN"}:
        return direct_label

    # Fallback convention from the original application.
    # Verify this against the actual training label encoding.

    if isinstance(
        class_value,
        (int, np.integer, float, np.floating)
    ):

        if class_value == 1:
            return "WORN"

        if class_value == 0:
            return "UNWORN"

    return f"CLASS {class_value}"


# ============================================================
# PAGE HEADER
# ============================================================

st.title("⚙️ CNC Tool Wear Detection System")

st.markdown(
    """
    **Machine Learning Based CNC Tool-Condition Monitoring System**

    Upload a CNC machining experiment CSV file to:

    - Analyze CNC machine sensor signals.
    - Visualize current, power and feed-rate behavior.
    - Analyze acceleration signals.
    - Calculate statistical sensor features.
    - Predict whether the cutting tool is WORN or UNWORN.
    """
)

st.divider()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Project Information")

    st.write("**Application:** CNC Tool Wear Detection")

    st.write("**Best Model:**")
    st.write(model_name)

    st.write("**Input:** CNC sensor experiment CSV")

    st.write("**Feature Extraction:** Statistical features")

    st.write("**Output:** WORN / UNWORN")

    st.divider()

    st.info(
        "The prediction is generated using statistical "
        "features extracted from the uploaded CNC sensor data."
    )


# ============================================================
# FILE UPLOAD
# ============================================================

st.header("1. Upload CNC Experiment Data")

uploaded_file = st.file_uploader(
    "Choose an experiment CSV file",
    type=["csv"]
)


# ============================================================
# PROCESS UPLOADED FILE
# ============================================================

if uploaded_file is not None:

    try:

        data = pd.read_csv(uploaded_file)

        if data.empty:

            st.error("The uploaded CSV contains no data rows.")
            st.stop()

        st.success(
            f"File uploaded successfully: {uploaded_file.name}"
        )


        # ====================================================
        # DATASET INFORMATION
        # ====================================================

        st.subheader("Dataset Information")

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.metric(
                "Rows",
                f"{data.shape[0]:,}"
            )

        with col2:

            st.metric(
                "Columns",
                data.shape[1]
            )

        with col3:

            st.metric(
                "Numeric Columns",
                data.select_dtypes(
                    include=[np.number]
                ).shape[1]
            )

        with col4:

            st.metric(
                "Missing Values",
                int(data.isna().sum().sum())
            )


        # ====================================================
        # DATA PREVIEW
        # ====================================================

        with st.expander("View Uploaded Data"):

            st.dataframe(
                data.head(10),
                use_container_width=True
            )


        # ====================================================
        # CNC SENSOR ANALYSIS
        # ====================================================

        st.header("2. CNC Sensor Analysis")

        st.write(
            "The graphs below display the actual recorded "
            "sensor and process signals from the experiment."
        )


        # ====================================================
        # CURRENT
        # ====================================================

        current_col = find_column(
            data,
            [
                "S1_OutputCurrent",
                "S1_CurrentFeedback",
                "X1_OutputCurrent",
                "X1_CurrentFeedback",
                "Y1_OutputCurrent",
                "Y1_CurrentFeedback",
                "Z1_OutputCurrent",
                "Z1_CurrentFeedback"
            ]
        )

        if current_col is not None:

            show_signal(
                data,
                current_col,
                "Spindle / Current Behavior"
            )

        else:

            st.info(
                "Current sensor column was not found."
            )


        # ====================================================
        # POWER
        # ====================================================

        power_col = find_column(
            data,
            [
                "S1_OutputPower",
                "X1_OutputPower",
                "Y1_OutputPower"
            ]
        )

        if power_col is not None:

            show_signal(
                data,
                power_col,
                "Power Behavior"
            )

        else:

            st.info(
                "Power sensor column was not found."
            )


        # ====================================================
        # FEED RATE
        # ====================================================

        feed_col = find_column(
            data,
            [
                "M1_CURRENT_FEEDRATE",
                "Current_Feedrate",
                "feedrate",
                "Feedrate"
            ]
        )

        if feed_col is not None:

            show_signal(
                data,
                feed_col,
                "Feed Rate"
            )

        else:

            st.info(
                "Feed-rate column was not found."
            )


        # ====================================================
        # ACCELERATION
        # ====================================================

        st.subheader("Acceleration Behavior")

        acceleration_columns = find_acceleration_columns(data)

        selected_acceleration = []

        for desired_column in [
            "X1_ActualAcceleration",
            "Y1_ActualAcceleration",
            "Z1_ActualAcceleration"
        ]:

            if desired_column in data.columns:

                selected_acceleration.append(
                    desired_column
                )

        if not selected_acceleration:

            selected_acceleration = acceleration_columns[:3]

        if selected_acceleration:

            for column in selected_acceleration:

                show_signal(
                    data,
                    column,
                    column
                )

        else:

            st.info(
                "Acceleration sensor columns were not found."
            )


        # ====================================================
        # OTHER NUMERIC SENSOR SIGNALS
        # ====================================================

        st.subheader("Other CNC Sensor Signals")

        excluded_columns = set()

        for column in [
            current_col,
            power_col,
            feed_col
        ]:

            if column is not None:
                excluded_columns.add(column)

        excluded_columns.update(
            acceleration_columns
        )

        numeric_columns = data.select_dtypes(
            include=[np.number]
        ).columns.tolist()

        remaining_columns = [
            column
            for column in numeric_columns
            if column not in excluded_columns
        ]

        if remaining_columns:

            selected_column = st.selectbox(
                "Select another sensor/process signal",
                remaining_columns
            )

            show_signal(
                data,
                selected_column,
                selected_column
            )

        else:

            st.info(
                "No additional numeric sensor signals found."
            )


        # ====================================================
        # SENSOR STATISTICS
        # ====================================================

        st.header("3. Sensor Statistics")

        numeric_data = data.select_dtypes(
            include=[np.number]
        )

        if not numeric_data.empty:

            statistics = pd.DataFrame({

                "Mean": numeric_data.mean(),

                "Standard Deviation": numeric_data.std(),

                "Minimum": numeric_data.min(),

                "Maximum": numeric_data.max(),

                "Range": (
                    numeric_data.max()
                    - numeric_data.min()
                ),

                "RMS": np.sqrt(
                    (numeric_data ** 2).mean()
                )

            })

            st.dataframe(
                statistics.round(4),
                use_container_width=True
            )

        else:

            st.info(
                "No numeric columns available for statistics."
            )


        # ====================================================
        # FEATURE EXTRACTION
        # ====================================================

        st.header("4. Feature Extraction")

        feature_data = extract_features(data)

        missing_features = [

            feature
            for feature in expected_features
            if feature not in feature_data.columns

        ]

        # Add missing expected features to maintain
        # the trained model's required input structure.

        for feature in missing_features:

            feature_data[feature] = 0.0

        # Maintain exactly the feature order expected
        # by the saved trained model.

        feature_data = feature_data.reindex(
            columns=expected_features,
            fill_value=0.0
        )

        feature_data = feature_data.replace(
            [np.inf, -np.inf],
            np.nan
        ).fillna(0.0)

        st.success(
            f"{feature_data.shape[1]} features prepared for prediction."
        )

        if missing_features:

            with st.expander(
                f"Review {len(missing_features)} missing model features"
            ):

                st.warning(
                    "Some expected model features were not present "
                    "in this CSV. They were filled with zero. "
                    "This may affect prediction reliability."
                )

                st.write(missing_features)


        # ====================================================
        # TOOL WEAR PREDICTION
        # ====================================================

        st.header("5. Tool Wear Prediction")

        if st.button(
            "🔍 Detect Tool Condition",
            type="primary",
            use_container_width=True
        ):

            try:

                prediction = model.predict(
                    feature_data
                )[0]

                probabilities = None

                if hasattr(model, "predict_proba"):

                    probabilities = model.predict_proba(
                        feature_data
                    )[0]

                metadata_mapping = get_metadata_label_mapping(
                    metadata
                )

                predicted_condition = class_to_condition(
                    prediction,
                    metadata_mapping
                )


                # ============================================
                # PREDICTION RESULT
                # ============================================

                st.subheader("Prediction Result")

                if predicted_condition == "WORN":

                    st.error(
                        "🔴 TOOL CONDITION: WORN"
                    )

                    st.warning(
                        "The model predicts that the cutting "
                        "tool is worn."
                    )

                elif predicted_condition == "UNWORN":

                    st.success(
                        "🟢 TOOL CONDITION: UNWORN"
                    )

                    st.success(
                        "The model predicts that the cutting "
                        "tool is unworn."
                    )

                else:

                    st.error(
                        f"Model returned {prediction!r}, but its "
                        "tool-condition meaning could not be identified. "
                        "Check the training label encoding."
                    )


                # ============================================
                # PROBABILITY BREAKDOWN
                # ============================================

                if probabilities is not None:

                    model_classes = getattr(
                        model,
                        "classes_",
                        None
                    )

                    if (
                        model_classes is not None
                        and len(model_classes) == len(probabilities)
                    ):

                        probability_rows = []

                        for class_value, probability_value in zip(
                            model_classes,
                            probabilities
                        ):

                            condition = class_to_condition(
                                class_value,
                                metadata_mapping
                            )

                            probability_rows.append({

                                "Tool Condition": condition,

                                "Probability (%)": (
                                    float(probability_value) * 100
                                )

                            })

                        probability_df = pd.DataFrame(
                            probability_rows
                        )

                        st.subheader(
                            "Prediction Probability Breakdown"
                        )

                        st.bar_chart(
                            probability_df.set_index(
                                "Tool Condition"
                            ),
                            use_container_width=True
                        )

                        predicted_index = list(
                            model_classes
                        ).index(prediction)

                        predicted_probability = float(
                            probabilities[predicted_index]
                        )

                        st.metric(
                            "Probability for Predicted Class",
                            f"{predicted_probability * 100:.2f}%"
                        )

                        st.caption(
                            "This is the model's estimated class "
                            "probability, not a guarantee of correctness."
                        )

                    else:

                        st.warning(
                            "The model returned probabilities, but "
                            "its class labels could not be aligned."
                        )


                # ============================================
                # SENSOR INTERPRETATION
                # ============================================

                st.subheader(
                    "Sensor Analysis Interpretation"
                )

                st.write(
                    f"The trained {model_name} model classified "
                    f"this experiment as **{predicted_condition}**."
                )

                st.write(
                    "Review current, power, feed-rate and acceleration "
                    "signals together with the machining conditions. "
                    "Changes in these signals can also be influenced "
                    "by material, feed rate, machining phase and other "
                    "operating conditions. A signal change alone does "
                    "not independently confirm tool wear."
                )


                # ============================================
                # PREDICTION DETAILS
                # ============================================

                st.divider()

                st.subheader("Prediction Details")

                result_col1, result_col2 = st.columns(2)

                with result_col1:

                    st.write(
                        f"**Model:** {model_name}"
                    )

                with result_col2:

                    st.write(
                        f"**Features used:** {len(expected_features)}"
                    )

                if missing_features:

                    st.warning(
                        f"{len(missing_features)} expected features "
                        "were filled with zero. Interpret this "
                        "prediction cautiously."
                    )

                if (
                    not metadata_mapping
                    and isinstance(
                        prediction,
                        (int, np.integer, float, np.floating)
                    )
                ):

                    st.caption(
                        "Numeric class interpretation currently uses "
                        "the original application convention: "
                        "1 = WORN and 0 = UNWORN. Verify this against "
                        "the target encoding used during model training."
                    )


            except Exception as prediction_error:

                st.error(
                    "Prediction could not be completed."
                )

                st.exception(prediction_error)


    except pd.errors.EmptyDataError:

        st.error(
            "The uploaded CSV file is empty or has no readable columns."
        )

    except UnicodeDecodeError:

        st.error(
            "Unable to read the CSV encoding. Save the file as UTF-8 "
            "CSV and upload it again."
        )

    except Exception as error:

        st.error(
            "An error occurred while processing the uploaded file."
        )

        st.exception(error)


else:

    st.info(
        "Upload a CNC experiment CSV file above to begin."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "CNC Tool Wear Detection using Machine Learning | "
    "Experimental project"
)