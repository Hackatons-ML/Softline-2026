"""
Fast local multilingual neural embedding engine using ONNX Runtime + HuggingFace Tokenizers.
Uses quantized multilingual-e5-small (384-dim) with query/passage instruction prefixes,
dynamic ONNX input inspection, masked mean pooling, and L2 normalization.
"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Iterable, List, Optional
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer
from huggingface_hub import hf_hub_download

MODEL_CANDIDATES = [
    ("Xenova/multilingual-e5-small", "onnx/model_quantized.onnx", "tokenizer.json"),
    ("Xenova/multilingual-e5-small", "onnx/model.onnx", "tokenizer.json"),
    ("intfloat/multilingual-e5-small", "onnx/model.onnx", "tokenizer.json"),
]


class LocalSemanticEmbedder:
    """Thread-safe local ONNX embedder for Russian + English B2B IT search."""

    def __init__(self, cache_dir: Optional[Path] = None, max_length: int = 96) -> None:
        self.max_length = max_length
        self.cache_dir = str(cache_dir) if cache_dir else None
        self.model_id = ""
        self.tokenizer: Optional[Tokenizer] = None
        self.session: Optional[ort.InferenceSession] = None
        self.input_names: List[str] = []
        self._load_model()

    def _load_model(self) -> None:
        last_err: Optional[Exception] = None
        for repo_id, onnx_file, tok_file in MODEL_CANDIDATES:
            try:
                tok_path = hf_hub_download(
                    repo_id=repo_id,
                    filename=tok_file,
                    cache_dir=self.cache_dir,
                )
                onnx_path = hf_hub_download(
                    repo_id=repo_id,
                    filename=onnx_file,
                    cache_dir=self.cache_dir,
                )
                tokenizer = Tokenizer.from_file(tok_path)
                tokenizer.enable_truncation(max_length=self.max_length)
                tokenizer.enable_padding(pad_id=1, pad_token="<pad>")

                sess_opts = ort.SessionOptions()
                sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                cpu_count = os.cpu_count() or 8
                sess_opts.intra_op_num_threads = max(4, cpu_count)
                sess_opts.inter_op_num_threads = 2

                providers = [
                    p
                    for p in ["CUDAExecutionProvider", "CPUExecutionProvider"]
                    if p in ort.get_available_providers()
                ]
                session = ort.InferenceSession(
                    onnx_path, sess_options=sess_opts, providers=providers or ["CPUExecutionProvider"]
                )
                self.model_id = f"{repo_id}/{onnx_file}"
                self.tokenizer = tokenizer
                self.session = session
                self.input_names = [inp.name for inp in session.get_inputs()]
                return
            except Exception as exc:
                last_err = exc
                continue
        raise RuntimeError(f"Failed to initialize ONNX semantic model: {last_err}")

    def _encode_raw(self, prefixed_texts: List[str], batch_size: int = 128) -> np.ndarray:
        assert self.tokenizer is not None and self.session is not None
        if not prefixed_texts:
            return np.zeros((0, 384), dtype=np.float32)

        all_vecs: List[np.ndarray] = []
        for start in range(0, len(prefixed_texts), batch_size):
            batch = prefixed_texts[start : start + batch_size]
            encodings = self.tokenizer.encode_batch(batch)
            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

            feed = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
            }
            if "token_type_ids" in self.input_names:
                feed["token_type_ids"] = np.zeros_like(input_ids, dtype=np.int64)

            outputs = self.session.run(None, feed)
            hidden = outputs[0]  # [B, L, D] or [B, D]
            if hidden.ndim == 3:
                mask_f = attention_mask.astype(np.float32)[..., None]
                summed = np.sum(hidden * mask_f, axis=1)
                counts = np.clip(np.sum(mask_f, axis=1), a_min=1e-9, a_max=None)
                pooled = summed / counts
            else:
                pooled = hidden.astype(np.float32)

            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            normalized = (pooled / np.clip(norms, 1e-12, None)).astype(np.float32)
            all_vecs.append(normalized)

        return np.vstack(all_vecs)

    def encode_passages(self, texts: Iterable[str], batch_size: int = 128) -> np.ndarray:
        prefixed = [f"passage: {t.strip()}" for t in texts]
        return self._encode_raw(prefixed, batch_size=batch_size)

    def encode_query(self, query: str) -> np.ndarray:
        vecs = self._encode_raw([f"query: {query.strip()}"], batch_size=1)
        return vecs[0]
