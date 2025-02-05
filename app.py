import streamlit as st
import whisper
import spacy
import os
import tempfile
from spacy import displacy

# ---- Настройка моделей ----
@st.cache_resource
def load_models():
    whisper_model = whisper.load_model("medium")
    nlp = spacy.load("ru_core_news_sm")
    return whisper_model, nlp

# ---- Функции анализа ----
def analyze_text(text, nlp):
    doc = nlp(text)
    results = {
        "promo_mentioned": False,
        "was_polite": False,
        "conflict_detected": False,
        "expired_products": False,
        "entities": [],
        "sentiment": "neutral"
    }

    promo_keywords = ["акции", "акция", "скидка", "промо", "специальное предложение"]
    polite_phrases = ["спасибо", "пожалуйста", "добрый день", "будем рады помочь"]
    conflict_words = ["оскорбление", "хамство", "претензия", "жалоба"]
    
    # Используем актуальный текст из session_state
    results["promo_mentioned"] = any(token.text.lower() in promo_keywords for token in doc)
    results["was_polite"] = any(token.text.lower() in polite_phrases for token in doc)
    results["conflict_detected"] = any(token.text.lower() in conflict_words for token in doc)
    results["expired_products"] = any("срок годности" in sent.text for sent in doc.sents)
    results["entities"] = [(ent.text, ent.label_) for ent in doc.ents]
    
    if any(word in text.lower() for word in ["прекрасно", "отлично", "доволен"]):
        results["sentiment"] = "positive"
    elif any(word in text.lower() for word in ["ужасно", "разочарован", "плохо"]):
        results["sentiment"] = "negative"
    
    return results

def main():
    st.title("🕵️ Анализ проверок тайного покупателя")
    
    # Инициализация состояния
    if "raw_text" not in st.session_state:
        st.session_state.raw_text = ""
    if "edited_text" not in st.session_state:
        st.session_state.edited_text = ""

    # Загрузка аудио
    audio_file = st.file_uploader("Выберите аудиофайл", type=["mp3", "wav"])

    if audio_file and not st.session_state.raw_text:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(audio_file.read())
            audio_path = tmp.name

        whisper_model, _ = load_models()
        with st.spinner("Транскрибируем аудио..."):
            st.session_state.raw_text = whisper.transcribe(whisper_model, audio_path)["text"]
            st.session_state.edited_text = st.session_state.raw_text  # Инициализируем edited_text
        
        os.unlink(audio_path)

    if st.session_state.raw_text:
        # Редактирование текста с привязкой к session_state
        st.subheader("✏️ Редактирование транскрипции")
        st.session_state.edited_text = st.text_area(
            "Внесите правки:", 
            value=st.session_state.edited_text,
            height=250,
            key="text_editor"  # Уникальный ключ для отслеживания изменений
        )

        # Кнопка анализа с использованием актуального текста
        if st.button("Анализировать текст"):
            _, nlp = load_models()
            analysis = analyze_text(st.session_state.edited_text, nlp)  # Используем ОТРЕДАКТИРОВАННЫЙ текст
            
            # Отображение результатов
            st.subheader("📊 Результаты анализа")
            
            # Метрики
            cols = st.columns(4)
            with cols[0]:
                st.metric("Упомянуты акции", "✅" if analysis["promo_mentioned"] else "❌")
            with cols[1]:
                st.metric("Вежливость", "✅" if analysis["was_polite"] else "❌")
            with cols[2]:
                st.metric("Конфликты", "⚠️" if analysis["conflict_detected"] else "✅")
            with cols[3]:
                st.metric("Тональность", analysis["sentiment"].capitalize())

            # Сущности
            st.subheader("🔍 Обнаруженные сущности")
            if analysis["entities"]:
                for entity, label in analysis["entities"]:
                    st.markdown(f"- `{entity}` ({label})")
            else:
                st.info("Сущности не обнаружены")

            # Детальный отчет
            st.subheader("📄 Проблемные места")
            if analysis["expired_products"]:
                st.error("**Обнаружено:** Упоминание просроченных товаров")
            if analysis["conflict_detected"]:
                st.error("**Обнаружено:** Признаки конфликта")

            # Визуализация
            with st.expander("Синтаксический анализ"):
                doc = nlp(st.session_state.edited_text)
                html = displacy.render(doc, style="dep", page=True)
                st.components.v1.html(html, width=800, height=400, scrolling=True)

if __name__ == "__main__":
    main()