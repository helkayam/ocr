import React from "react";
import "./index.css";

function App() {
  return (
    <div className="app-container app-rtl">
      <h1 className="app-title">Protocol Genesis – מסך פתיחה</h1>

      <p>
        זהו המסך הראשוני של מערכת <strong>Protocol Genesis</strong>.
        בשלב זה המערכת נמצאת בשלב התשתיות (Stage 1), ומוכנה להמשך פיתוח
        של Workspaces והעלאת קבצים.
      </p>

      <div className="app-section">
        <h2>מה כבר קיים בשלב 1?</h2>
        <ul>
          <li>תשתיות Docker (FastAPI, PostgreSQL, MinIO)</li>
          <li>שרת FastAPI בסיסי עם נקודת בדיקה <code>/health</code></li>
          <li>אפליקציית React + TypeScript שרצה ב־<code>localhost:3000</code></li>
          <li>MinIO לאחסון קבצים עם ממשק ניהול ב־<code>localhost:9001</code></li>
        </ul>
      </div>

      <div className="app-section">
        <h2>מה מתוכנן לשלב הבא (Sprint 2)?</h2>
        <ul>
          <li>ניהול Workspaces (יצירה, רשימה, פתיחה)</li>
          <li>ממשק העלאת קבצי PDF באמצעות Signed URL</li>
          <li>שמירת מטא־דאטה של קבצים ב־PostgreSQL</li>
          <li>שיפור ה־UI לפי סקיצות Lovable</li>
        </ul>
      </div>
    </div>
  );
}

export default App;
