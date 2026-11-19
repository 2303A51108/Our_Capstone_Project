import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import LeaveOneOut
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectKBest, f_classif

from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
    VotingClassifier,
    StackingClassifier
)
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)

print("=" * 60)
print("FINAL CNC TOOL WEAR MODEL COMPARISON")
print("=" * 60)

# ---------------------------------------------------------
# 1. LOAD FEATURES
# ---------------------------------------------------------

df = pd.read_csv("features_improved.csv")

X = df.drop(
    columns=["experiment_id", "tool_condition", "material"],
    errors="ignore"
)

y = df["tool_condition"].map({
    "unworn": 0,
    "worn": 1
})

# Convert categorical columns if any remain
X = pd.get_dummies(X, drop_first=True)

print("\nDataset shape:", X.shape)
print("Unworn:", sum(y == 0))
print("Worn:", sum(y == 1))

# ---------------------------------------------------------
# 2. MODELS
# ---------------------------------------------------------

decision_tree = DecisionTreeClassifier(
    max_depth=2,
    min_samples_leaf=2,
    class_weight="balanced",
    random_state=42
)

gradient_boosting = GradientBoostingClassifier(
    n_estimators=50,
    learning_rate=0.05,
    max_depth=1,
    random_state=42
)

svm = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler()),
    ("select", SelectKBest(f_classif, k=20)),
    ("model", SVC(
        C=0.1,
        probability=True,
        class_weight="balanced",
        random_state=42
    ))
])

random_forest = RandomForestClassifier(
    n_estimators=200,
    max_depth=3,
    min_samples_leaf=2,
    class_weight="balanced",
    random_state=42
)

logistic = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler()),
    ("select", SelectKBest(f_classif, k=20)),
    ("model", LogisticRegression(
        C=0.1,
        class_weight="balanced",
        max_iter=5000,
        random_state=42
    ))
])

# ---------------------------------------------------------
# 3. VOTING ENSEMBLE
# ---------------------------------------------------------

voting = VotingClassifier(
    estimators=[
        ("dt", decision_tree),
        ("gb", gradient_boosting),
        ("svm", svm),
        ("rf", random_forest)
    ],
    voting="soft"
)

# ---------------------------------------------------------
# 4. STACKING ENSEMBLE
# ---------------------------------------------------------

stacking = StackingClassifier(
    estimators=[
        ("dt", decision_tree),
        ("gb", gradient_boosting),
        ("svm", svm),
        ("rf", random_forest)
    ],
    final_estimator=LogisticRegression(
        class_weight="balanced",
        max_iter=5000,
        random_state=42
    ),
    cv=3,
    stack_method="predict_proba"
)

models = {
    "Decision Tree": decision_tree,
    "Gradient Boosting": gradient_boosting,
    "SVM": svm,
    "Random Forest": random_forest,
    "Voting Ensemble": voting,
    "Stacking Ensemble": stacking
}

# ---------------------------------------------------------
# 5. LEAVE-ONE-EXPERIMENT-OUT EVALUATION
# ---------------------------------------------------------

loo = LeaveOneOut()

results = []
all_predictions = {}

for name, model in models.items():

    print(f"\nTesting: {name}")

    y_true = []
    y_pred = []

    for train_idx, test_idx in loo.split(X):

        X_train = X.iloc[train_idx]
        X_test = X.iloc[test_idx]

        y_train = y.iloc[train_idx]
        y_test = y.iloc[test_idx]

        model.fit(X_train, y_train)

        prediction = model.predict(X_test)[0]

        y_true.append(y_test.iloc[0])
        y_pred.append(prediction)

    accuracy = accuracy_score(y_true, y_pred)
    precision = precision_score(
        y_true, y_pred, zero_division=0
    )
    recall = recall_score(
        y_true, y_pred, zero_division=0
    )
    f1 = f1_score(
        y_true, y_pred, zero_division=0
    )

    results.append({
        "Model": name,
        "Accuracy": accuracy,
        "Precision": precision,
        "Recall": recall,
        "F1 Score": f1
    })

    all_predictions[name] = y_pred

    print(f"Accuracy : {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall   : {recall:.4f}")
    print(f"F1 Score : {f1:.4f}")

# ---------------------------------------------------------
# 6. RESULTS TABLE
# ---------------------------------------------------------

results_df = pd.DataFrame(results)

results_df = results_df.sort_values(
    by="F1 Score",
    ascending=False
)

print("\n" + "=" * 60)
print("FINAL MODEL RANKING")
print("=" * 60)

print(results_df.to_string(index=False))

results_df.to_csv(
    "final_model_results.csv",
    index=False
)

# ---------------------------------------------------------
# 7. BEST MODEL
# ---------------------------------------------------------

best_model_name = results_df.iloc[0]["Model"]

print("\n" + "=" * 60)
print("BEST MODEL")
print("=" * 60)

print("Selected model:", best_model_name)
print(
    "Accuracy:",
    f"{results_df.iloc[0]['Accuracy']:.2%}"
)
print(
    "Precision:",
    f"{results_df.iloc[0]['Precision']:.2%}"
)
print(
    "Recall:",
    f"{results_df.iloc[0]['Recall']:.2%}"
)
print(
    "F1 Score:",
    f"{results_df.iloc[0]['F1 Score']:.2%}"
)

# ---------------------------------------------------------
# 8. CONFUSION MATRIX
# ---------------------------------------------------------

best_predictions = all_predictions[best_model_name]

cm = confusion_matrix(
    y,
    best_predictions
)

print("\nConfusion Matrix:")
print(cm)

# ---------------------------------------------------------
# 9. TRAIN FINAL BEST MODEL ON ALL DATA
# ---------------------------------------------------------

best_model = models[best_model_name]

best_model.fit(X, y)

joblib.dump(
    best_model,
    "final_tool_wear_model.pkl"
)

# Save feature names for Streamlit
feature_data = {
    "features": list(X.columns),
    "model_name": best_model_name
}

joblib.dump(
    feature_data,
    "model_metadata.pkl"
)

print("\n" + "=" * 60)
print("FILES CREATED")
print("=" * 60)

print("final_model_results.csv")
print("final_tool_wear_model.pkl")
print("model_metadata.pkl")

print("\nFINAL MODEL READY.")