"""
Layer B — ML Scorer
Loads IsolationForest and RandomForestClassifier from model store.
Returns ml_bonus and ml_active flag.
Falls back to 0 bonus when fewer than MIN_TRAINING_RECORDS exist.
"""
import os
import logging
import numpy as np
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

_isolation_forest = None
_random_forest = None
_models_loaded = False


def _load_models():
    global _isolation_forest, _random_forest, _models_loaded
    try:
        import joblib
        iso_path = os.path.join(settings.MODEL_STORE_PATH, "isolation_forest.joblib")
        rf_path = os.path.join(settings.MODEL_STORE_PATH, "random_forest.joblib")

        if os.path.exists(iso_path) and os.path.exists(rf_path):
            _isolation_forest = joblib.load(iso_path)
            _random_forest = joblib.load(rf_path)
            _models_loaded = True
            logger.info("ML models loaded from model store.")
        else:
            logger.info("No trained models found in model store — ML scoring inactive.")
            _models_loaded = False
    except Exception as e:
        logger.warning(f"Failed to load ML models: {e}")
        _models_loaded = False


def reload_models():
    """Called by training module after a successful model swap."""
    global _isolation_forest, _random_forest, _models_loaded
    _isolation_forest = None
    _random_forest = None
    _models_loaded = False
    _load_models()


def score(feature_vector: list[float], verified_record_count: int) -> tuple[float, bool]:
    """
    Returns (ml_bonus, ml_active).
    ml_bonus is in range [-10, +10].
    ml_active is False when corpus is too small or models not loaded.
    """
    if verified_record_count < settings.MIN_TRAINING_RECORDS:
        return 0.0, False

    if not _models_loaded:
        _load_models()

    if not _models_loaded or _isolation_forest is None or _random_forest is None:
        return 0.0, False

    try:
        X = np.array(feature_vector).reshape(1, -1)

        # IsolationForest: score_samples returns negative values; -1 = anomaly
        # Normalize to [0, 1] where 1 = normal
        raw_score = _isolation_forest.score_samples(X)[0]
        # Typical range is roughly -0.7 to -0.1; we map to [0,1]
        anomaly_score = float(np.clip((raw_score + 0.7) / 0.6, 0.0, 1.0))

        # RandomForest: probability of class 1 (accepted)
        acceptance_prob = float(_random_forest.predict_proba(X)[0][1])

        isolation_bonus = anomaly_score * 5.0
        rf_bonus = (acceptance_prob - 0.5) * 10.0
        ml_bonus = float(np.clip(isolation_bonus + rf_bonus, -10.0, 10.0))

        return ml_bonus, True

    except Exception as e:
        logger.warning(f"ML scoring failed: {e}")
        return 0.0, False


# Attempt to load on import
_load_models()
