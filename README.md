# מערכת עיבוד דוחות נוכחות (Attendance Report Processing System)

מערכת ארכיטקטונית מתקדמת ב-Python לעיבוד, טרנספורמציה ורנדור של דוחות נוכחות. המערכת בנויה בהתאם לעקרונות **Clean Architecture**, **SOLID**, ותבניות עיצוב מתקדמות (**Design Patterns**), המבטיחים קוד מודולרי, נקי ופתוח להרחבה.

---

## 🏗️ מבנה הארכיטקטורה והשכבות במערכת

הפרויקט מחולק לשכבות עצמאיות המופרדות זו מזו באופן מוחלט:

נקודת הכניסה `main.py` מתאמת בלבד: הממשק נמצא ב-`cli.py`, וצינור עיבוד הדוח
נמצא ב-`pipeline.py`.

1. **מודלי נתונים (`models.py`):**
   - מגדירה את חוזי המערכת המרכזיים (`AttendanceRow`, `ReportSummary` ו-`AttendanceReport`) כמודלים קפואים (`frozen=True`). שורות הדוח והערות הסיכום נשמרות כ-tuples כדי לשמור על אי-שינויות גם של האוספים.
   - שעות כניסה ויציאה ומשך עבודה מיוצגים במודל כמספרי דקות; שעות שעון נשמרות כדקות מאז חצות, והמרה למחרוזת תצוגה מתבצעת רק בשכבת הרינדור.
   - מנגנון הרישום הדינמי (**Registry Pattern**) נמצא ב-`parsing/attendance_parser.py` (`ParserRegistry`) וב-`transformation/transformer.py` (`TRANSFORMATION_STRATEGIES`): הוספת סוג דוח חדש מתבצעת דרך שכבות הפרסור והטרנספורמציה.

2. **שכבת קריאת הקבצים ו-OCR (`ocr/ocr.py`):**
   - אחראית על חילוץ טקסט גולמי מקבצי PDF ועל ניקויו באמצעות פונקציית `clean_text` (טיפול בשגיאות פורמט, שעות שבורות ורווחים מיותרים).
   - חילוץ הטקסט מתבצע פעם אחת ב-pipeline; הפרסר מקבל מחרוזת בלבד ואינו קורא קבצים.

3. **שכבת הפרסור (`parsing/`):**
   - `parsing/classifier.py` מסווג טקסט לפי ניקוד מצטבר של כמה ראיות, ודוחה טקסט עם ראיות חלשות או תיקו באמצעות `UnknownReportTypeError`. `ReportType` מוגדר פעם אחת ב-`models.py`: סוג A הוא סיכום שכר, וסוג B הוא דוח נוכחות מפורט.
   - `parsing/parser.py` מספק את `parse_report(text, report_type, ...)`, ו-`parsing/attendance_parser.py` מרכז את זרימת העבודה המשותפת (`BaseParser`: סינון כותרות, פענוח שורות וסיכומים), ללא גישה לקובץ המקור.

4. **שכבת הטרנספורמציה והלוגיקה העסקית (`transformation/transformer.py`):**
   - מיישמת את תבנית **Strategy Pattern** עם אסטרטגיות עיבוד נפרדות לכל סוג דו"ח (`TypeATransformationStrategy`, `TypeBTransformationStrategy`).
   - מקבלת הגדרות מטיפוס `TransformationRules`, אוכפת כללי תקינות (*Invariants* כמו שעת יציאה מאוחרת מהכניסה), דטרמיניזם באמצעות `seed`, ושמירה קפדנית על `Immutability` באמצעות יצירת מופעים חדשים בלבד.

5. **שכבת היצירה והרנדור (`generation/generator.py`):**
   - מנותקת משלבי ה-OCR והפרסור, ומקבלת את אובייקט ה-`AttendanceReport` לאחר הטרנספורמציה כדי לרנדר HTML או PDF.
   - המסמכים נבנים מחדש מנתוני `AttendanceReport`; הם אינם עותק של קובץ המקור. כך הפלט משקף את הנתונים והטרנספורמציות, והמקור נשאר ללא שינוי. הפלט אינו מתחייב להיות זהה חזותית למקור.
   - `generation/layouts.py` מגדיר פריסת נתונים נפרדת לכל סוג דוח, בהתאמה למבנה דוח השכר ולמבנה הדוח המפורט שבדוגמאות: העמודות וסדרן, שדות הסיכום ומיקומם. הרנדררים משתמשים באותה פריסה, בעוד שכל אחד מהם אחראי בנפרד לכתיבת HTML או PDF.
   - פלט ה-PDF מציג עברית בכיוון נכון (המרה לסדר חזותי RTL בפונקציה `to_visual_rtl`, כולל טקסט שמשלב עברית ומספרים), עם עמודות מסודרות מימין לשמאל.
   - נדרש גופן TTF התומך בעברית (Arial ב-Windows/macOS, DejaVu Sans ב-Linux). אפשר לציין גופן אחר במשתנה הסביבה `ATTENDANCE_FONT`.

---

## 🚀 הוראות התקנה והרצה

### א. הרצה מקומית (Local Environment)

1. **התקנת תלויות מערכת (נדרש עבור OCR ו-PDF):**
   - *ב-Ubuntu/Debian:* `sudo apt-get install tesseract-ocr tesseract-ocr-heb poppler-utils`
   - *ב-macOS (דרך Homebrew):* `brew install tesseract tesseract-lang poppler`

2. **יצירת סביבה וירטואלית והתקנת חבילות Python:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

### ב. הפעלת ממשק המשתמש

מתיקיית הפרויקט, לאחר הפעלת הסביבה הווירטואלית:

```powershell
streamlit run app.py
```

הדפדפן יפתח ממשק להעלאת PDF, הזנת פרטי העובד ובחירת סוג הדוח (`TYPE_A` או `TYPE_B`). בסיום העיבוד אפשר להוריד את ה-PDF שנוצר.

אפשר לבחור גם במצב **„תרגול — נתונים סינתטיים”**. מצב זה משתמש בזהות הדגמה,
מייצר שעות חוזרות לפי seed וטווח שינוי בדקות, ומחשב מחדש שעות עבודה, מדרגות
שעות וסיכומי שבת. התאריך והזמנים לכל שורה נקבעים באופן דטרמיניסטי לפי ה-seed
ותאריך השורה. בדוח סינתטי, שורות שבת וחגים שהוזנו נשארים בתאריך המקורי וללא שעות;
בעיבוד רגיל נשמרות שעות העבודה המקוריות גם בימים אלה.
אפשר להזין תאריכי חג מפורשים, וכן תאריך הפקה להצגה בדוח. ללא תאריך הפקה מפורש,
לא מתווסף תאריך נוכחי. הפלט מסומן בכותרת וב-watermark בכל עמוד כנתונים סינתטיים,
וכולל את תאריך ההפקה (אם הוזן) ואת ה-seed. קובץ המקור אינו משתנה.

### ג. יצירת קובץ PDF או HTML משורת הפקודה

   המערכת מפיקה PDF כאשר נתיב הפלט מסתיים ב-`.pdf`:

   ```powershell
   python main.py `
     --input "input_pdfs\a_r_25.pdf" `
     --employee-id "12345" `
     --employee-name "ישראל ישראלי" `
     --period "2026-10" `
     --report-type TYPE_A `
     --output "output\a_r_25_NEW.pdf"
   ```

   להפעלת סימולציית תרגול מסומנת, יש להוסיף `--synthetic-simulation`.
   ברירת המחדל היא שינוי אקראי של 20–30 דקות לכל כיוון, היסט תאריך נפרד של עד
   30 ימים, גבול מדרגת 100% של 480 דקות (8 שעות) ו-seed של 42:

   ```powershell
   python main.py `
     --input "input_pdfs\a_r_25.pdf" `
     --report-type TYPE_A `
     --synthetic-simulation `
     --min-shift-minutes 20 `
     --max-shift-minutes 30 `
     --overtime-100-limit-minutes 480 `
     --maximum-date-shift-days 30 `
     --holiday-date 2026-10-01 `
     --simulation-date 2026-11-09 `
     --seed 42 `
     --output "output\synthetic_practice.pdf"
     ```

     אפשר לציין כמה חגים באמצעות חזרה על `--holiday-date`. שורות בשבת או בתאריכי חג
     שהוגדרו יופקו ללא זמני כניסה/יציאה, הפסקות או שעות עבודה. תקרת מדרגת 100% והיסט
     התאריך ניתנים לשינוי בנפרד; 30 דקות שינוי אינן 30 ימי היסט. התאריכים חייבים להיות
     בפורמט ISO (`YYYY-MM-DD`). `--simulation-date` אופציונלי ומוצג בפלט אם הוגדר.

ערכי ברירת המחדל העסקיים מרוכזים ב-[config.py](./config.py). `saturday_minutes` הוא
נתון נפרד שאינו מתווסף למדרגות 100%/125%/150%; סכום שלוש המדרגות שווה תמיד לסך
דקות העבודה.

   אפשר להפיק HTML במקום PDF על ידי שימוש בסיומת `.html`.

   קובץ פלט קיים אינו נדרס: יצירה ליעד קיים נכשלת עם `FileExistsError`. יש לבחור נתיב
   חדש או להעביר את הקובץ הקיים ידנית. ה-pipeline גם מוודא שנתיב הפלט אינו זהה
   לנתיב המקור, כדי למנוע דריסת מקור.

   קובצי הקלט שסופקו בפרויקט הם סריקות תמונה. לכן `pypdf` לבדו אינו מספיק:
   נדרש להתקין Tesseract OCR עם שפה עברית ו-Poppler. ב-Windows יש להוסיף
   את `tesseract.exe` ואת תיקיית `pdftoppm.exe` ל-PATH, או להגדיר:

   ```powershell
   $env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
   $env:POPPLER_PATH = "C:\poppler\Library\bin"
   ```

   ב-Docker התלויות הללו מותקנות אוטומטית:

   ```powershell
   docker build -t attendance-project .
   docker run --rm `
     -v "${PWD}\input_pdfs:/app/input_pdfs" `
     -v "${PWD}\output:/app/output" `
     attendance-project `
     python main.py --input input_pdfs/a_r_25.pdf --employee-id 12345 `
     --employee-name "ישראל ישראלי" --period 2026-10 `
     --report-type TYPE_A --output output/a_r_25_NEW.pdf
   ```

### ד. בדיקות

```powershell
python -m pytest -q
```

בדיקות הפרסר והמסווג טוענות טקסט מתוך `tests/fixtures/`. בדיקות היחידה אינן
מריצות חילוץ PDF/OCR ואינן מפעילות את Tesseract, Poppler, `pdf2image` או
`pytesseract`. הקבצים `a_r_25.txt`, `a_r_9.txt`, `n_r_5_n.txt` ו-`n_r_10_n.txt`
הם פלטי OCR שנשמרו מארבעת ה-PDFים המקוריים ונבדקים גם לסיווג וגם להפקת שורות
נוכחות. דוגמאות `type_a_payroll_sample.txt` ו-`type_b_detailed_sample.txt` הן
fixtures סינתטיים משלימים לבדיקת שני סוגי הדוחות. בדיקות ה-OCR מתמקדות בניקוי
טקסט; בדיקת הצינור כולו משתמשת גם ב-PDF טקסטואלי שנוצר בזמן הבדיקה.
