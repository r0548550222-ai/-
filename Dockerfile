# שימוש בתמונת בסיס רזה ויציבה של פייתון
FROM python:3.11-slim

# הגדרת משתני סביבה למניעת באפרing וייעול ריצת פייתון
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# התקנת תלויות מערכת נדרשות ל-OCR (Tesseract בעברית) ולעיבוד PDF (Poppler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-heb \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# הגדרת תיקיית העבודה בתוך הקונטיינר
WORKDIR /app

# העתקת קובץ התלויות והתקנת ספריות הפייתון
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# העתקת קוד המקור של המערכת לתוך הקונטיינר
COPY . .

# הגדרת פקודת ברירת המחדל להרצת המערכת (או פקודת בדיקה)
CMD ["python", "main.py"]
