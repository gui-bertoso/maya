import datetime
import os.path
import settings


def create_log(message):
    if os.path.exists(settings.LOGS_PATH):
        file = open(
            settings.LOGS_PATH,
            "a"
        )
    else:
        file = open(
            settings.LOGS_PATH,
            "w+"
        )
        file.write("-----------------------------------------------------------------")
        file.close()

        file = open(
            settings.LOGS_PATH,
            "a"
        )

    file.writelines(
        f"\nDATE: {datetime.datetime.today()}"
        f"\nLOG: {message}"
        f"\n-----------------------------------------------------------------"
    )
