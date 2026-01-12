#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
סקריפט להשוואת דיוק המרת PDF לטקסט - מותאם לעברית
משווה בין קובץ אופטימלי (ground truth) לבין פלט של מודל
כולל אלגוריתמים ייעודיים לשפה העברית
"""

import os
import difflib
from pathlib import Path
import json
from typing import Dict, List, Tuple, Set
import re
from collections import Counter
import unicodedata
import Levenshtein  # pip install python-Levenshtein


class HebrewPDFTextComparator:
    """מחלקה להשוואת קבצי טקסט עבריים ממרות PDF"""
    
    # תווים עבריים
    HEBREW_CHARS = set('אבגדהוזחטיכךלמםנןסעפףצץקרשת')
    
    # ניקוד עברי
    NIKUD = set([
        '\u05B0',  # שווא
        '\u05B1',  # חטף סגול
        '\u05B2',  # חטף פתח
        '\u05B3',  # חטף קמץ
        '\u05B4',  # חיריק
        '\u05B5',  # צירה
        '\u05B6',  # סגול
        '\u05B7',  # פתח
        '\u05B8',  # קמץ
        '\u05B9',  # חולם
        '\u05BB',  # קובוץ
        '\u05BC',  # דגש
        '\u05BD',  # מתג
        '\u05BF',  # רפה
        '\u05C1',  # שין
        '\u05C2',  # שין שמאלית
        '\u05C3',  # סוף פסוק
        '\u05C4',  # פיסוק עליון
    ])
    
    # סימני פיסוק עבריים
    HEBREW_PUNCTUATION = set('׃׀׆״׳')
    
    # אותיות סופיות ואותיות רגילות מקבילות
    FINAL_LETTERS = {
        'ך': 'כ',
        'ם': 'מ',
        'ן': 'נ',
        'ף': 'פ',
        'ץ': 'צ'
    }
    
    def __init__(self, optimal_dir: str, model_output_dir: str):
        """
        Args:
            optimal_dir: תיקייה עם קבצי הטקסט האופטימליים
            model_output_dir: תיקייה עם קבצי הטקסט שהמודל הפיק
        """
        self.optimal_dir = Path(optimal_dir)
        self.model_output_dir = Path(model_output_dir)
    
    def remove_nikud(self, text: str) -> str:
        """הסרת ניקוד מטקסט עברי"""
        return ''.join(char for char in text if char not in self.NIKUD)
    
    def normalize_hebrew_text(self, text: str, aggressive: bool = False) -> str:
        """
        נרמול טקסט עברי
        
        Args:
            text: טקסט להנרמול
            aggressive: האם לבצע נרמול אגרסיבי (להתעלם מאותיות סופיות)
        """
        # הסרת ניקוד
        text = self.remove_nikud(text)
        
        # נרמול רווחים
        text = re.sub(r'\s+', ' ', text)
        
        # הסרת רווחים בתחילת ובסוף שורות
        text = '\n'.join(line.strip() for line in text.split('\n'))
        
        # הסרת שורות ריקות מרובות
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # נרמול Unicode (NFC)
        text = unicodedata.normalize('NFC', text)
        
        # במצב אגרסיבי - המרת אותיות סופיות לרגילות
        if aggressive:
            for final, regular in self.FINAL_LETTERS.items():
                text = text.replace(final, regular)
        
        return text.strip()
    
    def count_hebrew_characters(self, text: str) -> Dict[str, int]:
        """ספירת תווים עבריים בטקסט"""
        char_count = Counter()
        for char in text:
            if char in self.HEBREW_CHARS or char in self.FINAL_LETTERS:
                char_count[char] += 1
        
        return {
            'total_hebrew_chars': sum(char_count.values()),
            'unique_hebrew_chars': len(char_count),
            'char_distribution': dict(char_count.most_common(10))
        }
    
    def detect_common_ocr_errors(self, optimal: str, model: str) -> Dict[str, List[Tuple[str, str]]]:
        """זיהוי שגיאות OCR נפוצות בעברית"""
        common_errors = {
            'ו_י': [],  # בלבול בין ו' לי'
            'ה_ח': [],  # בלבול בין ה' לח'
            'ד_ר': [],  # בלבול בין ד' לר'
            'כ_ב': [],  # בלבול בין כ' לב'
            'ס_ם': [],  # בלבול בין ס' לם סופית
            'final_letter': [],  # טעויות באותיות סופיות
            'nikud_loss': [],  # אובדן ניקוד
        }
        
        optimal_words = optimal.split()
        model_words = model.split()
        
        # השוואת מילים
        matcher = difflib.SequenceMatcher(None, optimal_words, model_words)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                for opt_word, model_word in zip(optimal_words[i1:i2], model_words[j1:j2]):
                    # בדיקת טעויות נפוצות
                    if 'ו' in opt_word and 'י' in model_word:
                        common_errors['ו_י'].append((opt_word, model_word))
                    if 'ה' in opt_word and 'ח' in model_word:
                        common_errors['ה_ח'].append((opt_word, model_word))
                    if 'ד' in opt_word and 'ר' in model_word:
                        common_errors['ד_ר'].append((opt_word, model_word))
                    if 'כ' in opt_word and 'ב' in model_word:
                        common_errors['כ_ב'].append((opt_word, model_word))
                    
                    # בדיקת אותיות סופיות
                    for final, regular in self.FINAL_LETTERS.items():
                        if final in opt_word and regular in model_word:
                            common_errors['final_letter'].append((opt_word, model_word))
        
        return {k: v for k, v in common_errors.items() if v}
    
    def calculate_hebrew_character_accuracy(self, optimal: str, model: str) -> Dict[str, float]:
        """חישוב דיוק תווים עבריים בלבד"""
        # סינון רק תווים עבריים
        optimal_hebrew = ''.join(c for c in optimal if c in self.HEBREW_CHARS or c in self.FINAL_LETTERS)
        model_hebrew = ''.join(c for c in model if c in self.HEBREW_CHARS or c in self.FINAL_LETTERS)
        
        # דיוק מדויק
        distance_exact = Levenshtein.distance(optimal_hebrew, model_hebrew)
        max_len_exact = max(len(optimal_hebrew), len(model_hebrew))
        exact_accuracy = (1 - distance_exact / max_len_exact) * 100 if max_len_exact > 0 else 100.0
        
        # דיוק עם התעלמות מאותיות סופיות
        optimal_normalized = optimal_hebrew
        model_normalized = model_hebrew
        for final, regular in self.FINAL_LETTERS.items():
            optimal_normalized = optimal_normalized.replace(final, regular)
            model_normalized = model_normalized.replace(final, regular)
        
        distance_normalized = Levenshtein.distance(optimal_normalized, model_normalized)
        max_len_normalized = max(len(optimal_normalized), len(model_normalized))
        normalized_accuracy = (1 - distance_normalized / max_len_normalized) * 100 if max_len_normalized > 0 else 100.0
        
        return {
            'exact_accuracy': round(exact_accuracy, 2),
            'normalized_accuracy': round(normalized_accuracy, 2),
            'hebrew_chars_optimal': len(optimal_hebrew),
            'hebrew_chars_model': len(model_hebrew)
        }
    
    def calculate_word_accuracy(self, optimal: str, model: str) -> Dict[str, float]:
        """חישוב דיוק ברמת מילים עבריות"""
        optimal_words = optimal.split()
        model_words = model.split()
        
        # דיוק מדויק
        matcher = difflib.SequenceMatcher(None, optimal_words, model_words)
        exact_ratio = matcher.ratio() * 100
        
        # חישוב WER (Word Error Rate)
        distance = Levenshtein.distance(' '.join(optimal_words), ' '.join(model_words))
        wer = (distance / len(optimal_words)) * 100 if optimal_words else 0
        word_accuracy = max(0, 100 - wer)
        
        # דיוק עם נרמול (התעלמות מאותיות סופיות)
        optimal_normalized = ' '.join(optimal_words)
        model_normalized = ' '.join(model_words)
        for final, regular in self.FINAL_LETTERS.items():
            optimal_normalized = optimal_normalized.replace(final, regular)
            model_normalized = model_normalized.replace(final, regular)
        
        optimal_words_norm = optimal_normalized.split()
        model_words_norm = model_normalized.split()
        matcher_norm = difflib.SequenceMatcher(None, optimal_words_norm, model_words_norm)
        normalized_ratio = matcher_norm.ratio() * 100
        
        return {
            'exact_match': round(exact_ratio, 2),
            'word_accuracy': round(word_accuracy, 2),
            'normalized_match': round(normalized_ratio, 2),
            'total_words_optimal': len(optimal_words),
            'total_words_model': len(model_words)
        }
    
    def calculate_line_accuracy(self, optimal: str, model: str) -> float:
        """חישוב דיוק ברמת שורות"""
        optimal_lines = [line.strip() for line in optimal.split('\n') if line.strip()]
        model_lines = [line.strip() for line in model.split('\n') if line.strip()]
        
        matcher = difflib.SequenceMatcher(None, optimal_lines, model_lines)
        return round(matcher.ratio() * 100, 2)
    
    def calculate_hebrew_semantic_similarity(self, optimal: str, model: str) -> Dict[str, float]:
        """חישוב דמיון סמנטי - מותאם לעברית"""
        # הסרת ניקוד ונרמול
        optimal_normalized = self.normalize_hebrew_text(optimal, aggressive=False)
        model_normalized = self.normalize_hebrew_text(model, aggressive=False)
        
        optimal_words = set(optimal_normalized.split())
        model_words = set(model_normalized.split())
        
        if not optimal_words:
            return {'jaccard': 0.0, 'overlap': 0.0, 'missing_words': 0}
        
        intersection = optimal_words & model_words
        union = optimal_words | model_words
        missing = optimal_words - model_words
        
        jaccard = len(intersection) / len(union) if union else 0
        overlap = len(intersection) / len(optimal_words) if optimal_words else 0
        
        return {
            'jaccard': round(jaccard * 100, 2),
            'overlap': round(overlap * 100, 2),
            'missing_words_count': len(missing),
            'missing_words': list(missing)[:10]  # רק 10 הראשונות
        }
    
    def analyze_hebrew_text_quality(self, text: str) -> Dict:
        """ניתוח איכות טקסט עברי"""
        total_chars = len(text)
        hebrew_chars = sum(1 for c in text if c in self.HEBREW_CHARS or c in self.FINAL_LETTERS)
        nikud_chars = sum(1 for c in text if c in self.NIKUD)
        spaces = text.count(' ')
        newlines = text.count('\n')
        
        # בדיקת יחס אותיות סופיות
        final_letter_count = sum(1 for c in text if c in self.FINAL_LETTERS)
        
        return {
            'total_characters': total_chars,
            'hebrew_characters': hebrew_chars,
            'hebrew_percentage': round(hebrew_chars / total_chars * 100, 2) if total_chars > 0 else 0,
            'nikud_characters': nikud_chars,
            'has_nikud': nikud_chars > 0,
            'spaces': spaces,
            'lines': newlines + 1,
            'final_letters': final_letter_count,
            'avg_word_length': round(hebrew_chars / (spaces + 1), 2) if spaces > 0 else 0
        }
    
    def generate_hebrew_diff_report(self, optimal: str, model: str) -> str:
        """יצירת דוח הבדלים מפורט לעברית"""
        optimal_lines = optimal.split('\n')
        model_lines = model.split('\n')
        
        diff = difflib.unified_diff(
            optimal_lines,
            model_lines,
            lineterm='',
            fromfile='טקסט אופטימלי',
            tofile='פלט המודל'
        )
        
        return '\n'.join(diff)
    
    def compare_files(self, optimal_file: Path, model_file: Path, 
                     detect_errors: bool = True) -> Dict:
        """השוואה מפורטת בין שני קבצים עבריים"""
        print(f"משווה: {optimal_file.name} <-> {model_file.name}")
        
        # קריאת קבצים
        with open(optimal_file, 'r', encoding='utf-8') as f:
            optimal_text = f.read()
        with open(model_file, 'r', encoding='utf-8') as f:
            model_text = f.read()
        
        # ניתוח איכות
        optimal_quality = self.analyze_hebrew_text_quality(optimal_text)
        model_quality = self.analyze_hebrew_text_quality(model_text)
        
        # נרמול
        optimal_normalized = self.normalize_hebrew_text(optimal_text)
        model_normalized = self.normalize_hebrew_text(model_text)
        
        # חישוב מדדים
        hebrew_char_metrics = self.calculate_hebrew_character_accuracy(optimal_normalized, model_normalized)
        word_metrics = self.calculate_word_accuracy(optimal_normalized, model_normalized)
        line_accuracy = self.calculate_line_accuracy(optimal_normalized, model_normalized)
        semantic_metrics = self.calculate_hebrew_semantic_similarity(optimal_normalized, model_normalized)
        
        # זיהוי שגיאות נפוצות
        ocr_errors = {}
        if detect_errors:
            ocr_errors = self.detect_common_ocr_errors(optimal_normalized, model_normalized)
        
        # חישוב ציון כולל משוקלל - מותאם לעברית
        overall_score = (
            hebrew_char_metrics['normalized_accuracy'] * 0.35 +  # משקל גבוה יותר לתווים עבריים
            word_metrics['word_accuracy'] * 0.30 +
            line_accuracy * 0.15 +
            semantic_metrics['overlap'] * 0.20
        )
        
        result = {
            'file': optimal_file.name,
            
            # מדדי דיוק תווים עבריים
            'hebrew_char_exact_accuracy': hebrew_char_metrics['exact_accuracy'],
            'hebrew_char_normalized_accuracy': hebrew_char_metrics['normalized_accuracy'],
            
            # מדדי דיוק מילים
            'word_exact_match': word_metrics['exact_match'],
            'word_accuracy': word_metrics['word_accuracy'],
            'word_normalized_match': word_metrics['normalized_match'],
            
            # מדדי דיוק שורות ומבנה
            'line_accuracy': line_accuracy,
            
            # מדדים סמנטיים
            'semantic_jaccard': semantic_metrics['jaccard'],
            'semantic_overlap': semantic_metrics['overlap'],
            'missing_words_count': semantic_metrics['missing_words_count'],
            
            # ציון כולל
            'overall_score': round(overall_score, 2),
            
            # נתוני איכות
            'optimal_quality': optimal_quality,
            'model_quality': model_quality,
            
            # שגיאות OCR נפוצות
            'common_ocr_errors': ocr_errors if ocr_errors else 'לא זוהו שגיאות',
            
            # נתונים נוספים
            'hebrew_chars_ratio': round(
                model_quality['hebrew_characters'] / optimal_quality['hebrew_characters'] * 100, 2
            ) if optimal_quality['hebrew_characters'] > 0 else 0
        }
        
        return result
    
    def compare_all(self, save_diff: bool = False, detect_errors: bool = True) -> Dict:
        """השוואה בין כל הקבצים בתיקיות"""
        results = []
        
        # מציאת כל קבצי הטקסט בתיקייה האופטימלית
        optimal_files = sorted(self.optimal_dir.glob('*.txt'))
        
        if not optimal_files:
            print(f"שגיאה: לא נמצאו קבצי txt בתיקייה {self.optimal_dir}")
            return {}
        
        print(f"נמצאו {len(optimal_files)} קבצים עבריים להשוואה\n")
        
        for optimal_file in optimal_files:
            # חיפוש קובץ מתאים בתיקיית המודל
            model_file = self.model_output_dir / optimal_file.name
            
            if not model_file.exists():
                print(f"אזהרה: קובץ {optimal_file.name} לא נמצא בתיקיית המודל")
                continue
            
            # השוואה
            result = self.compare_files(optimal_file, model_file, detect_errors=detect_errors)
            results.append(result)
            
            # שמירת דוח הבדלים אם נדרש
            if save_diff:
                with open(optimal_file, 'r', encoding='utf-8') as f:
                    optimal_text = f.read()
                with open(model_file, 'r', encoding='utf-8') as f:
                    model_text = f.read()
                
                diff_report = self.generate_hebrew_diff_report(optimal_text, model_text)
                diff_file = Path(f'diff_{optimal_file.stem}.txt')
                with open(diff_file, 'w', encoding='utf-8') as f:
                    f.write(diff_report)
        
        # חישוב ממוצעים
        if results:
            avg_results = {
                'total_files': len(results),
                'average_hebrew_char_accuracy': round(
                    sum(r['hebrew_char_normalized_accuracy'] for r in results) / len(results), 2
                ),
                'average_word_accuracy': round(
                    sum(r['word_accuracy'] for r in results) / len(results), 2
                ),
                'average_line_accuracy': round(
                    sum(r['line_accuracy'] for r in results) / len(results), 2
                ),
                'average_semantic_overlap': round(
                    sum(r['semantic_overlap'] for r in results) / len(results), 2
                ),
                'average_overall_score': round(
                    sum(r['overall_score'] for r in results) / len(results), 2
                ),
                'total_missing_words': sum(r['missing_words_count'] for r in results),
                'individual_results': results
            }
        else:
            avg_results = {'error': 'לא נמצאו קבצים להשוואה'}
        
        return avg_results
    
    def print_hebrew_report(self, results: Dict):
        """הדפסת דוח מפורט לעברית"""
        if 'error' in results:
            print(f"שגיאה: {results['error']}")
            return
        
        print("\n" + "="*80)
        print("דוח השוואת דיוק המרת PDF לטקסט עברי")
        print("="*80)
        
        print(f"\nמספר קבצים שהושוו: {results['total_files']}")
        print("\n--- ציונים ממוצעים ---")
        print(f"דיוק תווים עבריים (Hebrew Character Accuracy): {results['average_hebrew_char_accuracy']}%")
        print(f"דיוק מילים עבריות (Word Accuracy): {results['average_word_accuracy']}%")
        print(f"דיוק שורות (Line Accuracy): {results['average_line_accuracy']}%")
        print(f"חפיפה סמנטית (Semantic Overlap): {results['average_semantic_overlap']}%")
        print(f"סה\"כ מילים חסרות: {results['total_missing_words']}")
        print(f"\n🎯 ציון כולל משוקלל: {results['average_overall_score']}%")
        
        print("\n--- תוצאות לפי קובץ ---")
        for result in results['individual_results']:
            print(f"\n📄 {result['file']}")
            print(f"  ציון כולל: {result['overall_score']}%")
            print(f"  דיוק תווים עבריים: {result['hebrew_char_normalized_accuracy']}%")
            print(f"  דיוק מילים: {result['word_accuracy']}%")
            print(f"  דיוק שורות: {result['line_accuracy']}%")
            print(f"  חפיפה סמנטית: {result['semantic_overlap']}%")
            print(f"  אחוז תווים עבריים (אופטימלי): {result['optimal_quality']['hebrew_percentage']}%")
            print(f"  אחוז תווים עבריים (מודל): {result['model_quality']['hebrew_percentage']}%")
            print(f"  מילים חסרות: {result['missing_words_count']}")
            
            # הצגת שגיאות OCR נפוצות
            if result['common_ocr_errors'] != 'לא זוהו שגיאות':
                print(f"  🔍 שגיאות OCR נפוצות:")
                for error_type, examples in result['common_ocr_errors'].items():
                    if examples:
                        print(f"     - {error_type}: {len(examples)} מקרים")
        
        print("\n" + "="*80)
        
        # הערכה כללית
        score = results['average_overall_score']
        if score >= 95:
            grade = "מצוין! המודל מתאים מאוד לעברית 🌟"
        elif score >= 90:
            grade = "טוב מאוד! המודל עובד יפה עם עברית ✅"
        elif score >= 80:
            grade = "טוב - המודל מטפל בעברית באופן סביר 👍"
        elif score >= 70:
            grade = "בינוני - יש בעיות בזיהוי תווים עבריים 🤔"
        else:
            grade = "נמוך - המודל נתקל בקשיים משמעותיים בעברית 📉"
        
        print(f"\nהערכה: {grade}")
        print("="*80 + "\n")
    
    def save_json_report(self, results: Dict, output_file: str = 'hebrew_comparison_results.json'):
        """שמירת תוצאות לקובץ JSON"""
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"תוצאות נשמרו לקובץ: {output_file}")


def main():
    """פונקציה ראשית"""
    print("🔍 מערכת להשוואת דיוק המרת PDF לטקסט עברי\n")
    print("מערכת זו מותאמת במיוחד לשפה העברית ומזהה שגיאות נפוצות\n")
    
    # הגדרת תיקיות - שנה את הנתיבים לפי הצורך
    optimal_dir = "TEST_FILES\\optimal"
    model_output_dir = "extraction"
    
    # בדיקת קיום התיקיות
    if not os.path.exists(optimal_dir):
        print(f"שגיאה: התיקייה {optimal_dir} לא קיימת")
        return
    
    if not os.path.exists(model_output_dir):
        print(f"שגיאה: התיקייה {model_output_dir} לא קיימת")
        return
    
    # יצירת אובייקט השוואה
    comparator = HebrewPDFTextComparator(optimal_dir, model_output_dir)
    
    # ביצוע השוואה
    print("\nמתחיל השוואה של טקסט עברי...\n")
    results = comparator.compare_all(save_diff=False, detect_errors=True)
    
    # הצגת תוצאות
    comparator.print_hebrew_report(results)
    
    # שמירת תוצאות ל-JSON
    save_json = input("\nלשמור תוצאות לקובץ JSON? (y/n): ").strip().lower()
    if save_json == 'y':
        comparator.save_json_report(results)
    
    print("\n✅ סיום!")


if __name__ == "__main__":
    main()
