import streamlit as st
import whisper
import spacy
import os
import tempfile
from spacy import displacy
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from passlib.hash import bcrypt

# Инициализация состояния сессии
if 'user' not in st.session_state:
    st.session_state.user = None
if 'audio_data' not in st.session_state:
    st.session_state.audio_data = None
if 'transcription' not in st.session_state:
    st.session_state.transcription = None

# ---- Настройка БД ----
Base = declarative_base()
engine = create_engine('sqlite:///users.db')
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True)
    hashed_password = Column(String(100))
    is_admin = Column(Boolean, default=False)

# Создаем таблицы при первом запуске
Base.metadata.create_all(engine)

# ---- Функции аутентификации ----
def create_user(username, password, is_admin=False):
    with Session() as session:
        if session.query(User).filter_by(username=username).first():
            return False
        hashed = bcrypt.hash(password)
        user = User(username=username, hashed_password=hashed, is_admin=is_admin)
        session.add(user)
        session.commit()
        return True

def verify_user(username, password):
    with Session() as session:
        user = session.query(User).filter_by(username=username).first()
        if user and bcrypt.verify(password, user.hashed_password):
            return user
        return None

# ---- Настройка моделей анализа ----
@st.cache_resource
def load_models():
    whisper_model = whisper.load_model("medium")
    try:
        nlp = spacy.load("ru_core_news_sm")
    except OSError:
        raise Exception("Модель ru_core_news_sm не установлена. Выполните: python -m spacy download ru_core_news_sm")
    return whisper_model, nlp

# ---- Функции анализа текста ----
def analyze_text(text, nlp):
    doc = nlp(text)
    return {
        "promo_mentioned": any(token.text.lower() in ["акция", "скидка", "промо"] for token in doc),
        "was_polite": any(token.text.lower() in ["спасибо", "пожалуйста"] for token in doc),
        "entities": [(ent.text, ent.label_) for ent in doc.ents]
    }

# ---- Основной интерфейс ----
def main_app():
    st.title("🕵️ Анализ проверок тайного покупателя")

    # ---- Панель аутентификации ----
    if not st.session_state.user:
        auth_type = st.radio("Выберите действие:", ["Вход", "Регистрация"])
        username = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")

        if auth_type == "Регистрация":
            if st.button("Зарегистрироваться"):
                if create_user(username, password):
                    st.success("Регистрация успешна! Теперь войдите")
                else:
                    st.error("Пользователь уже существует")

        if auth_type == "Вход":
            if st.button("Войти"):
                user = verify_user(username, password)
                if user:
                    st.session_state.user = {
                        "username": user.username,
                        "is_admin": user.is_admin
                    }
                    st.rerun()
                else:
                    st.error("Неверные данные")

    # ---- Выход ----
    if st.sidebar.button("Выйти"):
        st.session_state.clear()  # Очищаем все состояние
        st.rerun()

    # ---- Основной функционал ----
    if st.session_state.user:
        st.sidebar.subheader(f"Вы вошли как: {st.session_state.user['username']}")

        if st.session_state.user.get('is_admin'):
            admin_interface()
        else:
            user_interface()

# ---- Интерфейс администратора ----
def admin_interface():
    st.subheader("Панель администратора")

    # Создание пользователей
    with st.expander("Создать администратора"):
        new_user = st.text_input("Логин")
        new_pass = st.text_input("Пароль", type="password")
        if st.button("Создать админа"):
            if create_user(new_user, new_pass, is_admin=True):
                st.success("Админ создан")
            else:
                st.error("Ошибка создания")

    audio_file = st.file_uploader("Загрузите аудиофайл", type=["mp3", "wav"])

    if audio_file:
        process_audio(audio_file)

        if st.session_state.transcription:
            st.subheader("Транскрипция:")
            edited_text = st.text_area("Редактирование",
                                       st.session_state.transcription,
                                       height=200,
                                       key="edited_text")

            if st.button("Анализировать"):
                analysis = analyze_text(edited_text, load_models()[1])

                st.subheader("Результаты анализа:")
                st.write(f"Упомянуты акции: {'✅' if analysis['promo_mentioned'] else '❌'}")
                st.write(f"Вежливый тон: {'✅' if analysis['was_polite'] else '❌'}")

                if analysis['entities']:
                    st.write("Обнаруженные сущности:")
                    for entity, label in analysis['entities']:
                        st.write(f"- {entity} ({label})")

# ---- Интерфейс пользователя ----
def user_interface():
    st.subheader("Рабочая панель")
    audio_file = st.file_uploader("Загрузите аудиофайл", type=["mp3", "wav"])

    if audio_file:
        process_audio(audio_file)

        if st.session_state.transcription:
            st.subheader("Транскрипция:")
            edited_text = st.text_area("Редактирование",
                                       st.session_state.transcription,
                                       height=200,
                                       key="edited_text")

            if st.button("Анализировать"):
                analysis = analyze_text(edited_text, load_models()[1])

                st.subheader("Результаты анализа:")
                st.write(f"Упомянуты акции: {'✅' if analysis['promo_mentioned'] else '❌'}")
                st.write(f"Вежливый тон: {'✅' if analysis['was_polite'] else '❌'}")

                if analysis['entities']:
                    st.write("Обнаруженные сущности:")
                    for entity, label in analysis['entities']:
                        st.write(f"- {entity} ({label})")

# ---- Обработка аудио ----
def process_audio(audio_file):
    # Если аудио уже обработано, не делаем транскрипцию снова
    if st.session_state.audio_data == audio_file.getvalue():
        return

    st.session_state.audio_data = audio_file.getvalue()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(audio_file.read())
        audio_path = tmp.name

    whisper_model, nlp = load_models()

    with st.spinner("Обработка аудио..."):
        st.session_state.transcription = whisper_model.transcribe(audio_path)["text"]

    os.unlink(audio_path)

if __name__ == "__main__":
    main_app()
