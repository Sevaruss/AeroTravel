import argparse
import yaml, json, os, sys
from cryptography.fernet import Fernet
from pathlib import Path
import logging.config

prog_name = 'AeroTravel.exe'
prog_version = '2.1'
prog_version_date = '18.11.2024'
prog_description = 'Подготовка и отправка данных для AeroClub и CbtcTravelClick'

class Settings:
    def __init__(self, settings_dict):
        self.__dict__.update(settings_dict)
        engine = Fernet(Configuration.KEY)
        if "password" in settings_dict.keys():
            password = settings_dict.get("password")
            self.decrypted_password = engine.decrypt(password).decode()
    def keys(self):
        return self.__dict__.keys()
    def __setitem__(self, key, value):
        setattr(self, key, value)
    def __getitem__(self, key):
        return getattr(self, key)

class Configuration:
    """ Класс-холдер конфигурационных параметров (командная строка и yaml-файл с настройками).
    """
    #region Конфигурационные константы
    AGENCY_AERO, AGENCY_CBTC, NEW_USER, TRAVEL_DEV, MAIL_USER = 'AERO', 'CBTC', 'NUSR', 'TDEV', 'SMTP'
    PROXY_ZSCALER, PROXY_SYSTEM, PROXY_NONE = 'zscaler', 'system', 'none'
    KEY = b'02p-Lards_EpJRbSQHn6c1fqZdYBLGBibyFNpPTQ8pA='
    #endregion Конфигурационные константы
    def __init__(self):
        """Инициализация конфигурации приложения.
        """
        self.path = Path(__file__).parents[0]
        #self.settings_path = self.path / 'settings.yaml'
        self.settings_path = 'settings.yaml' # имя файла жестко зашито, лежит рядом с exe-шником.
        # считывние аргументов командной строки
        self.parser = argparse.ArgumentParser(prog=prog_name,
                #usage='%(prog)s [options]',
                description=prog_description,
                epilog='%(prog)s' + ', версия: ' + prog_version + ', ' + prog_version_date)

        self.parser.add_argument('-a', '--agency', dest='agency', type=str, choices=[self.AGENCY_AERO, self.AGENCY_CBTC],
                                 help=f'Агентство, куда будут отправляться данные.')
        self.parser.add_argument('-p', '--proxy', dest='proxy', type=str, default=self.PROXY_ZSCALER, choices=[self.PROXY_ZSCALER, self.PROXY_SYSTEM, self.PROXY_NONE],
                                 help=f'Отправка запросов через прокси (по умолчанию %(default)s)')
        self.parser.add_argument('-e', dest='password', type=str,
                                 help='Шифрование пароля для вставки в yaml. Вместе с -y добавляет в секцию yaml, иначе выводит на экран.')
        self.parser.add_argument('-y', dest='section', type=str,
                                 choices=[self.AGENCY_AERO, self.AGENCY_CBTC, self.NEW_USER, self.TRAVEL_DEV, self.MAIL_USER], 
                                 help='Секция в yaml, куда надо вставить пароль.')
        if '-secret' in sys.argv:
            self.parser.add_argument('-secret', dest='secret', action='store_true', default=False,
                                     help='Активация секретных параметров')
            self.parser.add_argument('-showpass', dest='showpass', action='store_true', default=False,
                                     help='Секретный параметр: показывает расшифрованный пароль, если указать имя секции в -y.')
        
        self.namespace = self.parser.parse_args()
        
        # считывание настроек приложения из yaml-файла.
        with open(self.settings_path, encoding='utf-8') as config_file:
            settings = yaml.safe_load(config_file)
            self.logging_config = settings.get('logging_config')
            self.settings = json.loads(json.dumps(settings), object_hook=Settings)
            # если у settings есть раздер smtp, у которого есть атрибуты mailuser и password
            # и пароль расшифрован, то меняем его у logging_config.  
            if hasattr(self.settings, 'smtp') and hasattr(self.settings.smtp, 'mailuser') and \
                hasattr(self.settings.smtp, 'password') and hasattr(self.settings.smtp, 'decrypted_password'):
                new_cred = [self.settings.smtp.mailuser, self.settings.smtp.decrypted_password]
                self.logging_config['handlers']['mail']['credentials'] = new_cred

    def print_old_or_save_new_pass(self) -> None:
        """Печать на экран старого или установка нового пароля"""
        if self.section and not self.password: # Если указан -y (имя секции), но не указан -e (пароль)
            #выводим на экран пароль указанной секции только если указан секретный параметр.
            if not self.showpass: 
                print(f'Пароль для {self.section}: -secret !')
                return
            else:
                if self.section == Configuration.AGENCY_AERO:
                    print(f'Пароль для {self.section}: {self.settings.AeroClub.decrypted_password}')
                elif self.section == Configuration.AGENCY_CBTC:
                    print(f'Пароль для {self.section}: {self.settings.CbtcTravelClick.decrypted_password}')
                elif self.section == Configuration.NEW_USER:
                    print(f'Пароль для {self.section}: {self.settings.CbtcTravelClick.newUser.decrypted_password}')
                elif self.section == Configuration.TRAVEL_DEV:
                    print(f'Пароль для {self.section}: {self.settings.CbtcTravelClick.travel_dev.decrypted_password}')
                elif self.section == Configuration.MAIL_USER:
                    print(f'Пароль для {self.section}: {self.settings.smtp.decrypted_password}')
                else:
                    print(f'Указанный ключ {self.section} не обрабатывается. Варианты: {Configuration.AGENCY_AERO}, {Configuration.AGENCY_CBTC}, {Configuration.NEW_USER}, {Configuration.TRAVEL_DEV}. {Configuration.MAIL_USER}.')
        else: # если указан пароль, и указан или не указана секция.
            encripted_password = Configuration.encrypt_password(self.password)
            if not self.section: # если не указана -y (имя секции) - зашифрованный пароль выводим на экран
                print(f'Шифрованный пароль:\n{encripted_password}\nДля автоматической замены в нужной секции, укажите имя секции в соответствующем параметре.')
                return
            # указаны -y (секция) и -e (пароль)
            if self.section==Configuration.AGENCY_AERO:
                section = 'AeroClub:'
                new_pass_line = f'  password: {encripted_password}\n'
            elif self.section==Configuration.AGENCY_CBTC:
                section = 'CbtcTravelClick:'
                new_pass_line = f'  password: {encripted_password}\n'
            elif self.section==Configuration.NEW_USER:
                section = 'newUser:'
                new_pass_line = f'    password: {encripted_password}\n'
            elif self.section==Configuration.TRAVEL_DEV:
                section = 'travel_dev:'
                new_pass_line = f'    password: {encripted_password}\n'
            elif self.section==Configuration.MAIL_USER:
                section = 'smtp:'
                new_pass_line = f'  password: {encripted_password}\n'

            # открываем файл и меняем пароль в нем.
            with open(self.settings_path, mode='r+', encoding='utf-8') as config_file:
                config_lines = config_file.readlines()
                old_pass_line, secFounded = None, False
                for line in config_lines:
                    if not secFounded and line.find(section)!=-1: # если нашли секцию
                        secFounded = True
                        continue
                    if secFounded and line.find('password')!=-1: #ищем внутри найденной секции password
                        old_pass_line = line
                        break
                if old_pass_line: # нашли
                    # заменяем в списке строк файла-конфига старый пароль, на новый
                    new_config_lines = [new_pass_line if line==old_pass_line else line for line in config_lines]
                    config_file.seek(0)
                    config_file.writelines(new_config_lines) # сохраняем обратно
                    print(f'Пароль заменен в секции {section}')

    #region Параметры командной строки в виде свойств.
    @property
    def proxy(self) -> str:
        """Параметр командной строки: указывает какой прокси использовать.
            Returns: str: именование прокси
        """
        return self.namespace.proxy
    @property
    def agency(self) -> str:
        """Флаг командной строки: указывает имя агентства.
            Returns: str: имя агентства
        """
        return self.namespace.agency
    @property
    def password(self) -> str:
        """Флаг командной строки: пароль для шифровки.
            Returns: str: пароль
        """
        return self.namespace.password
    @property
    def showpass(self) -> str:
        """Флаг командной строки: какой из паролей показывать.
            Returns: str: ключ
        """
        return self.namespace.showpass if '-secret' in sys.argv else None
    @property
    def section(self) -> str:
        """Флаг командной строки: какая секция используется.
            Returns: str: ключ секции
        """
        return self.namespace.section
    @property
    def is_debug_limit_off(self) -> bool:
        """Включение отладочной отправки: выключение минимальных лимитов, формирование только 1 записи для каждой companies, и передача по указанным URL.
            Returns: bool: true если дебаг включен.
        """
        return self.settings.settings.debug_limit_off
    #endregion Параметры командной строки в виде свойств.

    #region Статические методы шифрования/дешифрования паролей
    @staticmethod
    def encrypt_password(password):
        """Шифрование пароля.

        Args:
            password (str): нешифрованный пароль

        Returns:
            str: зашифрованный пароль
        """
        engine = Fernet(Configuration.KEY)
        return engine.encrypt(password.encode()).decode()

    @staticmethod
    def decrypt_password(password):
        """Дешифрование пароля.

        Args:
            password (str): шифрованный пароль

        Returns:
            str: дешифрованный пароль
        """
        try:
            return Fernet(Configuration.KEY).decrypt(password).decode()
        except Exception as e:
            return None
    #endregion Статические методы шифрования/дешифрования паролей

def setupLogging(config: Configuration):
    """Установка логирования по параметрам конфигурации из файла.

    Args:
        config (Configuration): Параметры конфигурации
    """
    def mk_logs_dir(path):
        dir, filename = os.path.split(path)
        Path(dir).mkdir(parents=True, exist_ok=True)

    path = config.settings.logging_config.handlers.file.filename
    mk_logs_dir(path)
    logging.config.dictConfig(config.logging_config)
