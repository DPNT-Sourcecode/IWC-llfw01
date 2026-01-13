from datetime import datetime
from enum import IntEnum

class P(IntEnum):
    NORMAL = 2

MAX_TS = datetime.max.replace(tzinfo=None)
t1 = datetime(2025,1,1,12,1)
t2 = datetime(2025,1,1,12,7)

key1 = (0, 0, t1, t1)
key2 = (P.NORMAL, 0, MAX_TS, t2)

print('key1:', key1)
print('key2:', key2)
print('key1 < key2:', key1 < key2)
print()
print('First elements:', key1[0], '<', key2[0], '=', key1[0] < key2[0])
