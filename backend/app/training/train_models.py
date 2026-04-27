"""
Model training logic.
retrain_if_ready() is the single function used by:
  - background_trainer.py (after training upload batch)
  - scheduler.py (weekly Sunday retrain)
  - POST /training/retrain/force
"""
import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

import numpy as np

from app.config import settings
from app.db.database import AsyncSessionLocal
from app.db import corpus

logger = logging.getLogger(__name__)


@dataclass
class RetrainResult:
    swapped: bool
    new_f1: Optional[float]
    old_f1: Optional[float]
    skipped_reason: Optional[str] = None


def _load_current_f1() -> Optional[float]:
    meta_path = os.path.join(settings.MODEL_STORE_PATH, "model_meta.json")
    try:
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                return json.load(f).get("f1_score")
    except Exception:
        pass
    return None


def _save_meta(f1: float, version: str):
    meta_path = os.path.join(settings.MODEL_STORE_PATH, "model_meta.json")
    with open(meta_path, "w") as f:
        json.dump({
            "f1_score": f1,
            "version": version,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)


def retrain_if_ready() -> RetrainResult:
    """
    Synchronous (runs in background thread, never in the async event loop).
    1. Fetches corpus from DB synchronously via a new session
    2. Builds X, y arrays
    3. Trains IsolationForest + RandomForest
    4. Evaluates on held-out 20% split
    5. Swaps production models only if new_f1 >= current_f1
    """
    import asyncio
    import joblib
    from sklearn.ensemble import IsolationForest, RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import f1_score

    # Fetch records synchronously by running async code in a new event loop
    loop = asyncio.new_event_loop()
    try:
        async def _fetch():
            async with AsyncSessionLocal() as db:
                return await corpus.get_verified_records(db)
        records = loop.run_until_complete(_fetch())
    finally:
        loop.close()

    if len(records) < settings.MIN_TRAINING_RECORDS:
        logger.info(f"[train] Skipped — only {len(records)} verified records (need {settings.MIN_TRAINING_RECORDS})")
        return RetrainResult(swapped=False, new_f1=None, old_f1=_load_current_f1(),
                             skipped_reason=f"Need {settings.MIN_TRAINING_RECORDS} records, have {len(records)}")

    # Build feature matrix
    X_all, y_all = [], []
    X_accepted = []
    for rec in records:
        if not rec.feature_vector:
            continue
        try:
            fv = json.loads(rec.feature_vector)
            label = 1 if rec.outcome == "accepted" else 0
            X_all.append(fv)
            y_all.append(label)
            if rec.outcome == "accepted":
                X_accepted.append(fv)
        except Exception:
            continue

    if len(X_all) < settings.MIN_TRAINING_RECORDS:
        return RetrainResult(swapped=False, new_f1=None, old_f1=_load_current_f1(),
                             skipped_reason="Insufficient records with feature vectors")

    X_all = np.array(X_all)
    y_all = np.array(y_all)
    X_accepted = np.array(X_accepted) if X_accepted else X_all

    # Train-test split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X_all, y_all, test_size=0.2, random_state=42, stratify=y_all if len(set(y_all)) > 1 else None
    )

    # Model 1 — IsolationForest (trained on accepted only)
    X_acc_train = X_train[y_train == 1] if y_train.sum() > 0 else X_train
    iso = IsolationForest(contamination=0.05, random_state=42, n_jobs=-1)
    iso.fit(X_acc_train)

    # Model 2 — RandomForestClassifier
    rf = RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)

    # Evaluate on test set
    y_pred = rf.predict(X_test)
    new_f1 = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))
    old_f1 = _load_current_f1()

    logger.info(f"[train] New F1={new_f1:.4f}, Old F1={old_f1}")

    # Only swap if improvement
    if old_f1 is None or new_f1 >= old_f1:
        iso_path = os.path.join(settings.MODEL_STORE_PATH, "isolation_forest.joblib")
        rf_path = os.path.join(settings.MODEL_STORE_PATH, "random_forest.joblib")
        joblib.dump(iso, iso_path)
        joblib.dump(rf, rf_path)

        version = f"v{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        _save_meta(new_f1, version)

        # Reload in-memory models
        from app.validation import ml_scorer
        ml_scorer.reload_models()

        logger.info(f"[train] Models swapped → {version} (F1: {old_f1} → {new_f1})")
        return RetrainResult(swapped=True, new_f1=new_f1, old_f1=old_f1)
    else:
        logger.info(f"[train] No swap — new model did not improve F1 ({new_f1:.4f} < {old_f1:.4f})")
        return RetrainResult(swapped=False, new_f1=new_f1, old_f1=old_f1)
