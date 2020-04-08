from datetime import datetime
import pytz

timestamp = datetime.now(pytz.utc).timestamp()
date = datetime.now().strftime("%d %b %Y")

print(timestamp, date)