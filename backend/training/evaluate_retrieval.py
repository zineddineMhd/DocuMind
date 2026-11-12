"""Compare des modèles d'embeddings sur les jeux de test tenus à l'écart (FQuAD, newsquadfr, Alloprof).

Métriques : Recall@1/5/10, MRR@10, nDCG@10. Résultat écrit dans reports/retrieval_benchmark.json.

Usage : python -m training.evaluate_retrieval [--models chemin_ou_nom ...]
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "training"
REPORT = ROOT / "reports" / "retrieval_benchmark.json"


def metrics(ranked: list[list[str]], gold: list[set[str]]) -> dict[str, float]:
    out = {"recall@1": 0.0, "recall@5": 0.0, "recall@10": 0.0, "mrr@10": 0.0, "ndcg@10": 0.0}
    for ids, rel in zip(ranked, gold):
        for k in (1, 5, 10):
            out[f"recall@{k}"] += float(bool(rel & set(ids[:k])))
        for rank, i in enumerate(ids[:10], 1):
            if i in rel:
                out["mrr@10"] += 1.0 / rank
                break
        dcg = sum(1.0 / math.log2(r + 1) for r, i in enumerate(ids[:10], 1) if i in rel)
        idcg = sum(1.0 / math.log2(r + 1) for r in range(1, min(len(rel), 10) + 1))
        out["ndcg@10"] += dcg / idcg
    return {k: round(v / len(ranked), 4) for k, v in out.items()}


def evaluate(model_name: str, sets: dict[str, dict], batch_size: int = 32) -> dict:
    import torch

    model = SentenceTransformer(model_name, device="cuda" if torch.cuda.is_available() else "cpu")
    model.max_seq_length = 512
    res = {}
    for name, data in sets.items():
        t0 = time.time()
        cids = list(data["corpus"])
        qids = list(data["queries"])
        c = model.encode(["passage: " + data["corpus"][i] for i in cids], batch_size=batch_size,
                         normalize_embeddings=True, show_progress_bar=False)
        q = model.encode(["query: " + data["queries"][i] for i in qids], batch_size=batch_size,
                         normalize_embeddings=True, show_progress_bar=False)
        top = np.argsort(-(q @ c.T), axis=1)[:, :10]
        ranked = [[cids[j] for j in row] for row in top]
        gold = [set(data["qrels"][i]) for i in qids]
        res[name] = metrics(ranked, gold) | {"n_queries": len(qids), "n_corpus": len(cids),
                                             "seconds": round(time.time() - t0, 1)}
        print(model_name, name, res[name], flush=True)
    res["mean_ndcg@10"] = round(float(np.mean([v["ndcg@10"] for v in res.values()])), 4)
    res["mean_recall@5"] = round(float(np.mean([v["recall@5"] for k, v in res.items() if isinstance(v, dict)])), 4)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["intfloat/multilingual-e5-small",
                                                    str(ROOT / "models" / "documind-e5-small-ft")])
    ap.add_argument("--batch-size", type=int, default=32)
    args = ap.parse_args()
    sets = {p.stem.replace("eval_", ""): json.loads(p.read_text("utf-8")) for p in sorted(DATA.glob("eval_*.json"))}
    report = {m: evaluate(m, sets, args.batch_size) for m in args.models}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(REPORT.read_text("utf-8")) if REPORT.exists() else {}
    existing.update(report)
    REPORT.write_text(json.dumps(existing, indent=2, ensure_ascii=False), "utf-8")
    print(json.dumps({m: {"mean_ndcg@10": r["mean_ndcg@10"], "mean_recall@5": r["mean_recall@5"]}
                      for m, r in existing.items()}, indent=2))


if __name__ == "__main__":
    main()
