import pandas as pd
import numpy as np

from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, StackingClassifier
from sklearn.svm import SVC

from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score


# ============================================================
# STEP 1: FEATURE EXTRACTION
# ============================================================

train = pd.read_csv("train.csv")

features = []

for i in range(1, 19):

    df = pd.read_csv(f"experiment_{i:02d}.csv")

    numeric = df.select_dtypes(include="number")

    row = {
        "experiment_id": i
    }

    # Statistical features
    for column in numeric.columns:

        values = numeric[column].dropna()

        row[f"{column}_mean"] = values.mean()
        row[f"{column}_std"] = values.std()
        row[f"{column}_median"] = values.median()
        row[f"{column}_min"] = values.min()
        row[f"{column}_max"] = values.max()
        row[f"{column}_range"] = values.max() - values.min()
        row[f"{column}_rms"] = np.sqrt(np.mean(values ** 2))
        row[f"{column}_abs_mean"] = np.mean(np.abs(values))
        row[f"{column}_energy"] = np.sum(values ** 2)

    # Experiment labels
    label = train[train["No"] == i].iloc[0]

    row["material"] = label["material"]
    row["feedrate"] = label["feedrate"]
    row["clamp_pressure"] = label["clamp_pressure"]
    row["tool_condition"] = label["tool_condition"]

    features.append(row)


feature_data = pd.DataFrame(features)

feature_data.to_csv(
    "features_improved.csv",
    index=False
)

print("\n========================================")
print("FEATURE EXTRACTION")
print("========================================")

print("Dataset shape:", feature_data.shape)

print("\nTool condition:")
print(feature_data["tool_condition"].value_counts())


# ============================================================
# STEP 2: PREPARE ML DATA
# ============================================================

y = feature_data["tool_condition"].map({
    "unworn": 0,
    "worn": 1
})

X = feature_data.drop(columns=[
    "experiment_id",
    "tool_condition",
    "material"
])

X = pd.get_dummies(X, drop_first=True)


# ============================================================
# STEP 3: DEFINE MODELS
# ============================================================

models = {

    "Logistic Regression": Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(
            max_iter=3000,
            C=0.1
        ))
    ]),

    "Decision Tree": Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", DecisionTreeClassifier(
            max_depth=2,
            min_samples_leaf=2,
            random_state=42
        ))
    ]),

    "Random Forest": Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", RandomForestClassifier(
            n_estimators=300,
            max_depth=3,
            min_samples_leaf=2,
            random_state=42
        ))
    ]),

    "SVM": Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", SVC(
            C=0.1,
            probability=True,
            kernel="rbf"
        ))
    ]),

    "Gradient Boosting": Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", GradientBoostingClassifier(
            n_estimators=50,
            learning_rate=0.05,
            max_depth=1,
            random_state=42
        ))
    ])
}


# ============================================================
# STEP 4: MODEL COMPARISON
# ============================================================

loo = LeaveOneOut()

results = []

print("\n========================================")
print("MODEL COMPARISON")
print("========================================")

for name, model in models.items():

    predictions = cross_val_predict(
        model,
        X,
        y,
        cv=loo
    )

    accuracy = accuracy_score(y, predictions)
    precision = precision_score(
        y,
        predictions,
        zero_division=0
    )
    recall = recall_score(
        y,
        predictions,
        zero_division=0
    )
    f1 = f1_score(
        y,
        predictions,
        zero_division=0
    )

    results.append({
        "Model": name,
        "Accuracy": accuracy,
        "Precision": precision,
        "Recall": recall,
        "F1 Score": f1
    })


results_df = pd.DataFrame(results)

print(
    results_df.to_string(
        index=False,
        float_format=lambda x: f"{x:.4f}"
    )
)

results_df.to_csv(
    "improved_model_results.csv",
    index=False
)


# ============================================================
# STEP 5: HYBRID STACKING MODEL
# ============================================================

base_models = [
    ("logistic", models["Logistic Regression"]),
    ("tree", models["Decision Tree"]),
    ("random_forest", models["Random Forest"]),
    ("gradient_boosting", models["Gradient Boosting"]),
    ("svm", models["SVM"])
]

hybrid = StackingClassifier(
    estimators=base_models,
    final_estimator=LogisticRegression(
        max_iter=3000,
        C=0.1
    ),
    cv=3
)


# ============================================================
# STEP 6: HYBRID EVALUATION
# ============================================================

hybrid_predictions = cross_val_predict(
    hybrid,
    X,
    y,
    cv=loo
)

hybrid_accuracy = accuracy_score(
    y,
    hybrid_predictions
)

hybrid_precision = precision_score(
    y,
    hybrid_predictions,
    zero_division=0
)

hybrid_recall = recall_score(
    y,
    hybrid_predictions,
    zero_division=0
)

hybrid_f1 = f1_score(
    y,
    hybrid_predictions,
    zero_division=0
)


print("\n========================================")
print("HYBRID STACKING MODEL")
print("========================================")

print(
    f"Accuracy : {hybrid_accuracy:.4f} "
    f"({hybrid_accuracy * 100:.2f}%)"
)

print(
    f"Precision: {hybrid_precision:.4f} "
    f"({hybrid_precision * 100:.2f}%)"
)

print(
    f"Recall   : {hybrid_recall:.4f} "
    f"({hybrid_recall * 100:.2f}%)"
)

print(
    f"F1 Score : {hybrid_f1:.4f} "
    f"({hybrid_f1 * 100:.2f}%)"
)


# ============================================================
# STEP 7: SAVE HYBRID RESULTS
# ============================================================

hybrid_results = pd.DataFrame({
    "Actual": y.values,
    "Predicted": hybrid_predictions
})

hybrid_results.to_csv(
    "improved_hybrid_predictions.csv",
    index=False
)

print("\n========================================")
print("FILES CREATED")
print("========================================")

print("features_improved.csv")
print("improved_model_results.csv")
print("improved_hybrid_predictions.csv")