import httplib2
import apiclient
#import apiclient.discovery
import pandas as pd
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from database_service.models.test_service import Test, Question, Answer

from oauth2client.service_account import ServiceAccountCredentials

from dependency_injector.wiring import Provide, inject

from .container import TableContainer

from .config import TableConfig


@inject
async def get_tests_from_table(credentials: ServiceAccountCredentials = Provide[TableContainer.credentials],
                               config: TableConfig = Provide(TableContainer.config)) -> list:
    httpAuth = credentials.authorize(httplib2.Http())  # Авторизуемся в системе
    service = apiclient.discovery.build('sheets', 'v4', http=httpAuth)  # Выбираем работу с таблицами и 4 версию API
    ranges = ["tests"]  #

    results = service.spreadsheets().values().batchGet(spreadsheetId=config.sheet_id.value,
                                                       ranges=ranges,
                                                       valueRenderOption='FORMATTED_VALUE',
                                                       dateTimeRenderOption='FORMATTED_STRING').execute()
    sheet_values = results['valueRanges'][0]['values']
    tests = []
    test = []
    for i in sheet_values:
        if not i:
            continue
        elif i[0] == 'Промпт для отправки':
            test.append(i)
            tests.append(test)
            test = []
        else:
            test.append(i)
    return tests


@inject
async def update_test_database(session: AsyncSession = Provide[TableContainer.postgres.session],) -> None:
    tests = await get_tests_from_table()
    for test in tests:
        test_json = await test_to_json(test)
        await upsert_test(test_info=test_json, session=session)


async def test_to_json(test) -> None:
    # Преобразуем в DataFrame для удобства
    df = pd.DataFrame(test)

    # Извлекаем общую информацию о тесте
    test_info = {
        'id': df.iloc[0, 1],
        'folder': df.iloc[1, 1],
        'title': df.iloc[2, 1],
        'description': df.iloc[3, 1],
        'welcome_image': df.iloc[4, 1],
        'questions_count': int(df.iloc[5, 1]),
        'available_in_kira': True if df.iloc[6, 1] == 'Да' else False,
        'test_available': True if df.iloc[7, 1] == 'Да' else False,
        'message_after_test': df.iloc[8, 1],
        'prompt': df.iloc[-1, 1]
    }

    # Начинаем парсинг вопросов
    questions = []
    current_question = {}
    for i in range(10, len(df) - 1):
        row = df.iloc[i]
        if pd.isna(row[0]) and pd.isna(row[1]):
            continue  # Пропускаем пустые строки
        elif row[0].startswith("Вопрос") and row[0] != 'Вопрос':  # Новый вопрос
            if current_question:
                questions.append(current_question)  # Добавляем предыдущий вопрос
            current_question = {
                'question': None,
                'image': None,
                'question_type': None,
                'answers': []
            }
        elif row[0] == 'Картинка':
            current_question['image'] = row[1]
        elif row[0] == 'Вопрос':
            current_question['question'] = row[1]
        elif row[0] == 'Тип вопроса':
            current_question['question_type'] = row[1]
        elif row[0] == 'Варианты ответов' or pd.notna(row[1]):
            current_question['answers'].append(row[1])

    # Добавляем последний вопрос
    if current_question:
        questions.append(current_question)

    # Формируем итоговый JSON
    test_info['questions'] = questions

    # Преобразуем в JSON-строку
    result_json = json.dumps(test_info, ensure_ascii=False, indent=4)
    return test_info


async def upsert_test(test_info: dict, session: AsyncSession) -> None:
    # Проверяем, существует ли тест в базе по `test_id`
    existing_test = await session.execute(
        select(Test).options(selectinload(Test.questions)).where(Test.test_id == test_info['id'])
    )
    existing_test = existing_test.scalar_one_or_none()

    if existing_test:
        # Обновляем существующий тест
        existing_test.folder = test_info.get('folder')
        existing_test.title = test_info['title']
        existing_test.description = test_info.get('description')
        existing_test.welcome_image = test_info.get('welcome_image')
        existing_test.questions_count = test_info['questions_count']
        existing_test.available_in_kira = test_info.get('available_in_kira', False)
        existing_test.test_available = test_info.get('test_available', True)
        existing_test.message_after_test = test_info.get('message_after_test')
        existing_test.prompt = test_info.get('prompt')
    else:
        # Создаем новый тест
        existing_test = Test(
            test_id=test_info['id'],
            folder=test_info.get('folder'),
            title=test_info['title'],
            description=test_info.get('description'),
            welcome_image=test_info.get('welcome_image'),
            questions_count=test_info['questions_count'],
            available_in_kira=test_info.get('available_in_kira', False),
            test_available=test_info.get('test_available', True),
            message_after_test=test_info.get('message_after_test'),
            prompt=test_info.get('prompt'),
        )
        session.add(existing_test)

    for idx, question_data in enumerate(test_info['questions'], start=1):
        # Пытаемся найти существующий вопрос
        existing_question = await session.execute(
            select(Question).where(
                Question.test_id == test_info['id'],
                Question.position == idx
            )
        )
        existing_question = existing_question.scalar_one_or_none()

        if existing_question:
            print('обновляем существующий вопрос')
            # Обновляем существующий вопрос
            existing_question.question = question_data['question']
            existing_question.image = question_data.get('image')
            existing_question.question_type = question_data.get('question_type')
        else:
            print('добаляем новый вопрос')
            # Добавляем новый вопрос
            existing_question = Question(
                test_id=test_info['id'],
                question=question_data['question'],
                image=question_data.get('image'),
                question_type=question_data.get('question_type'),
                position=idx,
            )
            session.add(existing_question)

        # Обрабатываем ответы для текущего вопроса
        for ans_idx, answer_text in enumerate(question_data['answers'], start=1):
            existing_answer = await session.execute(
                select(Answer).where(
                    Answer.question_id == existing_question.id,
                    Answer.position == ans_idx
                )
            )
            existing_answer = existing_answer.scalar_one_or_none()

            if existing_answer:
                print('обновляем существующий ответ')
                # Обновляем существующий ответ
                existing_answer.answer_text = answer_text
            else:
                print('добавляем новый ответ')
                # Добавляем новый ответ
                answer = Answer(
                    question=existing_question,
                    answer_text=answer_text,
                    position=ans_idx,
                )
                session.add(answer)

    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        print(f"Ошибка вставки или обновления: {e}")
