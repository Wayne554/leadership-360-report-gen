"""CLI: Prepare RAGFlow context for a person.

Usage:
  python src/rag/prepare_context.py --user_id 10016759 [--level L4]

Outputs:
  data/processed/rag_cache/rag_context_{uid}.json
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.rag.rag_engine import prepare_context, save_context


def main():
    parser = argparse.ArgumentParser(description="Prepare RAGFlow context")
    parser.add_argument("--user_id", type=str, required=True, help="Person ID")
    parser.add_argument("--level", type=str, default="L4", choices=["L3", "L4"])
    parser.add_argument("--top_k", type=int, default=3, help="Chunks per dimension")
    args = parser.parse_args()

    print(f"Preparing RAGFlow context for {args.user_id} ({args.level})...")
    context = prepare_context(args.user_id, args.level, args.top_k)
    path = save_context(context)

    dim_count = len(context.get("dimensions", {}))
    chunk_total = sum(
        len(d.get("chunks", [])) for d in context.get("dimensions", {}).values()
    )
    print(f"  Dimensions retrieved: {dim_count}")
    print(f"  Total chunks: {chunk_total}")
    print(f"  Context saved: {path}")


if __name__ == "__main__":
    main()
