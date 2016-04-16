
from __future__ import division, print_function
import re

import dateutil.parser


time_pattern = re.compile(
    r'^'
    r'(?:(?P<d>\d+)[dD])?'
    r'(?:(?P<h>\d+)[hH])?'
    r'(?:(?P<m>\d+)[mM])?'
    r'(?:(?P<s>\d+)[sS]?)?'
    r'$')


def seconds_to_string(seconds):
    parts = [
        (604800, 'w'),
        (86400, 'd'),
        (3600, 'h'),
        (60, 'm'),
    ]
    s = []
    for scale, suffix in parts:
        if seconds >= scale:
            s.append('{}{}'.format(seconds // scale, suffix))
            seconds %= scale
    if seconds:
        s.append('{}s'.format(seconds))
    return ''.join(s)


def to_seconds(time_string):
    match = time_pattern.match(time_string)
    if match is None:
        return
    day = match.group('d')
    hour = match.group('h')
    minute = match.group('m')
    second = match.group('s')
    seconds = int(second) if second else 0
    seconds += int(minute)*60 if minute else 0
    seconds += int(hour)*3600 if hour else 0
    seconds += int(day)*86400 if day else 0
    return seconds


def parse_timestamp(time_string):
    # TODO parse german weekdays?
    try:
        return dateutil.parser.parse(time_string)
    except ValueError:
        return


def simple_tobytes(data, enc='utf-8'):
    if isinstance(data, dict):
        return {k.encode(enc): simple_tobytes(v, enc) for k, v in data.iteritems()}
    if isinstance(data, list):
        return [simple_tobytes(v, enc) for v in data]
    if isinstance(data, unicode):
        return data.encode(enc)
    return data


if __name__ == '__main__':
    x = to_seconds('7d')
    print(seconds_to_string(x))
