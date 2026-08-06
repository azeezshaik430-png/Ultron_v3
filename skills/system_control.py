"""
ULTRON V3
System Control Skill
"""

import datetime
import psutil



def get_time():

    now = datetime.datetime.now()

    return (
        f"The time is {now.strftime('%I:%M %p')}"
    )



def get_date():

    today = datetime.datetime.now()

    return (
        f"Today is {today.strftime('%d %B %Y')}"
    )



def get_battery():

    battery = psutil.sensors_battery()


    if battery:

        percent = battery.percent

        if battery.power_plugged:

            status = "charging"

        else:

            status = "not charging"


        return (
            f"Battery is {percent}% and {status}"
        )


    return "Battery information unavailable"



def system_status():

    return (
        "All systems are online Boss. "
        "Voice, memory and command systems are working."
    )