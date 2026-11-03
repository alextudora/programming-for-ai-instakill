import numpy as np
from pathlib import Path
from fastapi import HTTPException

MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "like_model.npz"
_saved_model = None


def load_model():
    """Load the model once at startup. Returns 503 if missing."""
    global _saved_model
    if not MODEL_PATH.exists():
        return False

    try:
        _saved_model = dict(np.load(MODEL_PATH, allow_pickle=True))
        return True
    except Exception:
        return False


def get_model():
    """Retrieve the loaded model or raise 503."""
    if _saved_model is None:
        raise HTTPException(status_code=503, detail="Learned model not available (like_model.npz missing)")
    return _saved_model


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -60, 60)))


def predict(saved, features):
    """
    Pure predict function: raw signals (n, 6) in the saved order -> P(like).
    No I/O, no globals, NumPy only[cite: 1, 2].
    """
    x = (features - saved["mu"]) / saved["sd"]
    hidden = np.tanh(x @ saved["W1"] + saved["b1"])
    return sigmoid((hidden @ saved["W2"] + saved["b2"])[:, 0])