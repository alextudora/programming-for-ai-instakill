from sentence_transformers import SentenceTransformer
import numpy as np

class SemanticEncoder:
    """
    Adapter boundary for the pretrained semantic model.
    Isolates the Hugging Face / sentence_transformers dependency from the rest of the app.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        """
        Transforms a list of text strings into a normalized embedding matrix.
        Returns a numpy array of floats.
        """
        return self.model.encode(texts, normalize_embeddings=True)