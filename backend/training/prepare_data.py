"""Télécharge des jeux de données publics de recherche (FR + EN) et construit :

- data/training/train_pairs.jsonl      : {"query", "positive"}            (négatifs « in-batch »)
- data/training/train_triplets.jsonl   : {"query", "positive", "negative"} (négatifs difficiles)
- data/training/eval_<nom>.json        : {"queries", "corpus", "qrels"}   (jeux de test tenus à l'écart)

Sources (Hugging Face Hub, toutes publiques) :
  etalab-ia/piaf                 QA français natif sur Wikipédia          -> entraînement
  lincoln/newsquadfr             QA français sur articles de presse       -> entraînement + test
  sentence-transformers/miracl   requêtes FR + négatifs difficiles        -> entraînement
  lyon-nlp/alloprof              questions d'élèves -> fiches de cours    -> entraînement + test
  sentence-transformers/squad    QA anglais (maintien du multilingue)     -> entraînement
  manu/fquad2_test               FQuAD (validation)                       -> test uniquement

Usage : python -m training.prepare_data
"""
from __future__ import annotations

import ast
import json
import random
from pathlib import Path

import pandas as pd
from huggingface_hub import hf_hub_download

OUT = Path(__file__).resolve().parents[1] / "data" / "training"
SEED = 42
MAX_PASSAGE_CHARS = 1500  # ~ taille de 1 à 2 chunks DocuMind


def _dl(repo: str, filename: str) -> str:
    return hf_hub_download(repo, filename, repo_type="dataset")


def _clean(text: str) -> str:
    return " ".join(str(text).split())


def _jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _eval_set(queries: dict[str, str], corpus: dict[str, str], qrels: dict[str, list[str]]) -> dict:
    return {"queries": queries, "corpus": corpus, "qrels": qrels}


def main() -> None:
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)
    pairs: list[dict] = []
    triplets: list[dict] = []
    stats: dict[str, int] = {}

    # ---- PIAF (entraînement) -------------------------------------------------
    piaf = pd.read_parquet(_dl("etalab-ia/piaf", "plain_text/train-00000-of-00001.parquet"))
    piaf_contexts = sorted({_clean(c) for c in piaf["context"]})
    for q, c in zip(piaf["question"], piaf["context"]):
        pairs.append({"query": _clean(q), "positive": _clean(c)[:MAX_PASSAGE_CHARS], "src": "piaf"})
    stats["piaf"] = len(piaf)

    # ---- newsquadfr (entraînement sur train, test sur valid+test) ------------
    news_train = _jsonl(_dl("lincoln/newsquadfr", "train.json"))
    news_eval = _jsonl(_dl("lincoln/newsquadfr", "valid.json")) + _jsonl(_dl("lincoln/newsquadfr", "test.json"))
    eval_paragraphs = {r["paragraph_id"] for r in news_eval}
    eval_articles = {r["article_id"] for r in news_eval}
    n = 0
    for r in news_train:
        if r["article_id"] in eval_articles:  # pas de fuite d'article entre train et test
            continue
        pairs.append({"query": _clean(r["question"]), "positive": _clean(r["context"]), "src": "newsquadfr"})
        n += 1
    stats["newsquadfr"] = n
    corpus = {f"n{r['paragraph_id']}": _clean(r["context"]) for r in news_train + news_eval}
    queries = {f"q{r['id']}": _clean(r["question"]) for r in news_eval}
    qrels = {f"q{r['id']}": [f"n{r['paragraph_id']}"] for r in news_eval}
    assert all(f"n{p}" in corpus for p in eval_paragraphs)
    (OUT / "eval_newsquadfr.json").write_text(json.dumps(_eval_set(queries, corpus, qrels), ensure_ascii=False), "utf-8")

    # ---- MIRACL fr (triplets avec négatifs difficiles) -----------------------
    miracl = pd.read_parquet(_dl("sentence-transformers/miracl", "fr-triplet/train-00000-of-00001.parquet"))
    for a, p, ng in zip(miracl["anchor"], miracl["positive"], miracl["negative"]):
        triplets.append({"query": _clean(a), "positive": _clean(p)[:MAX_PASSAGE_CHARS],
                         "negative": _clean(ng)[:MAX_PASSAGE_CHARS], "src": "miracl-fr"})
    stats["miracl-fr"] = len(miracl)

    # ---- Alloprof (questions d'élèves -> fiches) ------------------------------
    docs = json.load(open(_dl("lyon-nlp/alloprof", "documents.json"), encoding="utf-8"))
    doc_text = {d["uuid"]: _clean(f"{d['title']}. {d['text']}") for d in docs}
    q_train = json.load(open(_dl("lyon-nlp/alloprof", "queries-train.json"), encoding="utf-8"))
    q_test = json.load(open(_dl("lyon-nlp/alloprof", "queries-test.json"), encoding="utf-8"))

    def _rel(q: dict) -> list[str]:
        rel = q["relevant"]
        if isinstance(rel, str):
            rel = ast.literal_eval(rel)
        return [r for r in rel if r in doc_text]

    rng.shuffle(q_train)
    n = 0
    for q in q_train:
        rel = _rel(q)
        if not rel or len(q["text"]) < 15:
            continue
        pairs.append({"query": _clean(q["text"])[:400], "positive": doc_text[rel[0]][:MAX_PASSAGE_CHARS], "src": "alloprof"})
        n += 1
        if n >= 3000:
            break
    stats["alloprof"] = n
    rng.shuffle(q_test)
    queries, qrels = {}, {}
    for q in q_test:
        rel = _rel(q)
        if rel and len(queries) < 500:
            queries[f"a{q['id']}"] = _clean(q["text"])[:400]
            qrels[f"a{q['id']}"] = rel
    corpus = {k: v[:3000] for k, v in doc_text.items()}
    (OUT / "eval_alloprof.json").write_text(json.dumps(_eval_set(queries, corpus, qrels), ensure_ascii=False), "utf-8")

    # ---- SQuAD EN (échantillon, pour ne pas dégrader l'anglais) ---------------
    squad = pd.read_parquet(_dl("sentence-transformers/squad", "pair/train-00000-of-00001.parquet"))
    squad = squad.sample(n=1500, random_state=SEED)
    for q, c in zip(squad["question"], squad["answer"]):
        pairs.append({"query": _clean(q), "positive": _clean(c)[:MAX_PASSAGE_CHARS], "src": "squad-en"})
    stats["squad-en"] = len(squad)

    # ---- FQuAD (test uniquement ; contextes PIAF ajoutés comme distracteurs) --
    fq = pd.read_parquet(_dl("manu/fquad2_test", "data/valid-00000-of-00001-c57e7fc735be9d5f.parquet"))
    ctx_ids: dict[str, str] = {}
    for c in fq["context"]:
        ctx_ids.setdefault(_clean(c), f"f{len(ctx_ids)}")
    corpus = {cid: c for c, cid in ctx_ids.items()}
    for i, c in enumerate(piaf_contexts):
        corpus.setdefault(f"p{i}", c)
    queries, qrels = {}, {}
    for i, row in enumerate(fq.itertuples()):
        if not row.is_impossible:
            queries[f"fq{i}"] = _clean(row.question)
            qrels[f"fq{i}"] = [ctx_ids[_clean(row.context)]]
    (OUT / "eval_fquad.json").write_text(json.dumps(_eval_set(queries, corpus, qrels), ensure_ascii=False), "utf-8")

    rng.shuffle(pairs)
    rng.shuffle(triplets)
    with open(OUT / "train_pairs.jsonl", "w", encoding="utf-8") as fh:
        for r in pairs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT / "train_triplets.jsonl", "w", encoding="utf-8") as fh:
        for r in triplets:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    stats["total_pairs"] = len(pairs)
    stats["total_triplets"] = len(triplets)
    (OUT / "stats.json").write_text(json.dumps(stats, indent=2), "utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
