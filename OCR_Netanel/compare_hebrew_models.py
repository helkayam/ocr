#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
סקריפט דוגמה להשוואת מספר מודלים של המרת PDF לטקסט עברי
"""

from hebrew_pdf_comparison import HebrewPDFTextComparator
import json
from pathlib import Path
from collections import defaultdict


def compare_multiple_hebrew_models(optimal_dir: str, model_dirs: dict, 
                                   output_file: str = 'hebrew_models_comparison.json'):
    """
    משווה מספר מודלים של OCR עברי ומציג טבלת השוואה מפורטת
    
    Args:
        optimal_dir: תיקייה עם קבצי הטקסט האופטימליים
        model_dirs: מילון של {שם_מודל: נתיב_תיקייה}
        output_file: קובץ פלט ל-JSON
    """
    all_results = {}
    summary = []
    error_analysis = defaultdict(lambda: defaultdict(int))
    
    print("🔬 מתחיל השוואת מודלי OCR עבריים...\n")
    print("="*90)
    
    for model_name, model_dir in model_dirs.items():
        print(f"\n📊 בודק מודל: {model_name}")
        print("-"*90)
        
        if not Path(model_dir).exists():
            print(f"⚠️ אזהרה: תיקייה {model_dir} לא קיימת - מדלג")
            continue
        
        # יצירת אובייקט השוואה
        comparator = HebrewPDFTextComparator(optimal_dir, model_dir)
        
        # ביצוע השוואה
        results = comparator.compare_all(save_diff=False, detect_errors=True)
        
        if 'error' not in results:
            all_results[model_name] = results
            
            # איסוף נתוני שגיאות
            for result in results['individual_results']:
                if result['common_ocr_errors'] != 'לא זוהו שגיאות':
                    for error_type, examples in result['common_ocr_errors'].items():
                        error_analysis[model_name][error_type] += len(examples)
            
            # הוספה לסיכום
            summary.append({
                'model': model_name,
                'overall_score': results['average_overall_score'],
                'hebrew_char_accuracy': results['average_hebrew_char_accuracy'],
                'word_accuracy': results['average_word_accuracy'],
                'line_accuracy': results['average_line_accuracy'],
                'semantic_overlap': results['average_semantic_overlap'],
                'total_missing_words': results['total_missing_words'],
                'files_compared': results['total_files']
            })
            
            # הצגת תוצאות תמציתיות
            print(f"✅ ציון כולל: {results['average_overall_score']}%")
            print(f"   דיוק תווים עבריים: {results['average_hebrew_char_accuracy']}%")
            print(f"   דיוק מילים: {results['average_word_accuracy']}%")
            print(f"   מילים חסרות: {results['total_missing_words']}")
        else:
            print(f"❌ שגיאה: {results['error']}")
    
    print("\n" + "="*90)
    print("📈 טבלת השוואה - דירוג מודלי OCR עבריים")
    print("="*90)
    
    # מיון לפי ציון כולל
    summary_sorted = sorted(summary, key=lambda x: x['overall_score'], reverse=True)
    
    # הדפסת כותרת
    print(f"{'מקום':<6}{'מודל':<25}{'ציון כולל':<13}{'תווים עברי':<13}{'מילים':<13}{'מילים חסרות':<15}")
    print("-"*90)
    
    # הדפסת תוצאות
    for idx, result in enumerate(summary_sorted, 1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
        print(f"{medal:<6}{result['model']:<25}{result['overall_score']:<12.2f}%"
              f"{result['hebrew_char_accuracy']:<12.2f}%{result['word_accuracy']:<12.2f}%"
              f"{result['total_missing_words']:<15}")
    
    print("="*90)
    
    # ניתוח שגיאות OCR
    if error_analysis:
        print("\n" + "="*90)
        print("🔍 ניתוח שגיאות OCR נפוצות בעברית")
        print("="*90)
        
        error_names = {
            'ו_י': 'בלבול בין ו\' לי\'',
            'ה_ח': 'בלבול בין ה\' לח\'',
            'ד_ר': 'בלבול בין ד\' לר\'',
            'כ_ב': 'בלבול בין כ\' לב\'',
            'ס_ם': 'בלבול בין ס\' לם סופית',
            'final_letter': 'טעויות באותיות סופיות'
        }
        
        for model_name, errors in error_analysis.items():
            print(f"\n📊 {model_name}:")
            if errors:
                for error_type, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
                    error_desc = error_names.get(error_type, error_type)
                    print(f"   - {error_desc}: {count} מקרים")
            else:
                print("   ✅ לא זוהו שגיאות נפוצות")
        
        print("="*90)
    
    # המלצה
    if summary_sorted:
        best_model = summary_sorted[0]
        print(f"\n🏆 המודל המומלץ לעברית: {best_model['model']}")
        print(f"   ציון: {best_model['overall_score']}%")
        print(f"   דיוק תווים עבריים: {best_model['hebrew_char_accuracy']}%")
        print(f"   מילים חסרות: {best_model['total_missing_words']}")
        
        if len(summary_sorted) > 1:
            gap = best_model['overall_score'] - summary_sorted[1]['overall_score']
            print(f"   יתרון על המקום השני: {gap:.2f}%")
        
        # ניתוח נקודות חוזק וחולשה
        print(f"\n💪 נקודות חוזק:")
        if best_model['hebrew_char_accuracy'] >= 95:
            print(f"   ✓ זיהוי מעולה של תווים עבריים ({best_model['hebrew_char_accuracy']}%)")
        if best_model['word_accuracy'] >= 90:
            print(f"   ✓ דיוק גבוה בזיהוי מילים שלמות ({best_model['word_accuracy']}%)")
        if best_model['total_missing_words'] < 10:
            print(f"   ✓ מעט מילים חסרות ({best_model['total_missing_words']})")
        
        if best_model['overall_score'] < 90:
            print(f"\n⚠️ תחומים לשיפור:")
            if best_model['hebrew_char_accuracy'] < 90:
                print(f"   - דיוק תווים עבריים נמוך ({best_model['hebrew_char_accuracy']}%)")
            if best_model['word_accuracy'] < 85:
                print(f"   - דיוק מילים נמוך ({best_model['word_accuracy']}%)")
            if best_model['total_missing_words'] > 50:
                print(f"   - מספר גבוה של מילים חסרות ({best_model['total_missing_words']})")
    
    # שמירת תוצאות מלאות
    output_data = {
        'summary': summary_sorted,
        'detailed_results': all_results,
        'error_analysis': dict(error_analysis)
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 תוצאות מפורטות נשמרו ל: {output_file}")
    print("\n✅ סיום!\n")
    
    return summary_sorted, all_results


def generate_hebrew_html_report(summary: list, error_analysis: dict, 
                                output_file: str = 'hebrew_comparison_report.html'):
    """יצירת דוח HTML מפורט עם גרפים"""
    html_content = f"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>דוח השוואת מודלי OCR עבריים</title>
    <style>
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            border-bottom: 4px solid #3498db;
            padding-bottom: 20px;
            margin-bottom: 30px;
            font-size: 2.5em;
        }}
        h2 {{
            color: #34495e;
            margin-top: 40px;
            padding: 10px;
            background: linear-gradient(to right, #3498db, #2ecc71);
            color: white;
            border-radius: 5px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }}
        .summary-card:hover {{
            transform: translateY(-5px);
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .summary-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 15px;
            text-align: right;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: bold;
            position: sticky;
            top: 0;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        .medal {{
            font-size: 28px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}
        .score {{
            font-weight: bold;
            font-size: 18px;
        }}
        .score-excellent {{ 
            color: #27ae60;
            background: #d5f4e6;
            padding: 5px 10px;
            border-radius: 5px;
        }}
        .score-good {{ 
            color: #f39c12;
            background: #fef5e7;
            padding: 5px 10px;
            border-radius: 5px;
        }}
        .score-fair {{ 
            color: #e74c3c;
            background: #fadbd8;
            padding: 5px 10px;
            border-radius: 5px;
        }}
        .bar-container {{
            background-color: #ecf0f1;
            height: 25px;
            border-radius: 12px;
            overflow: hidden;
            position: relative;
        }}
        .bar {{
            background: linear-gradient(90deg, #3498db 0%, #2ecc71 100%);
            height: 100%;
            border-radius: 12px;
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 12px;
        }}
        .error-section {{
            margin: 30px 0;
            padding: 25px;
            background-color: #fff5f5;
            border-right: 5px solid #e74c3c;
            border-radius: 8px;
        }}
        .error-item {{
            display: flex;
            justify-content: space-between;
            padding: 12px;
            margin: 8px 0;
            background: white;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        }}
        .error-type {{
            font-weight: bold;
            color: #34495e;
        }}
        .error-count {{
            background: #e74c3c;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
        }}
        .info-box {{
            margin-top: 30px;
            padding: 25px;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-radius: 10px;
            border-right: 5px solid #3498db;
        }}
        .info-box h3 {{
            color: #2c3e50;
            margin-top: 0;
        }}
        .info-box ul {{
            line-height: 1.8;
        }}
        .recommendation {{
            background: linear-gradient(135deg, #ffeaa7 0%, #fdcb6e 100%);
            padding: 25px;
            border-radius: 10px;
            margin: 30px 0;
            border-right: 5px solid #f39c12;
        }}
        .recommendation h3 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        @media print {{
            body {{
                background: white;
            }}
            .container {{
                box-shadow: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 דוח השוואת מודלי OCR עבריים</h1>
        
        <div class="summary-grid">
            <div class="summary-card">
                <h3>מספר מודלים</h3>
                <div class="value">{len(summary)}</div>
            </div>
            <div class="summary-card">
                <h3>ציון ממוצע</h3>
                <div class="value">{sum(s['overall_score'] for s in summary) / len(summary):.1f}%</div>
            </div>
            <div class="summary-card">
                <h3>מודל מוביל</h3>
                <div class="value" style="font-size: 1.5em;">{summary[0]['model']}</div>
            </div>
        </div>
        
        <h2>🏆 דירוג מודלים</h2>
        <table>
            <thead>
                <tr>
                    <th>מקום</th>
                    <th>שם המודל</th>
                    <th>ציון כולל</th>
                    <th>תווים עבריים</th>
                    <th>דיוק מילים</th>
                    <th>דיוק שורות</th>
                    <th>חפיפה סמנטית</th>
                    <th>מילים חסרות</th>
                    <th>תצוגה גרפית</th>
                </tr>
            </thead>
            <tbody>
"""
    
    medals = ["🥇", "🥈", "🥉"]
    
    for idx, result in enumerate(summary):
        medal = medals[idx] if idx < 3 else f"{idx+1}"
        score_class = "score-excellent" if result['overall_score'] >= 90 else "score-good" if result['overall_score'] >= 75 else "score-fair"
        
        html_content += f"""
                <tr>
                    <td class="medal" style="text-align: center;">{medal}</td>
                    <td><strong>{result['model']}</strong></td>
                    <td class="score {score_class}">{result['overall_score']:.2f}%</td>
                    <td>{result['hebrew_char_accuracy']:.2f}%</td>
                    <td>{result['word_accuracy']:.2f}%</td>
                    <td>{result['line_accuracy']:.2f}%</td>
                    <td>{result['semantic_overlap']:.2f}%</td>
                    <td>{result['total_missing_words']}</td>
                    <td>
                        <div class="bar-container">
                            <div class="bar" style="width: {result['overall_score']}%;">
                                {result['overall_score']:.1f}%
                            </div>
                        </div>
                    </td>
                </tr>
"""
    
    html_content += """
            </tbody>
        </table>
"""
    
    # הוספת ניתוח שגיאות אם קיים
    if error_analysis:
        html_content += """
        <h2>🔍 ניתוח שגיאות OCR נפוצות</h2>
"""
        error_names = {
            'ו_י': 'בלבול בין ו\' לי\'',
            'ה_ח': 'בלבול בין ה\' לח\'',
            'ד_ר': 'בלבול בין ד\' לר\'',
            'כ_ב': 'בלבול בין כ\' לב\'',
            'ס_ם': 'בלבול בין ס\' לם סופית',
            'final_letter': 'טעויות באותיות סופיות'
        }
        
        for model_name, errors in error_analysis.items():
            html_content += f"""
        <div class="error-section">
            <h3>📊 {model_name}</h3>
"""
            if errors:
                for error_type, count in sorted(errors.items(), key=lambda x: x[1], reverse=True):
                    error_desc = error_names.get(error_type, error_type)
                    html_content += f"""
            <div class="error-item">
                <span class="error-type">{error_desc}</span>
                <span class="error-count">{count}</span>
            </div>
"""
            else:
                html_content += """
            <p style="color: #27ae60; font-weight: bold;">✅ לא זוהו שגיאות נפוצות</p>
"""
            html_content += """
        </div>
"""
    
    # המלצה
    best_model = summary[0]
    html_content += f"""
        <div class="recommendation">
            <h3>🏆 המלצה</h3>
            <p style="font-size: 1.2em;"><strong>המודל המומלץ לעברית:</strong> {best_model['model']}</p>
            <p><strong>ציון:</strong> {best_model['overall_score']:.2f}%</p>
            <p><strong>דיוק תווים עבריים:</strong> {best_model['hebrew_char_accuracy']:.2f}%</p>
            <p><strong>דיוק מילים:</strong> {best_model['word_accuracy']:.2f}%</p>
            <p><strong>מילים חסרות:</strong> {best_model['total_missing_words']}</p>
"""
    
    if len(summary) > 1:
        gap = best_model['overall_score'] - summary[1]['overall_score']
        html_content += f"""
            <p><strong>יתרון על המקום השני:</strong> {gap:.2f}%</p>
"""
    
    html_content += """
        </div>
        
        <div class="info-box">
            <h3>📝 הסבר על המדדים:</h3>
            <ul>
                <li><strong>ציון כולל:</strong> ממוצע משוקלל של כל המדדים, עם דגש על דיוק תווים עבריים (35%)</li>
                <li><strong>תווים עבריים:</strong> אחוז התווים העבריים הנכונים (כולל התעלמות מאותיות סופיות)</li>
                <li><strong>דיוק מילים:</strong> אחוז המילים העבריות הנכונות</li>
                <li><strong>דיוק שורות:</strong> שמירה על מבנה השורות והפסקאות המקורי</li>
                <li><strong>חפיפה סמנטית:</strong> דמיון תוכני בין הטקסטים (מדד Overlap)</li>
                <li><strong>מילים חסרות:</strong> מספר המילים שהופיעו בטקסט האופטימלי אך חסרות בפלט המודל</li>
            </ul>
        </div>
        
        <div class="info-box">
            <h3>🔍 שגיאות OCR נפוצות בעברית:</h3>
            <ul>
                <li><strong>בלבול בין ו' לי':</strong> אותיות דומות מבחינה ויזואלית</li>
                <li><strong>בלבול בין ה' לח':</strong> מבנה דומה בגופנים מסוימים</li>
                <li><strong>בלבול בין ד' לר':</strong> התרחש בעיקר בטקסט ידני או באיכות נמוכה</li>
                <li><strong>טעויות באותיות סופיות:</strong> אי-זיהוי נכון של כ/ך, מ/ם, נ/ן, פ/ף, צ/ץ</li>
            </ul>
        </div>
        
        <p style="text-align: center; color: #7f8c8d; margin-top: 40px;">
            נוצר בתאריך: """ + """<span id="date"></span>
        </p>
    </div>
    
    <script>
        document.getElementById('date').textContent = new Date().toLocaleDateString('he-IL');
    </script>
</body>
</html>
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"📄 דוח HTML מפורט נוצר: {output_file}")


def main():
    """פונקציה ראשית לדוגמה"""
    
    # הגדרת תיקיות - התאם לפי המבנה שלך
    optimal_dir = 'optimal_texts_hebrew'
    
    # מילון של מודלים לבדיקה
    model_dirs = {
        'Tesseract Hebrew': 'tesseract_output',
        'EasyOCR Hebrew': 'easyocr_output',
        'Google Vision API': 'google_vision_output',
        'AWS Textract': 'aws_textract_output',
        'Azure Read API': 'azure_read_output'
    }
    
    # בדיקה אם תיקיית הטקסט האופטימלי קיימת
    if not Path(optimal_dir).exists():
        print(f"❌ שגיאה: תיקייה {optimal_dir} לא קיימת")
        print("\nאנא צור תיקיות לפי המבנה הבא:")
        print("optimal_texts_hebrew/   # קבצי הטקסט העברי האופטימליים")
        print("tesseract_output/       # פלט Tesseract")
        print("easyocr_output/         # פלט EasyOCR")
        print("...")
        return
    
    # הרצת השוואה
    summary, all_results = compare_multiple_hebrew_models(optimal_dir, model_dirs)
    
    # יצירת דוח HTML
    if summary:
        # איסוף נתוני שגיאות לדוח HTML
        error_analysis = {}
        for model_name, results in all_results.items():
            model_errors = {}
            for result in results['individual_results']:
                if result['common_ocr_errors'] != 'לא זוהו שגיאות':
                    for error_type, examples in result['common_ocr_errors'].items():
                        model_errors[error_type] = model_errors.get(error_type, 0) + len(examples)
            if model_errors:
                error_analysis[model_name] = model_errors
        
        generate_hebrew_html_report(summary, error_analysis)


if __name__ == "__main__":
    main()
