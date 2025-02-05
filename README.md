# Secret Shopper Analysis App

## Установка

1. Клонировать репозиторий:
```bash
git clone https://github.com/ваш_username/название_репозитория.git
cd название_репозитория
```

2. Установить зависимости:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или 
venv\Scripts\activate    # Windows

pip install -r requirements.txt
python -m spacy download ru_core_news_sm
```

3. Запустить приложение:
```bash
streamlit run app.py
```