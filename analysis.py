import requests
import pandas as pd
import time
import matplotlib.pyplot as plt
import seaborn as sns

# Настройки запроса
url = "https://api.hh.ru/vacancies"
params = {
    "text": '(NAME:"аналитик данных" OR NAME:"аналитика данных" OR NAME:"data analyst")',
    "area": 113,  # Вся Россия
    "per_page": 50,
    "page": 0,
}

vacancies = []
max_pages = 4

# Парсинг вакансий
for page in range(max_pages):
    try:
        params["page"] = page
        print(f"Парсинг страницы {page + 1}...")
        time.sleep(1)
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        print(f"Найдено вакансий: {data['found']}")
        vacancies.extend(data["items"])
        
        if page >= data["pages"] - 1:
            break
            
    except Exception as e:
        print(f"Ошибка: {e}")
        break

print(f"\nСобрано вакансий: {len(vacancies)}")

def detect_level(vacancy):
    try:
        # Защита от полного отсутствия структуры experience
        experience = vacancy.get("experience") or {}
        experience_name = experience.get("name", "").lower()
        
        # Защита от отсутствия ключа salary
        salary = vacancy.get("salary") or {}
        
        # Полностью безопасное получение навыков
        key_skills = vacancy.get("key_skills", []) or []
        skills_list = [str(skill.get("name", "")).lower() for skill in key_skills if isinstance(skill, dict)]
        skills = " ".join(skills_list)
        
        title = str(vacancy.get("name", "")).lower()

        # Ключевые слова
        junior_keywords = {'junior', 'джун', 'младш', 'начинающий', 'стажер'}
        middle_keywords = {'middle', 'миддл', 'средний', 'опыт от 1 года'}
        senior_keywords = {'senior', 'сеньор', 'старш', 'ведущий', 'руководитель'}

        # Приоритет Senior -> Middle -> Junior
        for keyword in senior_keywords:
            if keyword in title or keyword in skills:
                return "Senior"
        
        for keyword in middle_keywords:
            if keyword in title or keyword in skills:
                return "Middle"
        
        for keyword in junior_keywords:
            if keyword in title or keyword in skills:
                return "Junior"
        
        # Анализ опыта с дополнительной защитой
        exp_mapping = {
            'нет опыта': 'Junior',
            'от 1 года до 3 лет': 'Middle',
            'от 3 лет': 'Senior'
        }
        for exp_pattern, level in exp_mapping.items():
            if exp_pattern in experience_name:
                return level
        
        # Анализ зарплаты с полной защитой
        salary_from = salary.get("from")
        if salary_from:
            try:
                salary_from = float(salary_from)
                if salary_from < 80000:
                    return "Junior"
                elif 80000 <= salary_from < 180000:
                    return "Middle"
                else:
                    return "Senior"
            except (TypeError, ValueError):
                pass
        
        return "Other"
    
    except Exception as e:
        print(f"Ошибка определения уровня: {str(e)}")
        print(f"Проблемная вакансия: {vacancy.get('id', 'no-id')}")
        return "Error"
    
# блок создания parsed_data
parsed_data = []
for vacancy in vacancies:
    try:
        # получение данных
        salary = vacancy.get("salary", {}) or {}
        employer = vacancy.get("employer", {}) or {}
        
        # Парсинг навыков с обработкой ошибок
        skills = []
        try:
            vacancy_response = requests.get(f'https://api.hh.ru/vacancies/{vacancy["id"]}', timeout=5)
            skills_data = vacancy_response.json().get("key_skills", []) or []
            skills = [skill.get("name", "") for skill in skills_data]
        except Exception as e:
            pass
        
        parsed_data.append({
            "Название": vacancy.get("name", "Не указано"),
            "Компания": employer.get("name", "Не указана"),
            "Уровень": detect_level(vacancy),
            "Зарплата_от": salary.get("from"),
            "Зарплата_до": salary.get("to"),
            "Валюта": salary.get("currency", "RUR"),
            "Опыт": vacancy.get("experience", {}).get("name", "Не указан"),
            "Ссылка": vacancy.get("alternate_url", ""),
            "Навыки": ", ".join(skills) if skills else "",  # Было "Не указаны"
        })
        
    except Exception as e:
        print(f"Критическая ошибка обработки вакансии: {str(e)}")
        continue

df = pd.DataFrame(parsed_data)

# Конвертация зарплаты
df["Зарплата_от"] = pd.to_numeric(df["Зарплата_от"], errors="coerce")
df["Зарплата_до"] = pd.to_numeric(df["Зарплата_до"], errors="coerce")

# Фильтр по рублям
df_rur = df[df["Валюта"] == "RUR"]
df_rur.to_csv("analyst_vacancies.csv", index=False)

# Удаляем записи с "Error" в уровне
df = df[df["Уровень"] != "Error"]

# Фильтр для навыков
all_skills = df[df["Навыки"] != ""]["Навыки"] \
    .str.split(", ").explode() \
    .value_counts().head(10)

# Визуализация
if not df_rur.empty:
    # Распределение зарплат
    plt.figure(figsize=(12, 6))
    sns.boxplot(
        data=df_rur[df_rur["Уровень"].isin(["Junior", "Middle", "Senior"])], 
        x="Уровень", 
        y="Зарплата_от", 
        palette="viridis",
        order=["Junior", "Middle", "Senior"]
    )
    plt.title("Распределение зарплат по уровням (RUR)")
    plt.show()

    # Топ навыков (без учета пустых значений)
    plt.figure(figsize=(10, 6))
    df[df["Навыки"] != ""]["Навыки"] \
    .str.split(", ") \
    .explode() \
    .value_counts() \
    .head(10) \
    .plot(kind="barh", color="teal")

    plt.title("Топ-10 востребованных навыков")
    plt.gca().invert_yaxis()
    plt.show()

    # Распределение уровней
    levels = df["Уровень"].value_counts()
    plt.figure(figsize=(8, 8))
    plt.pie(levels, labels=levels.index, autopct="%1.1f%%", startangle=90)
    plt.title("Распределение вакансий по уровням")
    plt.show()

    # Требования к опыту
    exp_stats = df["Опыт"].value_counts()
    plt.figure(figsize=(10, 6))
    sns.barplot(y=exp_stats.index, x=exp_stats.values, palette="rocket")
    plt.title("Требования к опыту работы")
    plt.xlabel("Количество вакансий")
    plt.show()
else:
    print("Недостаточно данных для визуализации")