"""Affinage (fine-tuning) du modèle d'embeddings de DocuMind pour la recherche documentaire.

Modèle de base : intfloat/multilingual-e5-small (384 dimensions, rapide sur CPU).
Perte : MultipleNegativesRankingLoss (contrastif, négatifs in-batch + négatifs difficiles MIRACL).

Usage :
    python -m training.prepare_data
    python -m training.train_embeddings --max-steps 400
    python -m training.evaluate_retrieval
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets import Dataset
from sentence_transformers import SentenceTransformer, SentenceTransformerTrainer, SentenceTransformerTrainingArguments
from sentence_transformers.losses import MultipleNegativesRankingLoss
from sentence_transformers.training_args import BatchSamplers, MultiDatasetBatchSamplers

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "training"
DEFAULT_OUT = ROOT / "models" / "documind-e5-small-ft"


def _load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-model", default="intfloat/multilingual-e5-small")
    ap.add_argument("--output", default=str(DEFAULT_OUT))
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--max-steps", type=int, default=400)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-seq-length", type=int, default=192)
    ap.add_argument("--epochs", type=float, default=None, help="si fourni, remplace --max-steps (entraînement GPU)")
    ap.add_argument("--device", default="auto", help="auto | cpu | cuda")
    args = ap.parse_args()

    import torch

    device = ("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" else args.device
    print("Périphérique :", device)
    model = SentenceTransformer(args.base_model, device=device)
    model.max_seq_length = args.max_seq_length

    # Les modèles E5 attendent les préfixes « query: » / « passage: ».
    pairs = _load(DATA / "train_pairs.jsonl")
    triplets = _load(DATA / "train_triplets.jsonl")
    ds_pairs = Dataset.from_dict({
        "anchor": ["query: " + r["query"] for r in pairs],
        "positive": ["passage: " + r["positive"] for r in pairs],
    })
    ds_triplets = Dataset.from_dict({
        "anchor": ["query: " + r["query"] for r in triplets],
        "positive": ["passage: " + r["positive"] for r in triplets],
        "negative": ["passage: " + r["negative"] for r in triplets],
    })
    print(f"paires={len(ds_pairs)} triplets={len(ds_triplets)}")

    loss = MultipleNegativesRankingLoss(model, scale=50.0)  # température 0.02
    targs = SentenceTransformerTrainingArguments(
        output_dir=str(ROOT / "data" / "training" / "checkpoints"),
        max_steps=-1 if args.epochs else args.max_steps,
        num_train_epochs=args.epochs or 1,
        fp16=device == "cuda",
        per_device_train_batch_size=args.batch_size,
        learning_rate=args.lr,
        warmup_ratio=0.1,
        weight_decay=0.01,
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        multi_dataset_batch_sampler=MultiDatasetBatchSamplers.PROPORTIONAL,
        logging_steps=20,
        save_strategy="no",
        report_to="none",
        use_cpu=device == "cpu",
        dataloader_num_workers=0,
        seed=42,
    )
    trainer = SentenceTransformerTrainer(
        model=model,
        args=targs,
        train_dataset={"pairs": ds_pairs, "triplets": ds_triplets},
        loss=loss,
    )
    trainer.train()
    model.max_seq_length = 512
    model.save(args.output)
    (Path(args.output) / "training_info.json").write_text(json.dumps({
        "base_model": args.base_model, "max_steps": trainer.state.global_step, "epochs": args.epochs,
        "device": device, "batch_size": args.batch_size,
        "lr": args.lr, "train_max_seq_length": args.max_seq_length,
        "n_pairs": len(ds_pairs), "n_triplets": len(ds_triplets),
        "log": [h for h in trainer.state.log_history if "loss" in h],
    }, indent=2), "utf-8")
    print("Modèle enregistré :", args.output)


if __name__ == "__main__":
    main()
