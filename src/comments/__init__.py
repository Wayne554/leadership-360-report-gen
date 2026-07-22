"""评语编码管线模块。"""
from src.comments.preprocess import load_raw_data, preprocess_one_person, run_preprocess
from src.comments.keywords import extract_keywords_file, extract_keywords_all, count_keywords_for_person
from src.comments.selection import run_selection, run_selection_all, select_representative_quotes
from src.comments.encoding import run_encoding, run_encoding_all, fallback_encoding
from src.comments.pipeline import run_one, run_all
__all__ = [
    "load_raw_data", "preprocess_one_person", "run_preprocess",
    "extract_keywords_file", "extract_keywords_all", "count_keywords_for_person",
    "run_selection", "run_selection_all", "select_representative_quotes",
    "run_encoding", "run_encoding_all", "fallback_encoding",
    "run_one", "run_all",
]
