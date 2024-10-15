import logging
import pyodbc

class ConnectDB:
    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        try:
            settings = config.settings
            driver = "DRIVER=" + settings.db.driver
            server = "SERVER=" + settings.db.server
            database = "DATABASE=" + settings.db.database
            type_auth = "Trusted_Connection=yes;"
            self.conn_str = ";".join([driver, server, database, type_auth])
            #self.listdrivers = pyodbc.drivers()

            self.logger.debug(f'Строка соединения: {self.conn_str}')
            self.conn = pyodbc.connect(self.conn_str)
            self.cursor = self.conn.cursor()
        except Exception as ex:
            self.logger.error(f'Ошибка соединения: {str(ex)}')

    def fetch(self, stored_proc):
        try:
            self.logger.debug(f"Обращение к хранимой процедуре: '{stored_proc}'")
            self.cursor.execute(stored_proc)
            return self.cursor.fetchall()
        except Exception as ex:
            self.logger.error(f'Ошибка вызова БД: {str(ex)}')
            return []
