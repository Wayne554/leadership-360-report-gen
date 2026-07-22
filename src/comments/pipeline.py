"""评语编码管线 — 统一入口。"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from src.comments.config import COMMENT_CACHE_DIR
from src.comments.preprocess import run_preprocess
from src.comments.keywords import extract_keywords_file
from src.comments.selection import run_selection
from src.comments.encoding import run_encoding
logger = logging.getLogger(__name__)
def run_one(person_id, level="L4", output_dir=None, use_llm=False, force=False):
    if output_dir is None:
        output_dir = Path(COMMENT_CACHE_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    pre_path = output_dir / f"{person_id}.json"
    if force or not pre_path.exists():
        from src.comments.preprocess import load_raw_data, preprocess_one_person
        df, rater_id_col, user_id_col = load_raw_data(level)
        person_df = df[df[user_id_col].astype(str) == str(person_id)]
        if len(person_df) == 0:
            raise ValueError(f"Person {person_id} not found in {level}")
        result = preprocess_one_person(person_df, rater_id_col, person_id, level=level)
        with open(pre_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    kw_path = output_dir / f"{person_id}_keywords.json"
    if force or not kw_path.exists():
        extract_keywords_file(person_id, output_dir, output_dir)
    run_selection(person_id, output_dir)
    enc_path = output_dir / f"{person_id}_encoded.json"
    if force or not enc_path.exists():
        run_encoding(person_id, output_dir, use_llm=use_llm)
    with open(enc_path, "r", encoding="utf-8") as f:
        return json.load(f)
def run_all(level="L4", output_dir=None, max_persons=None, use_llm=False):
    if output_dir is None:
        output_dir = Path(COMMENT_CACHE_DIR)
    stats = {}
    run_preprocess(level, output_dir, max_persons)
    from src.comments.keywords import extract_keywords_all
    extract_keywords_all(level, output_dir, output_dir, max_persons)
    from src.comments.selection import run_selection_all
    run_selection_all(level, output_dir, max_persons)
    from src.comments.encoding import run_encoding_all
    run_encoding_all(level, output_dir, max_persons, use_llm=use_llm)
    stats["phase1"] = len(list(output_dir.glob("[0-9]*.json")))
    stats["phase2"] = len(list(output_dir.glob("*_keywords.json")))
    stats["phase3"] = stats["phase2"]
    stats["phase4"] = len(list(output_dir.glob("*_encoded.json")))
    logger.info("Pipeline done: %s", stats)
    return stats
