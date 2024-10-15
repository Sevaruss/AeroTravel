import argparse
import yaml, json, os, sys
from cryptography.fernet import Fernet
from pathlib import Path
import logging.config
from pathlib import Path

_prog_name = 'AeroTravel.exe'
_version_number = '2.0'
_version_date = '24.05.2024'
_description = 'Подготовка и отправка данных для AeroClub и CbtcTravelClick'

class Settings:
    def __init__(self, settings_dict):
        self.__dict__.update(settings_dict)
        engine = Fernet(Configuration.KEY)
        if "password" in settings_dict.keys():
            password = settings_dict.get("password")
            self.decrypted_password = engine.decrypt(password).decode()
    def keys(self):
        return self.__dict__.keys()

class Configuration:
    #region Конфигурационные константы
    AGENCY_AERO, AGENCY_CBTC, NEW_USER, TRAVEL_DEV = 'AERO', 'CBTC', 'NUSR', 'TDEV'
    PROXY_ZSCALER, PROXY_SYSTEM, PROXY_NONE = 'zscaler', 'system', 'none'
    KEY = b'02p-Lards_EpJRbSQHn6c1fqZdYBLGBibyFNpPTQ8pA='
    #endregion Конфигурационные константы
    """Инициализация конфигурации приложения.
    """
    def __init__(self):
        self.path = Path(__file__).parents[0]
        #self.settings_path = self.path / 'settings.yaml'
        self.settings_path = 'settings.yaml'
        self.parser = argparse.ArgumentParser(prog=_prog_name,
                #usage='%(prog)s [options]',
                description=_description,
                epilog='%(prog)s' + ', version: ' + _version_number + ', ' + _version_date)

        self.parser.add_argument('-a', '--agency', dest='agency', type=str, choices=[self.AGENCY_AERO, self.AGENCY_CBTC],
                                 help=f'Агентство, куда будут отправляться данные.')
        self.parser.add_argument('-p', '--proxy', dest='proxy', type=str, default=self.PROXY_ZSCALER, choices=[self.PROXY_ZSCALER, self.PROXY_SYSTEM, self.PROXY_NONE],
                                 help=f'Отправка запросов через прокси (по умолчанию %(default)s)')
        self.parser.add_argument('-e', dest='password', type=str,
                                 help='Шифрование пароля для вставки в yaml. Вместе с -y добавляет в секцию yaml, иначе выводит на экран.')
        self.parser.add_argument('-y', dest='section', type=str, choices=[self.AGENCY_AERO, self.AGENCY_CBTC, self.NEW_USER, self.TRAVEL_DEV], 
                                 help='Секция в yaml, куда надо вставить пароль.')
        if '-secret' in sys.argv:
            self.parser.add_argument('-secret', dest='secret', action='store_true', default=False,
                                     help='Активация секретных параметров')
            self.parser.add_argument('-showpass', dest='showpass', action='store_true', default=False,
                                     help='Секретный параметр: показывает расшифрованный пароль, если указать имя секции в -y.')
        
        self.namespace = self.parser.parse_args()
        
        with open(self.settings_path, encoding='utf-8') as config_file:
            settings = yaml.safe_load(config_file)
            self.logging_config = settings.get('logging_config')
            self.settings = json.loads(json.dumps(settings), object_hook=Settings)

    def print_old_or_save_new_pass(self):
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
                else:
                    print(f'Указанный ключ {self.section} не обрабатывается. Варианты {Configuration.AGENCY_AERO}, {Configuration.AGENCY_CBTC}, {Configuration.NEW_USER}, {Configuration.TRAVEL_DEV}.')
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

    @property
    def proxy(self) -> str:
        """Флаг командной строки: указывает использовать внешней прокси.
            Returns: bool: True, если стоит в командной строке
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
            Returns: str: ключ
        """
        return self.namespace.section
    @property
    def is_debug_limit_off(self) -> bool:
        """Включение отладочной отправки: выключение минимальных лимитов, формирование только 1 записи для каждой companies, и передача по указанным URL.
            Returns: bool: true если дебаг включен.
        """
        return self.settings.settings.debug_limit_off

    @staticmethod
    def encrypt_password(password):
        engine = Fernet(Configuration.KEY)
        return engine.encrypt(password.encode()).decode()

    @staticmethod
    def decrypt_password(password):
        try:
            return Fernet(Configuration.KEY).decrypt(password).decode()
        except Exception as e:
            return None

def setupLogging(config: Configuration):
    def mk_logs_dir(path):
        dir, filename = os.path.split(path)
        Path(dir).mkdir(parents=True, exist_ok=True)

    path = config.settings.logging_config.handlers.file.filename
    mk_logs_dir(path)
    logging.config.dictConfig(config.logging_config)
