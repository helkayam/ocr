import os
import json
import difflib
import re
from collections import Counter

# -----------------------------
# Normalization
# -----------------------------

def normalize_text(text: str) -> str:
    """
    Normalize text for fair OCR comparison.
    """
    text = text.strip()

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Normalize quotes and dashes
    text = text.replace('״', '"').replace('׳', "'")
    text = text.replace('–', '-').replace('—', '-')

    return text


def tokenize_words(text: str):
    return text.split()


def tokenize_chars(text: str):
    return list(text)


# -----------------------------
# Distance Metrics
# -----------------------------

def edit_distance(a, b) -> int:
    """
    Levenshtein distance using difflib (efficient enough for OCR tests).
    """
    matcher = difflib.SequenceMatcher(None, a, b)
    distance = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            distance += max(i2 - i1, j2 - j1)
        elif tag == 'delete':
            distance += (i2 - i1)
        elif tag == 'insert':
            distance += (j2 - j1)

    return distance


def character_error_rate(gt: str, ocr: str) -> float:
    gt_chars = tokenize_chars(gt)
    ocr_chars = tokenize_chars(ocr)

    if not gt_chars:
        return 0.0

    dist = edit_distance(gt_chars, ocr_chars)
    return dist / len(gt_chars)


def word_error_rate(gt: str, ocr: str) -> float:
    gt_words = tokenize_words(gt)
    ocr_words = tokenize_words(ocr)

    if not gt_words:
        return 0.0

    dist = edit_distance(gt_words, ocr_words)
    return dist / len(gt_words)


# -----------------------------
# Line Accuracy
# -----------------------------

def line_accuracy(gt: str, ocr: str) -> float:
    gt_lines = [l.strip() for l in gt.splitlines() if l.strip()]
    ocr_lines = [l.strip() for l in ocr.splitlines() if l.strip()]

    if not gt_lines:
        return 1.0

    matches = 0
    for line in gt_lines:
        if line in ocr_lines:
            matches += 1

    return matches / len(gt_lines)


# -----------------------------
# OCR Error Analysis
# -----------------------------

def common_character_errors(gt: str, ocr: str, top_n=10):
    errors = Counter()

    matcher = difflib.SequenceMatcher(None, gt, ocr)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            for g, o in zip(gt[i1:i2], ocr[j1:j2]):
                errors[(g, o)] += 1

    return [
        {"expected": g, "ocr": o, "count": c}
        for (g, o), c in errors.most_common(top_n)
    ]


# -----------------------------
# File Comparison
# -----------------------------

def compare_files(gt_path: str, ocr_path: str) -> dict:
    with open(gt_path, 'r', encoding='utf-8') as f:
        gt_raw = f.read()

    with open(ocr_path, 'r', encoding='utf-8') as f:
        ocr_raw = f.read()

    gt = normalize_text(gt_raw)
    ocr = normalize_text(ocr_raw)

    cer = character_error_rate(gt, ocr)
    wer = word_error_rate(gt, ocr)
    la = line_accuracy(gt_raw, ocr_raw)

    score = round((1 - cer) * 0.5 + (1 - wer) * 0.3 + la * 0.2, 4)

    return {
        "character_error_rate": round(cer, 4),
        "word_error_rate": round(wer, 4),
        "line_accuracy": round(la, 4),
        "final_score": score,
        "common_errors": common_character_errors(gt, ocr)
    }


# -----------------------------
# Batch Evaluation
# -----------------------------

def evaluate_directories(optimal_dir: str, extraction_dir: str, output_dir="results"):
    os.makedirs(output_dir, exist_ok=True)

    summary = {}

    for filename in os.listdir(optimal_dir):
        if not filename.endswith(".txt"):
            continue

        gt_path = os.path.join(optimal_dir, filename)
        ocr_path = os.path.join(extraction_dir, filename)

        if not os.path.exists(ocr_path):
            print(f"Missing OCR file for {filename}")
            continue

        result = compare_files(gt_path, ocr_path)
        summary[filename] = result

        with open(os.path.join(output_dir, filename.replace(".txt", ".json")),
                  "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"{filename} → score: {result['final_score']}")

    with open(os.path.join(output_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


# -----------------------------
# Entry Point
# -----------------------------

if __name__ == "__main__":
    evaluate_directories(
        optimal_dir="optimal",
        extraction_dir="extraction"
    )
