import datetime
import os.path
import new_settings


def create_log(message):
    if os.path.exists(new_settings.LOGS_PATH):
        file = open(
            new_settings.LOGS_PATH,
            "a"
        )
    else:
        file = open(
            new_settings.LOGS_PATH,
            "w+"
        )
        file.write("-----------------------------------------------------------------")
        file.close()

        file = open(
            new_settings.LOGS_PATH,
            "a"
        )

    file.writelines(
        f"\nDATE: {datetime.datetime.today()}"
        f"\nLOG: {message}"
        f"\n-----------------------------------------------------------------"
    )
