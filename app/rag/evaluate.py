import json
import os
import pandas as pd
from loguru import logger

# אנחנו מייבאים רק את מנגנון החיפוש, בלי ה-LLM ובלי RAGAS
from app.retrieval.search import search

def run_retrieval_evaluation():
    dataset_path = "data/golden_dataset.json"
    
    if not os.path.exists(dataset_path):
        logger.error(f"Golden dataset not found at {dataset_path}")
        return

    with open(dataset_path, "r", encoding="utf-8") as f:
        golden_data = json.load(f)

    logger.info(f"Loaded {len(golden_data)} questions from Golden Dataset.")

    successful_retrievals = 0
    results_log = []
    
    # ההפרש בין העמוד המודפס לבין העמוד המוחלט ב-PDF
    OFFSET = 31 

    logger.info("Starting FAST Retrieval Evaluation (No LLM calls)...")

    for i, item in enumerate(golden_data, start=1):
        query = item["question"]
        expected_pages_original = item["expected_pages"]
        
        # מתקנים את העמודים המצופים לפי ההזחה של ה-PDF
        adjusted_expected_pages = [int(page) + OFFSET for page in expected_pages_original]
        
        # 1. מריצים רק את חיפוש ה-Top 5
        top_5_chunks = search(query=query, top_k=5)
        
        # 2. שולפים מתוך הצ'אנקים שחזרו רק את מספרי העמודים שלהם (ומוודאים שהם מספרים)
        retrieved_pages = [int(chunk.page_num) for chunk in top_5_chunks]
        
        # 3. בודקים האם לפחות עמוד אחד מהעמודים המצופים והמתוקנים נמצא ברשימה
        is_success = any(page in retrieved_pages for page in adjusted_expected_pages)
        
        if is_success:
            successful_retrievals += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
            
        logger.info(f"[{i}/{len(golden_data)}] {status} | Expected (Adjusted): {adjusted_expected_pages} | Retrieved: {retrieved_pages}")
        
        results_log.append({
            "Question": query,
            "Expected Pages (Original)": expected_pages_original,
            "Expected Pages (Adjusted)": adjusted_expected_pages,
            "Retrieved Pages": retrieved_pages,
            "Success": is_success
        })

    # --- סיכום התוצאות ---
    total_queries = len(golden_data)
    success_rate = (successful_retrievals / total_queries) * 100
    
    logger.info("========================================")
    logger.info(f"🏆 Final Retrieval Score (Recall@5): {success_rate:.2f}%")
    logger.info(f"✅ Successful queries: {successful_retrievals} out of {total_queries}")
    logger.info("========================================")

    # יצירת דוח אקסל (CSV) פשוט וממוקד
    df = pd.DataFrame(results_log)
    report_path = "data/retrieval_evaluation.csv"
    df.to_csv(report_path, index=False, encoding="utf-8-sig")
    logger.info(f"Saved detailed report to {report_path}")

if __name__ == "__main__":
    run_retrieval_evaluation()