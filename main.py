import requests
import re
from bs4 import BeautifulSoup

# Константы
ANKI_CONNECT_URL = "http://localhost:8765"

# Получение страницы
def get_page(word: str, url: str = "https://dictionary.cambridge.org/dictionary/english-russian/"):
    # Нормализация слова
    word = word.lower()
    word = word.replace(" ", "-").replace("/", "-")
    url = f"{url}{word}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("Ошибка загрузки:", response.status_code)
        return None

    page = BeautifulSoup(response.text, "html.parser")
    # Проверка для фразовых глаголов
    raw_phrasal_verb_page_title = page.select_one("h2.headword.tw-bw.dhw.dpos-h_hw ")
    # Проверка на то одинаково ли введеное слово и слово на странице
    raw_page_word = page.select_one("span.hw.dhw") if raw_phrasal_verb_page_title is None else None
    # Проверка на то нашлось ли слово
    raw_undefined_word_page_title = page.select_one("h1.lpb-10.lbb")
    # Проверка на то попалили мы на страницу англо-русского словаря
    raw_dictionary_page_title = page.select_one("h1.lmb-20")

    if raw_undefined_word_page_title is not None:
        print("Такого слова нет")
        return None
    elif raw_page_word is not None or raw_phrasal_verb_page_title is not None:
        page_title = raw_page_word.get_text(strip=True, separator=" ") if raw_page_word is not None else raw_phrasal_verb_page_title.get_text(strip=True, separator=" ")
        normalized_page_title = page_title.lower()
        normalized_page_title = normalized_page_title.replace(" ", "-").replace("/", "-")
        if word != normalized_page_title:
            print(f"Введенное слово и слово на странице не совпадают\nПроверьте слово на странице: {url}")
    elif raw_dictionary_page_title is not None:
        print("Слова нет в русском словаре")
        return get_page(word, "https://dictionary.cambridge.org/dictionary/english/")

    return page, page_title

# Добавление карточек в колоду
def add_note_to_anki(page_title: str, page: str, deck="English", model="Простая"):
    # Удаление лишних слов на страницах не производных от нужного слова
    # spare_words = page.select("div.pr.runon.drunon")
    # if spare_words is not None:
    #     for spare_word in spare_words:
    #         spare_word.decompose()
    # Выборка главных ячеек
    entries = page.select("div.entry")
    for entry in entries:
        # Выборка подблоков в ячейках
        subentries = entry.select("div.pr.entry-body__el")
        if not subentries:
            subentries = entry.select("div.pv-block")
        for subentry in subentries:
            # Стили
            back = (r"""
                        <style>
                            .blue-sense::before {
                                content: "►";
                                color: #0580e8;
                                margin-right: 5px;
                            }
                            .main {
                                border-top: 2px solid #5d2fc1;
                                text-align: left;
                                font-size: 14px;
                                padding: 8px;
                            }
                            p, span {
                                padding: 0px;
                                margin: 0px 0px 8px;
                            }
                            .runon-part-of-speech {
                                font-size: 14px;
                            }
                            .sense {
                                font-weight: 700;
                                color: #5d2fc1;
                            }
                            .definition {
                                font-size: 16px;
                                font-weight: 700;
                            }
                            .runon-block {
                                margin-bottom: 10px;
                            }
                            .runon-part-of-speech {
                                font-style: italic;
                                font-weight:700;
                            }
                            .runon-word {
                                font-size: 20px;
                                font-weight: 700;
                            }
                            .translation {
                                color: #0580e8;
                                font-size: 16px;
                            }
                            .examples {
                                padding-left: 12px;
                            }
                            .example {
                                font-style: italic
                            }
                            .blue-sense {
                                font-size: 16px;
                                color: #000;
                            }
                            .blue-main {
                                background-color: #defaff;
                                margin-bottom: 24px;
                            }
                            .no-sense {
                                border-top: none;
                            }
                        </style>
                        """)
            # Часть речи
            #part_of_speech = subentry.select_one("span.pos.dpos").get_text(strip=True, separator=" ")
            part_of_speech = ", ".join(span.get_text(strip=True) for span in subentry.select("span.pos.dpos")) or ""
            #print(f"Часть речи: {part_of_speech}")
            # Разные значения слова
            meanings = subentry.select("div.pr.dsense, div.pr.runon")
            for meaning in meanings:
                # Проверяем есть ли у значения смысл (фиолетовая надпись или надпись, перед которой стоит стрелка в синих блоках)
                raw_sense = meaning.select_one("h3.dsense_h")
                raw_examples = meaning.select("div.examp.dexamp")
                raw_translation = meaning.select_one("span.trans.dtrans.dtrans-se ")
                raw_definition = meaning.select_one("div.def.ddef_d.db")

                # Блок без смысла может быть фразовым глаголом, а может и не быть, может есть какие-то другие типы синих блоков надо проверить
                # Проверка на то является ли блок фразовым глаголом
                if meaning.select_one("div.pr.phrase-block.dphrase-block") is not None:
                    raw_sense = meaning.select_one("span.phrase-title.dphrase-title")
                    is_blue_background = True
                    not_sense = True
                else:
                    is_blue_background = False
                    not_sense = True if raw_sense is None else False

                if "runon" in meaning.get("class", []):
                    is_blue_background = True
                    not_sense = True
                    runon_word = meaning.select_one("span.w.dw").get_text(strip=True, separator=" ")
                    runon_part_of_speech = meaning.select_one("span.pos.dpos").get_text(strip=True, separator=" ")
                else:
                    runon_word = None
                    runon_part_of_speech = None

                sense = re.sub(
                            r"\(\s*(.*?)\s*\)", r"(\1)",
                            raw_sense.get_text(strip=True, separator=" ")
                        ) if raw_sense is not None else None
                definition = re.sub(
                        r'\(\s*(.*?)\s*\)|\s+([.,!?;:])',
                                lambda m: f"({m.group(1)})" if m.group(1) else m.group(2),
                                raw_definition.get_text(strip=True, separator=" ")
                            ) if raw_definition is not None else None
                translation = raw_translation.get_text(strip=True, separator=" ") if raw_translation is not None else None
                examples = [re.sub(
                        r'\(\s*(.*?)\s*\)|\[\s*(.*?)\s*\]|\s+([.,!?;:])',
                                lambda m: f"({m.group(1)})" if m.group(1) else (f"[{m.group(2)}]" if m.group(2) else m.group(3)),
                                example.get_text(strip=True, separator=" ")
                            ) for example in raw_examples] if raw_examples is not None else None
                # print(
                #     f"\n\n"
                #     f"{f'Смысл: {sense}\n' if sense else ''}"
                #     f"Определение: {definition}\n"
                #     f"Перевод: {translation}\n"
                #     f"Примеры: {examples}"
                # )

                # Формирование передней и задней стороны карточки
                front = page_title + f' <i style="font-size: 14px;">{part_of_speech}</i>'
                back += f"""
                        <div class="main {f'blue-main' if is_blue_background else ''} {f'no-sense' if not_sense else ''}">
                            {f'<div class="runon-block"><span class="runon-word">{runon_word}</span> <span class="runon-part-of-speech">{runon_part_of_speech}</span></div>' if runon_word is not None else ''}
                            {f'<p class="sense {f'blue-sense' if is_blue_background else ''}">{sense}</p>' if sense is not None else ''}
                            {f'<p class="definition">{definition}</p>' if definition is not None else ''}
                            {f'<p class="translation">{translation}</p>' if translation is not None else ''}
                            {f'<ul class="examples">{''.join(f"<li class='example'>{example}</li>" for example in examples)}</ul>' if examples is not None else ''}
                        </div>
                        """

            # back = str(subentry) может быть стоит просто парсить всю страницу и убирать с нее ненужное а не выбирать только нужные данные и составлять из них код
            # Создание карточки
            note = {
                "deckName": deck,
                "modelName": model,
                "fields": {
                    "Front": front,
                    "Back": back,
                },
                "options": {
                    "allowDuplicate": False
                },
            }
            # Данные для API
            payload = {
                "action": "addNote",
                "version": 6,
                "params": {
                    "note": note
                }
            }
            # Отправка реквеста на порт
            requests.post(ANKI_CONNECT_URL, json=payload).json()

        return f"Слово {page_title} успешно добавлено!"

if __name__ == "__main__":
    while True:
        word = input("\nВведите слово: ").strip()
        page, page_title = get_page(word)
        if page is not None:
            result = add_note_to_anki(page_title, page)
            print("Результат добавления:", result)
        else:
            print("Попробуйте еще раз")