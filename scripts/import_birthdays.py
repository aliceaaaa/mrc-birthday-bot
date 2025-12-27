import asyncio
import aiosqlite
from db import init_db, DB_NAME
from core.utils import normalize_username_or_none, normalize_date_or_none

DATA = [
    ("Степан Панов", "11.01", "@step1p"),
    ("Антон и Ульяна Безбородые", "12.01", ""),
    ("Иван Ларионов", "22.01", "@larionovnl"),
    ("Оля Петрушина", "30.01", "@OlgaPetrushina"),
    ("Павел Глуховченко", "09.02", "@Kopern1kus"),
    ("Анатолий Эврюков", "14.02", ""),
    ("Владимир Облейкин (Кач)", "15.02", ""),
    ("Даша Егорова", "17.02", ""),
    ("Павел Сериков", "19.02", "@spavelsergeevich"),
    ("Никита Ткач", "20.02", ""),
    ("Михаил Сергеевич Левин", "22.02", ""),
    ("Александр Крюков", "02.03", ""),
    ("Кононов Олег", "16.03", ""),
    ("Сашка Павлов", "22.03", ""),
    ("Глеб Свирский", "31.03", ""),
    ("Евгения Богданова", "04.04", ""),
    ("Вадим Олейник", "16.04", "@vadim_oleynik"),
    ("Кирилл Волков", "20.04", ""),
    ("Гульзана Холмирзаева", "16.05", "@gulzana_01"),
    ("Настя Николаева", "19.05", "@uneasyrunner"),
    ("Александр Чубучный", "29.05", ""),
    ("Настя Любицкая", "30.05", "@NastyaNooch"),
    ("Саша Олизаровский", "11.06", ""),
    ("Артур Арсланов", "12.06", "@JustArtur"),
    ("Алена Костина", "19.06", ""),
    ("Юля Кеня", "01.07", "@i_kenia"),
    ("Diana Light", "02.07", "@dreamcatchlight"),
    ("Катя Лоскутова", "05.07", "@loskutovaloskutova"),
    ("Андрей Зайцев", "05.07", ""),
    ("Юлия Цай", "05.07", "@ztgst"),
    ("Римма Акчурина", "16.07", "@Foma_Kinyaev"),
    ("Саша Штепо", "21.07", "@shtepsi"),
    ("Дима Сидельников", "22.07", ""),
    ("Катя Кочеткова", "26.07", "@KaterinaKochetkova"),
    ("Александр Нестеренко", "27.07", ""),
    ("Арсений Николаев", "01.08", "@ars_nikolaev"),
    ("Евгений Кох", "14.08", ""),
    ("Анна-Мария Филиппова", "03.09", ""),
    ("Фируза Сахапова", "07.09", "@FiraSakhapova"),
    ("Илья Немаков", "07.09", "@Reuuke"),
    ("Александра (Саша-Лампа)", "08.09", "@lampabegaet"),
    ("Игорь Желтухин", "19.09", "@Gilliam6"),
    ("Гульназ Сираева", "20.09", "@gulnaz_s"),
    ("Эврюкова Анна", "20.09", "@loceranets"),
    ("Дима Мостовых", "21.09", "@dimamostovykh"),
    ("Мария Пластинина", "30.09", "@mshplst"),
    ("Алексей Степанов", "01.10", ""),
    ("Артем Зенковец", "01.10", ""),
    ("Мария Шахназарова", "05.10", "@marimariai"),
    ("Павел Грибцов", "09.10", "@pavel999555"),
    ("Лида Венгерская", "09.10", "@vengerlys"),
    ("Вита Гурнутина", "11.10", "@prooosto_vitka"),
    ("Владислав Зенин", "13.10", "@migelson_md"),
    ("Елена Рубашенко", "13.10", "@oh_rubash"),
    ("Анна Васильева", "15.10", "@vvrubel"),
    ("Алексей Яковлев", "19.10", ""),
    ("Алексей Кобилев", "29.10", "@alex_kobilev"),
    ("Алиса Андрианова", "31.10", "@alisandrii"),
    ("Даниял Габитов", "30.10", "@ds202410"),
    ("Петр Козлов", "27.11", "@pkozlov92"),
    ("Тимур Хажиев", "05.12", "@khazhix"),
    ("Владимир Краснов", "10.12", "@krasnov_vladimir"),
    ("Артур Абисалов", "15.12", "@arthurhelloo"),
    ("Елена Родина", "29.12", "@yel_ka"),
    ("Саша Фъюри", "30.12", "@sashafureyous"),
    ("Сергей Бородин", "26.01", "@sergeiborodin89"),
    ("Егор Рудинский", "08.02", "@superegorwin"),
    ("Глеб Дмитриев", "13.05", "@woodrunsdeep"),
    ("Андрей Морозов", "23.12", "@alt_j"),
    ("Саша Яшина", "30.01", "@dancingonmyown"),
    ("Олег Ларин", "02.10", "@olegroan"),
    ("Таня", "08.03", "@tanya_designer803"),
    ("Миша", "19.11", "@mishachris"),
]

async def run_import_birthdays() -> tuple[int, int]:
    await init_db()
    
    inserted = 0
    updated = 0
    
    async with aiosqlite.connect(DB_NAME) as db:
        for name, date_str, tg_username in DATA:
            u = normalize_username_or_none(tg_username)
            d = normalize_date_or_none(date_str)
            
            await db.execute("INSERT OR IGNORE INTO users (username, tg_username) VALUES (?, ?)", (name, u))
            
            cursor = await db.execute("SELECT id FROM users WHERE username = ?", (name,))
            row = await cursor.fetchone()
            
            if not row or d is None:
                continue
            
            user_id = row[0]
            cursor = await db.execute("SELECT date FROM birthdays WHERE user_id = ?", (user_id,))
            exists = await cursor.fetchone()
            
            if exists:
                await db.execute("UPDATE birthdays SET date = ? WHERE user_id = ?", (d, user_id))
                updated += 1
            else:
                await db.execute("INSERT INTO birthdays (user_id, date) VALUES (?, ?)", (user_id, d))
                inserted += 1
        
        await db.commit()
        
    return inserted, updated

if __name__ == "__main__":
    asyncio.run(run_import_birthdays())
