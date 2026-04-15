import joblib

class FusionModelWrapper:
    """
    A wrapper class representing a fused model.
    It contains references to the underlying models and the fusion strategy.
    This can be serialized as a .joblib file and loaded by the InferenceEngine.
    """
    def __init__(self, sub_models, fusion_strategy="weighted", weights=None):
        self.sub_models = sub_models  # List of dicts e.g., [{"name": "lightgbm", "type": "lightgbm"}]
        self.fusion_strategy = fusion_strategy
        self.weights = weights or {}
        self.is_fusion = True

    def get_config(self):
        return {
            "sub_models": self.sub_models,
            "fusion_strategy": self.fusion_strategy,
            "weights": self.weights
        }

    def save(self, filepath):
        joblib.dump(self, filepath)

    @classmethod
    def load(cls, filepath):
        return joblib.load(filepath)
