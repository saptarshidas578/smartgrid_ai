import os
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

# Setup directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

forecast_path = os.path.join(DATA_DIR, "load_forecasting.csv")
abnormal_path = os.path.join(DATA_DIR, "abnormal_load.csv")
fault_path = os.path.join(DATA_DIR, "fault_detection.csv")

def train_and_save_models():
    print("Starting local training of Smart Grid ML models on the 5,200-row datasets...")
    
    # -----------------------------------------------------------------
    # 1. Train Load Forecasting Models (Model 1A & 1B)
    # -----------------------------------------------------------------
    if os.path.exists(forecast_path):
        print("\nTraining Forecasting Models (current and power)...")
        df = pd.read_csv(forecast_path)
        X = df.drop(columns=["timestamp", "future_current", "future_power"])
        X = pd.get_dummies(X, columns=["mode"], drop_first=True)
        
        # Save feature headers
        joblib.dump(X.columns.tolist(), os.path.join(MODELS_DIR, "forecasting_features.pkl"))
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(X, df["future_current"], test_size=0.15, random_state=42, shuffle=True)
        model_1a = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1) # 50 estimators for faster local training
        model_1a.fit(X_train, y_train)
        joblib.dump(model_1a, os.path.join(MODELS_DIR, "load_forecasting_current_model.pkl"))
        print("-> Saved load_forecasting_current_model.pkl")

        X_train, X_test, y_train, y_test = train_test_split(X, df["future_power"], test_size=0.15, random_state=42, shuffle=True)
        model_1b = RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)
        model_1b.fit(X_train, y_train)
        joblib.dump(model_1b, os.path.join(MODELS_DIR, "load_forecasting_power_model.pkl"))
        print("-> Saved load_forecasting_power_model.pkl")
    else:
        print(f"Error: Forecasting file not found at {forecast_path}")

    # -----------------------------------------------------------------
    # 2. Train Fault Classifier Diagnostics
    # -----------------------------------------------------------------
    if os.path.exists(fault_path):
        print("\nTraining Fault Classifiers...")
        df = pd.read_csv(fault_path)
        X = df.drop(columns=["timestamp", "fault", "fault_load", "fault_type", "fault_code", "severity"])
        X = pd.get_dummies(X, columns=["mode"], drop_first=True)
        
        # Save feature headers
        joblib.dump(X.columns.tolist(), os.path.join(MODELS_DIR, "fault_features.pkl"))
        
        # --- Fault Presence (Binary) ---
        X_train, X_test, y_train, y_test = train_test_split(X, df["fault"], test_size=0.15, random_state=42, shuffle=True)
        clf_pres = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
        clf_pres.fit(X_train, y_train)
        joblib.dump(clf_pres, os.path.join(MODELS_DIR, "fault_detection_model.pkl"))
        print("-> Saved fault_detection_model.pkl")

        # --- Fault Load Location (Multi-class) ---
        X_train, X_test, y_train, y_test = train_test_split(X, df["fault_load"], test_size=0.15, random_state=42, shuffle=True)
        clf_ld = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
        clf_ld.fit(X_train, y_train)
        joblib.dump(clf_ld, os.path.join(MODELS_DIR, "fault_load_model.pkl"))
        print("-> Saved fault_load_model.pkl")

        # --- Fault Type (Multi-class) ---
        X_train, X_test, y_train, y_test = train_test_split(X, df["fault_type"], test_size=0.15, random_state=42, shuffle=True)
        clf_tp = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
        clf_tp.fit(X_train, y_train)
        joblib.dump(clf_tp, os.path.join(MODELS_DIR, "fault_type_model.pkl"))
        print("-> Saved fault_type_model.pkl")

        # --- Fault Severity (Multi-class) ---
        X_train, X_test, y_train, y_test = train_test_split(X, df["severity"], test_size=0.15, random_state=42, shuffle=True)
        clf_sv = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
        clf_sv.fit(X_train, y_train)
        joblib.dump(clf_sv, os.path.join(MODELS_DIR, "fault_severity_model.pkl"))
        print("-> Saved fault_severity_model.pkl")
    else:
        print(f"Error: Fault dataset file not found at {fault_path}")

    print("\nLocal ML model training complete! All .pkl files saved to models/ directory.")

if __name__ == "__main__":
    train_and_save_models()
