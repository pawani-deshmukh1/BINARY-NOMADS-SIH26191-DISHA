import asyncio
import logging
import os
import site
import onnxruntime as ort
import numpy as np
from pathlib import Path
from .scoring_types import ModelConfidence
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class InferenceEngine:
    def __init__(self):
        # We assume models are mounted via docker-compose to /app/models or locally to layer0_imminent/models
        base = Path(__file__).resolve().parent.parent
        model_dir = base / "models"
        # If ONNX models are not in backend/models, fallback to layer0_imminent/models
        if not (model_dir / "damage_model.onnx").exists():
            fallback_dir = base.parent / "layer0_imminent" / "models"
            if (fallback_dir / "damage_model.onnx").exists():
                model_dir = fallback_dir

        self.model_paths = {
            "damage": str(model_dir / "damage_model.onnx"),
            "flood": str(model_dir / "flood_model.onnx"),
            "landslide": str(model_dir / "landslide_model.onnx"),
        }
        # Add onnxruntime-gpu's own bundled CUDA DLLs to the search path
        try:
            sp = site.getusersitepackages()
            for sub in ["cublas", "cudnn", "cuda_runtime", "cufft", "curand"]:
                dll_path = Path(sp) / "nvidia" / sub / "bin"
                if dll_path.exists():
                    os.add_dll_directory(str(dll_path))
                    logger.info(f"[InferenceEngine] Added DLL path: {dll_path}")
        except Exception as dll_err:
            logger.warning(f"[InferenceEngine] DLL path setup failed: {dll_err}")

        self.providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self.sessions = {}  # Cache sessions in VRAM (they total <500MB, easily fits in 4GB)
        logger.info(f"[InferenceEngine] Initialised with providers: {self.providers}")
        logger.info(f"[InferenceEngine] Available ORT providers: {ort.get_available_providers()}")

    def run(self, model_name: str, inputs: dict[str, np.ndarray]) -> tuple[np.ndarray | None, ModelConfidence | None]:
        """
        Runs ONNX inference using cached VRAM sessions.
        Inputs: dictionary mapping ONNX input names to numpy arrays.
        """
        if model_name not in self.model_paths:
            print(f"[InferenceEngine] Unknown model {model_name}")
            return None, None
            
        path = self.model_paths[model_name]
        if not Path(path).exists():
            print(f"[InferenceEngine] Model file missing: {path}")
            return None, None

        try:
            # Load into VRAM if not already loaded
            if model_name not in self.sessions:
                logger.info(f"[InferenceEngine] Loading {model_name} into VRAM on {self.providers[0]}...")
                self.sessions[model_name] = ort.InferenceSession(path, providers=self.providers)
            
            session = self.sessions[model_name]
            logger.info(f"[InferenceEngine] Executing {model_name} on {session.get_providers()[0]}...")
            
            # Run inference
            output = session.run(None, inputs)
            
            # Extract output tensor
            logits = output[0]
            
            # Calculate a mock confidence for now based on max logit magnitude
            # In production, this would be softmax/sigmoid probability
            score = float(np.clip(np.max(logits) / 10.0, 0.0, 1.0))
            
            confidence = ModelConfidence(
                score=score,
                last_updated=datetime.now(timezone.utc)
            )
            
            return logits, confidence
            
        except Exception as e:
            logger.error(f"[InferenceEngine] Error running {model_name}: {e}", exc_info=True)
            return None, None

    async def run_async(self, model_name: str, inputs: dict[str, np.ndarray]) -> tuple[np.ndarray | None, 'ModelConfidence | None']:
        """
        Async wrapper around run() using asyncio.to_thread.
        Allows multiple models to be gathered in parallel:
            damage, flood, landslide = await asyncio.gather(
                engine.run_async('damage', d_inputs),
                engine.run_async('flood', f_inputs),
                engine.run_async('landslide', l_inputs),
            )
        """
        return await asyncio.to_thread(self.run, model_name, inputs)

# Singleton instance
engine = InferenceEngine()
