import logging
from data_parser import TravelParser, AeroParser
from config import Configuration, setupLogging

def main():
    config = Configuration()
    setupLogging(config)
    logger = logging.getLogger(__name__)

    if config.section or config.password:
        config.print_old_or_save_new_pass()
        return
    
    logger.info("Приложение запущено.")
    if config.agency == Configuration.AGENCY_CBTC:
        TravelParser(config).travel_agent()
    elif config.agency == Configuration.AGENCY_AERO:
        AeroParser(config).aero_agent()
    else:
        logger.error(f"Агентство '{config.agency}' не существует." if config.agency else "Агентство не указано.")
        return
    logger.info("Приложение заверешено корректно.")
        
if __name__ == "__main__":
    main()