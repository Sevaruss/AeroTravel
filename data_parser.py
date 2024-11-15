import logging
from datetime import datetime
import xml.etree.ElementTree as xml
import json

from proxy import Proxy
from config import Configuration
from connect_db import ConnectDB

class DataParser():
    """Базовый класс всех парсеров.
    """
    #region константы класса
    FAKE_PERSON = {
        'ru_surname': 'Дубощит',
        'ru_name': 'Торин',
        'ru_middleName':'Траинович',
        'en_surname': 'Oakenshield',
        'en_name': 'Thorin',
        'login': 'Thorin',
        'ru_cardNumber': '1234567890',
        'ru_issueDate': '31.12.2010',
        'country': 'RU',
        'ru_placeOfBirth': 'Эребор',
        'en_cardNumber': '9876543210',
        'en_issueDate': '01.01.2010',
        'en_expireDate': '31.12.2050',
        'birthday': '01.01.2001',
        'gender': 'Male',
        'email': 'thorin@somemail.ru',
        'other_email': 'gendalf@somemail.ru',
        'tabNum': '00001234'
    }
    #endregion константы класса
    
    def __init__(self, config: Configuration) -> None:
        self.logger = logging.getLogger(__name__)
        self.config = config
        
    def _camouflage(self, key, realvalue) -> str: 
        return self.FAKE_PERSON[key] if self.config.is_debug_limit_off else realvalue
    
    def _convdate(self, datestr) -> str:
        return datetime.strptime(datestr, '%d.%m.%Y').strftime('%Y-%m-%d') if datestr else ''

class TravelParser(DataParser):
    """Класс-холдер для работы с ТревелКлик.
    """
    def __init__(self, config: Configuration) -> None:
        super().__init__(config)
        self.FAKE_PERSON['gender'] = 'MALE'

    def _create_employees_travel(self, list_users) -> list:
        """Подготовка списка сотрудников на передачу в агентство, с предварительной проверкой заполнения.

        Args:
            list_users (list): список сотрудников, полученный из БД.

        Returns:
            list: подготовленный для JSON-передачи список сотрудников
        """
        users_list_for_json = list()
        user_except = list()

        new_user = self.config.settings.CbtcTravelClick.newUser
        password = new_user.decrypted_password
        holding_user_role = new_user.holdingUserRole
        holding_user_policy = new_user.holdingUserPolicy
        other_user_policy = new_user.otherUserPolicy

        for user in list_users:
            try:
                #region Проверка заполнения критичных полей 
                if not user[7]:
                    raise Exception("Не заполнен день рождения.")
                if not user[8]:
                    raise Exception("Не заполнена страна.")
                if not user[9]:
                    raise Exception("Не заполнен пол.")
                if user[8] == 'RU':
                    if user[10] is None or user[11] is None:
                        raise Exception("Не заполнен российский паспорт.")
                else:
                    if user[14] is None or user[15] is None:
                        raise Exception("Не заполнен иностранный паспорт.")
                if user[17] is None or user[18] is None or user[19] is None:
                    raise Exception("Не заполнена орг.структура.")
                if user[22] is None or user[23] is None:
                    raise Exception("Не заполнены роли.")
                #endregion Проверка заполнения критичных полей
                
                #region Информация о ФИО
                names = [
                    # Информация о ФИО RU
                    {
                        'lang': 'RU',
                        'surname': self._camouflage('ru_surname', user[4]),
                        'name': self._camouflage('ru_name', user[5]),
                        'middleName': self._camouflage('ru_middleName', user[6])
                    },
                    # Информация о ФИО EN 
                    {
                        'lang': 'EN',
                        'surname': self._camouflage('en_surname', user[2]),
                        'name': self._camouflage('en_name', user[3])
                    } 
                ]
                #endregion Информации о ФИО

                #region Объект аутентификации
                detailPolicies = []
                # if user[22] == holding_user_role:
                #     #select_lm_users = f"exec [dbo].[GetEmpl1Level] {user[1]}"
                #     list_detailPolicy = []  # create_connection_fetch(select_lm_users)
                #     for tab_no in list_detailPolicy:
                #         detailPolicy = {"type": "USER", "value": tab_no[0]}
                #         detailPolicies.append(detailPolicy)

                auth = None
                if user[16] is not None:
                    auth = {
                        'login': self._camouflage('login', user[16]),
                        'policy': holding_user_policy if user[22]==holding_user_role else other_user_policy,
                        'password': password,
                        'roles': [user[22]], # роли сотрудника
                        'activeUser': "TRUE",
                        'detailPolicies': detailPolicies 
                    }
                #endregion Объект аутентификации выше

                #region Документы сотрудника
                _country = self._camouflage('country', user[8])
                documents = []
                if user[10]: # на случай, если это инстранный (user[8]!='RU'), у него может не быть российского паспорта.
                    documents = [{
                            'identityCardType': 'RUSSIAN_PASSPORT',
                            'cardNumber': self._camouflage('ru_cardNumber', user[10]),
                            'issueDate': self._camouflage('ru_issueDate', user[11]), 
                            'country': _country,
                            'placeOfBirth': self._camouflage('ru_placeOfBirth', user[12])
                        }]
                if user[13]: # Для иностранного (user[8]!='RU') или если есть инстранный паспорт
                    documents += [{
                            'identityCardType': 'FOREIGN_PASSPORT',
                            'cardNumber': self._camouflage('en_cardNumber', user[13]),
                            'issueDate': self._camouflage('en_issueDate', user[14]),
                            'expireDate': self._camouflage('en_expireDate', user[15]),
                            'country': _country
                        }]
                #endregion Документы сотрудника

                #region Объект служебной информации
                service = {
                    'unitName': user[18],
                    'costName': str(user[19]),
                    'position': user[17],
                    'authorizators': [{'tabNum': self._camouflage('tabNum', user[20])}] if user[20] else [],
                    'travelPolicy': user[23]
                    }
                #endregion Объект служебной информации выше

                employee = {
                    'tabNum': self._camouflage('tabNum', f'{user[1]:0>8}'),
                    'birthday': self._camouflage('birthday', self._convdate(user[7])),
                    'citizenshipCode': _country,
                    'gender': self._camouflage('gender', user[9]),
                    'names': names,
                    'documents': documents,
                    'service': service,
                    'documents': documents
                }
                if auth:
                    employee['auth'] = auth
                users_list_for_json.append(employee)
            except Exception as e:
                user_except.append(f'{user[1]:0>8} - {str(e)}')

        if len(user_except) > 1:
            body_exception = '\r\n'.join((user_except))
            self.logger.error(f'Ошибки при формировании employees_travel:\r\n {body_exception}')

        return users_list_for_json

    def _travel_answer_analize(self, response_content) -> None:
        """Анализ ответа от агентства.

        Args:
            response_content (Any): Значение content вернувшегося в Response от запроса

        """
        #region вспомогательные функции
        TYPES_FOR_ERROR = {'ERROR'} # ALL_TYPES={'ERROR', 'WARNING', 'INFO', 'SUCCESS'}

        def only_error_items(items) -> bool:
            """Фильтрация списка ответных сообщений по типу сообщений.

            Args:
                items (list): список сообщений

            Returns:
                bool: True если тип сообщения входит в сет TYPES_FOR_ERROR. 
            """
            for msg in items['importMessages']:
                if msg['type'] in TYPES_FOR_ERROR:
                    return True
            return False
        
        def replace_fio(message_text: str) -> str:
            """Удаление перс.данных из строки отчета.\n
            Пока удаляет ФИО отсюда: "...Пользователь ФИО уже...".

            Args:
                message_text (str): изначальная строка

            Returns:
                str: итоговая строка
            """
            points_between = [
                ('Пользователь', 'уже') #Пользователь ФИО уже существует в другой организации, перемещение запрещено настройками вашей организации
            ]
            for point in points_between:
                idx1 = message_text.find(point[0])
                if idx1 != -1: # нашли 
                    idx1 += len(point[0]) + 1
                    idx2 = message_text.find(point[1], idx1)
                    if idx2 != -1:
                        return f'{message_text[0:idx1]}{message_text[idx2:]}'
            return message_text

        def make_message_lines(employees, types):
            """Генерация списка строк для отчета по результату запроса

            Args:
                employees (list): список сообщений по каждому сотруднику
                types (_type_): типы выводимых в отчет ошибок (остальные не войдут в результирующий список)

            Returns:
                list: список со строками отчета
            """
            message_lines = list()
            for employee in employees:
                for msg in employee['importMessages']:
                    if msg['type'] in types:
                        message_lines.append(f"Для табельного номера '{employee['tabNum']}' сообщение типа '{msg['type']}': {replace_fio(msg['text'])}.")
            return message_lines if len(message_lines)>0 else None
        #endregion вспомогательные функции

        decoded_content = response_content.decode("utf-8")
        #self.logger.debug(f'{decoded_content=}')
        response_content = json.loads(decoded_content)
        fatalError = response_content.get('fatalError')
        if fatalError:
            self.logger.error(f"Ответ содержит общую ошибку обработки: '{fatalError}'.")
        else:
            error_employees = list(filter(only_error_items, response_content['employees']))
            message_lines = make_message_lines(error_employees, TYPES_FOR_ERROR)
            if message_lines:
                message_lines.insert(0, f"Результат анализа ошибочных записей, строк '{len(message_lines)}':")
                self.logger.error('\n'.join(message_lines))
                    
    def travel_agent(self) -> None:
        """Основная функция обработки.\n
        Получения информации, подготовка, оправка запроса, получение ответа, анализ и выдача результата.
        """
        agency = self.config.settings.CbtcTravelClick
        agency_name = 'CBTC Travel-Click'
        min_counter, procedure = agency.minCounter, agency.storedProc

        self.logger.info(f"Получение данных из БД для агентства '{agency_name}'")
        employee_db_list = ConnectDB(self.config).fetch(procedure)
        self.logger.info(f"Количество записей '{len(employee_db_list)}' получено из БД")
        if not self.config.is_debug_limit_off: # для debug игнорируем проверку на минимальный лимит по компании.
            if (not employee_db_list) or (len(employee_db_list) < min_counter):
                self.logger.error(f"Количество сотрудников для агентства '{agency_name}' меньше {min_counter}")
                return
        else:
            self.logger.info(f"Включен флаг отладки, ограничение '{min_counter=}' игнорируется")

        proxy = Proxy(self.config)
        self.logger.info(f"Цикл формирования json по компаниям для агентства '{agency_name}'")
        companies = agency.companies
        for company_key in companies.keys():
            company = getattr(companies, company_key)
            company_id = company.id
            result_employees_list = []
            self.logger.info(f"Формирование списка данных для '{company_key}' - '{company_id}'")
            for row in employee_db_list:
                if row[0] == company_id:
                    result_employees_list.append(row)
                    if self.config.is_debug_limit_off: # при включенном ключе отладки берем только 1 запись на компанию.
                        self.logger.info(f"Включен флаг отладки, список '{company_id}' будет только с 1 записью")
                        break
            if result_employees_list == []: # если лист пуст
                self.logger.warning(f"Пустой список данных для '{company_id}'!")
                break
            self.logger.info(f"Количество записей '{len(result_employees_list)}' сформировано для '{company_id}'")
            json_data = {
                'company': str(company.id).strip(),
                'confirm': company.confirm,
                'fullUpdate': company.fullUpdate,
                'incrementUpdate': company.incrementUpdate,
                'employees': self._create_employees_travel(result_employees_list)
            }
            try:
                encoded_data = json.dumps(json_data, ensure_ascii=False).encode('utf-8')
            except Exception as e:
                self.logger.error(f'Ошибка преобразования json в байтстрим. Error: {str(e)}')
            else:
                self.logger.info(f"Отправка данных сотрудников '{company_id}' в агентство '{agency_name}'")
                headers = {"content-type": "application/json; charset=UTF-8"}
                url, username, password = agency.url, agency.username, agency.decrypted_password
                if self.config.is_debug_limit_off:
                    url, password = agency.travel_dev.url, agency.travel_dev.decrypted_password
                    self.logger.info('Включен флаг отладки, отправка данных идет на URL из travel_dev')
                response_content = proxy.send_data(url, headers, username, password, encoded_data)
                if response_content: # обработка респонза от travel-click
                    self._travel_answer_analize(response_content)

class AeroParser(DataParser):
    """Класс-холдер для работы с АэроТревел.
    """
    def __init__(self, config: Configuration) -> None:
        super().__init__(config)

    def _create_profile_aero_xml(self, user):

        profile = xml.Element(
            "profile",
            {
                "uniqueIdentifier": self._camouflage('tabNum', f'{user[18]:0>8}'),  # tabnum
                "companyUniqueIdentifier": "NESTLE_RUSSIA",
            },
        )

        firstName = xml.Element("firstName")
        firstName_ru = xml.SubElement(firstName, "russian")
        firstName_ru.text = user[2]
        firstName_en = xml.SubElement(firstName, "english")
        firstName_en.text = user[5]

        lastName = xml.Element("lastName")
        lastName_ru = xml.SubElement(lastName, "russian")
        lastName_ru.text = user[1]
        lastName_en = xml.SubElement(lastName, "english")
        lastName_en.text = user[4]

        middleName = xml.Element("middleName")
        middleName_ru = xml.SubElement(middleName, "russian")
        middleName_ru.text = user[3]
        middleName_en = xml.SubElement(middleName, "english")

        gender = xml.Element("gender")
        gender.text = self._camouflage('gender', 'Male' if user[6] == 'm' else 'Female')

        dateOfBirth = xml.Element("dateOfBirth")
        _birthday = self._camouflage('birthday', user[7]) # Дата Рождения
        dateOfBirth.text = self._convdate(_birthday)

        dateOfTermination = xml.Element("dateOfTermination", {"xsi:nil": "true"})

        analytics = xml.Element(
            "analytics",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        properties = xml.Element(
            "properties",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        #region Начало доп полей

        property1 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property1, "identifier")
        identifier.text = "Employee ID"
        value = xml.SubElement(property1, "value")
        value.text = self._camouflage('tabNum', f'{user[18]:0>8}')  # tabnum

        properties.append(property1)

        property2 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property2, "identifier")
        identifier.text = "GRADE"
        value = xml.SubElement(property2, "value")
        value.text = str(user[19])

        properties.append(property2)

        property3 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property3, "identifier")
        identifier.text = "Position"
        value = xml.SubElement(property3, "value")
        value.text = user[20]

        properties.append(property3)

        property4 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property4, "identifier")
        identifier.text = "Department"
        value = xml.SubElement(property4, "value")
        value.text = user[21]

        properties.append(property4)

        property5 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property5, "identifier")
        identifier.text = "Structural division"
        value = xml.SubElement(property5, "value")
        value.text = user[22]

        properties.append(property5)

        property6 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property6, "identifier")
        identifier.text = "Cost Center"
        value = xml.SubElement(property6, "value")
        value.text = user[23]

        properties.append(property6)

        property7 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property7, "identifier")
        identifier.text = "Line manager email"
        value = xml.SubElement(property7, "value")
        value.text = self._camouflage('other_email', user[24])

        properties.append(property7)

        #endregion Конец создания доп полей

        analytics.append(properties)

        contacts = xml.Element(
            "contacts",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )
        emailAddress = xml.Element(
            "emailAddress",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
                "kind": "Work",
            },
        )

        address = xml.SubElement(emailAddress, "address")
        address.text = user[17]
#        print(user[17])
        contacts.append(emailAddress)

        documents = xml.Element(
            "documents",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        document = xml.Element(
            "document",
            {
                "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
                "type": "NationalPassport",
            },
        )

        series = xml.SubElement(document, "series")
        series.text = user[13] if (user[13] is not None and len(user[13]) > 0) else user[8]

        number = xml.SubElement(document, "number")
        number.text = user[14] if (user[14] is not None and len(user[14]) > 0) else user[9]

        issuedOn = xml.SubElement(document, "issuedOn")
        _issuedOn = user[15] if (user[15] is not None and len(user[15]) > 0) else user[10]
        issuedOn.text = self._convdate(_issuedOn)

        if user[16] is not None and user[16] != "":
            expiresOn = xml.SubElement(document, "expiresOn")
            expiresOn.text = self._convdate(user[16])
        else:
            expiresOn = xml.SubElement(document, "expiresOn", {"xsi:nil": "true"})
        #print(user[16])

        placeOfBirth = xml.SubElement(document, "placeOfBirth")
        placeOfBirth.text = user[11]

        firstName_doc = xml.SubElement(document, "firstName")
        firstName_doc.text = user[2]

        lastName_doc = xml.SubElement(document, "lastName")
        lastName_doc.text = user[1]

        citizenship = xml.SubElement(document, "citizenship")
        code = xml.SubElement(citizenship, "code")
        iso_attr = xml.SubElement(code, "iso3611-a2")
        iso_attr.text = user[12] if (user[12] is not None and len(user[12]) > 0) else "RU"
        # citizenship.append(iso_attr)
        documents.append(document)

        profile.append(firstName)
        profile.append(middleName)
        profile.append(lastName)
        profile.append(gender)
        profile.append(dateOfBirth)
        # profile.append(dateOfEmployment)
        profile.append(dateOfTermination)
        profile.append(analytics)
        profile.append(contacts)
        profile.append(documents)
        return profile

    def _create_profile_aero_xml_db(self, user, companyUniqueIdentifier):

        if user[8] is None:
            raise Exception("Problem with bithday")

        if user[7] is None:
            raise Exception("Problem with male")

        if user[6] is None:
            raise Exception("Problem with national")

        if user[22] is None or user[23] is None or user[24] is None or user[25] is None:
            raise Exception("Problem with org structure")
        profile = xml.Element(
            "profile",
            {
                "uniqueIdentifier": f'{user[21]:0>8}',  # tabnum
                "companyUniqueIdentifier": companyUniqueIdentifier,
            },
        )

        firstName = xml.Element("firstName")
        firstName_ru = xml.SubElement(firstName, "russian")
        firstName_ru.text = self._camouflage('ru_name', user[2])
        firstName_en = xml.SubElement(firstName, "english")
        firstName_en.text = self._camouflage('en_name', user[5])

        lastName = xml.Element("lastName")
        lastName_ru = xml.SubElement(lastName, "russian")
        lastName_ru.text = self._camouflage('ru_surname', user[1])
        lastName_en = xml.SubElement(lastName, "english")
        lastName_en.text = self._camouflage('en_surname', user[4])

        middleName = xml.Element("middleName")
        middleName_ru = xml.SubElement(middleName, "russian")
        middleName_ru.text = self._camouflage('en_middleName', user[3])
        middleName_en = xml.SubElement(middleName, "english")

        gender = xml.Element("gender")
        gender.text = self._camouflage('gender', 'Male' if user[7] == 'm' else 'Female')

        dateOfBirth = xml.Element("dateOfBirth")
        dateOfBirth.text = self._camouflage('birthday', self._convdate(user[8]))

        dateOfTermination = xml.Element("dateOfTermination", {"xsi:nil": "true"})

        analytics = xml.Element(
            "analytics",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        properties = xml.Element(
            "properties",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        #region Создание доп. полей
        property1 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property1, "identifier")
        identifier.text = "Employee ID"
        value = xml.SubElement(property1, "value")
        value.text = self._camouflage('tabNum', f'{user[21]:0>8}') # tabnum

        properties.append(property1)

        property2 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property2, "identifier")
        identifier.text = "GRADE"
        value = xml.SubElement(property2, "value")
        value.text = str(user[22])

        properties.append(property2)

        property3 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property3, "identifier")
        identifier.text = "Position"
        value = xml.SubElement(property3, "value")
        value.text = user[23]

        properties.append(property3)

        property4 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property4, "identifier")
        identifier.text = "Department"
        value = xml.SubElement(property4, "value")
        value.text = user[24]

        properties.append(property4)

        property5 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property5, "identifier")
        identifier.text = "Structural division"
        value = xml.SubElement(property5, "value")
        value.text = user[25]

        properties.append(property5)

        property6 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property6, "identifier")
        identifier.text = "Cost Center"
        value = xml.SubElement(property6, "value")
        value.text = user[26]

        properties.append(property6)

        property7 = xml.Element(
            "property",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )

        identifier = xml.SubElement(property7, "identifier")
        identifier.text = "Line manager email"
        value = xml.SubElement(property7, "value")
        value.text = self._camouflage('other_email', user[28])

        properties.append(property7)

        #endregion Конец создания доп полей

        analytics.append(properties)

        contacts = xml.Element(
            "contacts",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
            },
        )
        emailAddress = xml.Element(
            "emailAddress",
            {
                "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
                "kind": "Work",
            },
        )

        address = xml.SubElement(emailAddress, "address")
        address.text = self._camouflage('email', user[20])
        contacts.append(emailAddress)

        #region Паспорта
        if user[6] != "RU":
            if user[16] is not None and user[14] is not None and user[15] is not None:

                documents = xml.Element(
                    "documents",
                    {
                        "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                        "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
                    },
                )

                document = xml.Element(
                    "document",
                    {
                        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                        "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                        "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
                        "type": "InternationalPassport",
                    },
                )

                series = xml.SubElement(document, "series")
                series.text = user[14]

                number = xml.SubElement(document, "number")
                number.text = self._camouflage('en_cardNumber', user[15])

                issuedOn = xml.SubElement(document, "issuedOn")
                issuedOn.text = self._convdate(user[16])

                if user[17] is not None and len(user[17]) > 2:
                    expiresOn = xml.SubElement(document, "expiresOn")
                    expiresOn.text = self._convdate(user[17])
                else:
                    expiresOn = xml.SubElement(document, "expiresOn", {"xsi:nil": "true"})
                placeOfBirth = xml.SubElement(document, "placeOfBirth")

                firstName_doc = xml.SubElement(document, "firstName")
                firstName_doc.text = self._camouflage('en_name', user[5])

                lastName_doc = xml.SubElement(document, "lastName")
                lastName_doc.text = self._camouflage('en_surname', user[4])

                citizenship = xml.SubElement(document, "citizenship")
                code = xml.SubElement(citizenship, "code")
                iso_attr = xml.SubElement(code, "iso3611-a2")
                iso_attr.text = user[6]
        else:

            if user[9] is not None and user[10] is not None and user[11] is not None:

                documents = xml.Element(
                    "documents",
                    {
                        "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                        "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
                    },
                )

                document = xml.Element(
                    "document",
                    {
                        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                        "xmlns:xs": "http://www.w3.org/2001/XMLSchema",
                        "xmlns": "http://integration.aeroclub.ru/hub/schemas/profiles",
                        "type": "NationalPassport",
                    },
                )

                series = xml.SubElement(document, "series")
                series.text = user[9]

                number = xml.SubElement(document, "number")
                number.text = self._camouflage('ru_cardNumber', user[10])

                issuedOn = xml.SubElement(document, "issuedOn")
                issuedOn.text = self._convdate(user[11])

                expiresOn = xml.SubElement(document, "expiresOn", {"xsi:nil": "true"})

                placeOfBirth = xml.SubElement(document, "placeOfBirth")

                firstName_doc = xml.SubElement(document, "firstName")
                firstName_doc.text = self._camouflage('ru_name', user[2])

                lastName_doc = xml.SubElement(document, "lastName")
                lastName_doc.text = self._camouflage('ru_surname', user[1])

                citizenship = xml.SubElement(document, "citizenship")
                code = xml.SubElement(citizenship, "code")
                iso_attr = xml.SubElement(code, "iso3611-a2")
                iso_attr.text = user[6]

        try:
            if document is not None:
                documents.append(document)
        except:
            pass
        #endregion Паспорта

        profile.append(firstName)
        profile.append(middleName)
        profile.append(lastName)
        profile.append(gender)
        profile.append(dateOfBirth)
        profile.append(dateOfTermination)
        profile.append(analytics)
        profile.append(contacts)
        try:
            if document is not None:
                profile.append(documents)
        except:
            pass

        return profile

    def _createXML_aero(self, list_aero, company):
        """Создаем XML файл."""

        profiles = xml.Element(
            'profiles',
            {
                'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
                'xmlns:xs': 'http://www.w3.org/2001/XMLSchema',
                'xmlns': 'http://integration.aeroclub.ru/hub/schemas/profiles',
            },
        )

        user_except = list()
        for row in list_aero:
            try:
                profile = self._create_profile_aero_xml_db(row, company)
                profiles.append(profile)
                if self.config.is_debug_limit_off: # при включенном отладочном параметре список будет только с 1 записью.
                    self.logger.info('Включен флаг отладки, список будет только с 1 записью.')
                    break
            except Exception as e:
                user_except.append(f'{row[21]:0>8} {str(e)}')

        if len(user_except) > 1:
            body_exception = "\r\n".join((user_except))
            self.logger.error(f'Ошибки при формировании XML для AeroClub: \r\n {body_exception}')

        tree = xml.tostring(profiles)
        return tree

    def aero_agent(self) -> None:
        """Основная функция обработки.\n
        Получения информации, подготовка, оправка запроса, получение ответа, анализ и выдача результата.
        """
        agency = self.config.settings.AeroClub
        agency_name = 'AeroClub'
        companies = agency.companies

        proxy = Proxy(self.config)
        for company_name in companies.keys():
            company = getattr(companies, company_name)
            company_id = company.id
            min_counter, procedure = company.minCounter, company.storedProc

            self.logger.info(f"Обращение к хранимой процедуре: '{procedure}' для компании '{company_id}'")
            employee_db_list = ConnectDB(self.config).fetch(procedure)
            self.logger.info(f"Количество записей '{len(employee_db_list)}' получено из БД.")
            if not self.config.is_debug_limit_off: # игнорируем минимальный лимит по компании 
                if (not employee_db_list) or (len(employee_db_list) < min_counter):
                    self.logger.error(f"Количество сотрудников для компании '{company_id}' в агентстве '{agency_name}' меньше {min_counter}")
                    continue
            else:
                self.logger.info(f"Включен флаг отладки - ограничение '{min_counter}' игнорируется.")

            self.logger.info(f"Формирование xml для '{company_id}' в агентстве '{agency_name}'")
            finish_xml = self._createXML_aero(employee_db_list, company_id)
            self.logger.info(f"Отправка данных сотрудников '{company_id}' в агентство '{agency_name}'")
            
            user_agent, url, sourceUrl = agency.userAgent, agency.url, agency.sourceUrl
            headers = {
                "Host": sourceUrl,
                "User-Agent": user_agent,
                "Content-Type": "application/vnd.aeroclub.integration-hub.profiles.v1+xml; charset=UTF-8"
            }
            username, password = agency.username, agency.decrypted_password
            response_content = proxy.send_data(url, headers, username, password, finish_xml)
            #if response_content: # обработка респонза от Aero
            #    pass # <-- тут можно обработать обратный ответ, если таковой приходит в ответ.
            
