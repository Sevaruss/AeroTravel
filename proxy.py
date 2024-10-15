import requests
import logging
import re
from requests.auth import HTTPBasicAuth

from config import Configuration

class Proxy:
    def __init__(self, config: Configuration):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.settings = config.settings
        self.proxy_list = None
        if self.config.proxy == Configuration.PROXY_ZSCALER:
            self.proxy_list = self._get_proxy_list()
        elif self.config.proxy == Configuration.PROXY_SYSTEM:
            self.proxy_list = [self.settings.settings.proxyIp]

    def _get_proxy_list(self) -> list:
        """Функция для получения списка внешних прокси Nestle

        Returns:
            list: список внешних прокси 
        """
        searchIn = "//******   Use the Standard Zscaler proxies if not internal or exception   ******" # искомая строка в файле от zscaler
        NestleProxy = self.settings.settings.nestleProxy
        prlist = requests.get(NestleProxy)
        buffer_proxy = prlist.text
        flagWrite = False
        self.logger.debug('Запрос от zscaler выполнен, ищем требуемые прокси в response')
        buffer_proxy = buffer_proxy.splitlines()
        #ищем нужную строку с 4 прокси адресами и пишем их в основной массив прокси
        for line in buffer_proxy:
            if(str.find(line, searchIn) != -1): # нашли искомую строку, пропускаем ее и переходим к следующей
                flagWrite = True
                continue
            if flagWrite:
                line = re.sub('\\s|[;}"]|DIRECT|return', '', line) # удаление из строки всех вхождений паттерна
                if line:
                    self.logger.debug(f'Строка со списком прокси найдена: {line}')
                    line = line.split('PROXY')
                    line = list(filter(None, line))
                    return line
        self.logger.error('Ни одной прокси не найдено в ответе от zscaler! Возможно изменился формат ответа.')
        return list()

    def _post_request(self, source_url: str, username: str, password: str, headers: dict, proxy: str, data: str):
        try:
            self.logger.debug(f'Запрос через {proxy=}.')
            proxiesDict = {'http': proxy, 'https': proxy} if proxy else None 
            response = requests.post(url=source_url, data=data, verify=False, proxies=proxiesDict, headers=headers, auth=HTTPBasicAuth(username, password))
            self.logger.info(f'post-запрос завершен успешно, код http возврата={response.status_code}')
            return response
        except Exception as ex:
            self.logger.error(f'Ошибка при вызове через {proxy=}. Error: {str(ex)}')
            return None
        
    def send_data(self, url, headers, username, password, data):
        self.logger.debug(f"Запрос на '{url=}'")
        if self.proxy_list is None: # proxy_list - пустой, вызов не через прокси
            response = self._post_request(url, username, password, headers, None, data)
            if response:
                self.logger.info(f'Успешный http-запрос без прокси.')
            else: 
                self.logger.warning('Запрос не был успешно вызван.')
        else:
            for proxy in self.proxy_list:
                response = self._post_request(url, username, password, headers, proxy, data)
                if response:
                    self.logger.info(f'Успешный http-запрос через {proxy=}')
                    break
        # обработка респонза и возврат контента.
        response_content = None
        if response:
            if not response.content:
                self.logger.warning(f'Обратный ответ получен, но контент ответа пустой.')
            else:
                response_content = response.content
        else:
            self.logger.warning('Неуспешный http-запрос, response отсутствует.')
        return response_content
