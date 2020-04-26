import os
import re
import csv
from datetime import datetime
from urllib.parse import unquote, urlparse

def guess_filename_from_url(url, make_unique=True, default="xhr_requests", ext="txt"):
    now = get_datetime_as_str()
    if ext:
        ext = ext if ext.startswith(".") else "."+ ext
    u = urlparse(url)
    filename=default
    if u.netloc:
        host = unquote(u.netloc)
        filename = str(host).replace(".", "_")
    elif u.path:
        path = unquote(u.path)
        filename = str(path).replace(".", "_").replace("/","_")
    filename = remove_specialchars_fromstr(filename)
    if make_unique:
        filename += "_" + now
    if ext:
        filename += ext
    return filename

def remove_specialchars_fromstr(string, replacement=""):
    p = r"[^0-9a-zA-Z-_]+"
    string = re.sub(p, replacement, string)
    return string

def get_datetime_as_str(date=None, fmt=None):
    date = date or datetime.now()
    fmt = fmt or "%Y%m%d%H%M%S"
    return datetime.strftime(date, fmt)

def write_to_csv(csv_path, header, records, quoting=csv.QUOTE_MINIMAL):
    if not isinstance(records, (list, tuple)):
        records = [records]
    records = remove_line_sep(records)
    header = remove_line_sep(header)
    with open(csv_path, "w", newline="") as fd:
        writer = csv.DictWriter(fd, header, quoting=quoting)
        writer.writeheader()
        writer.writerows(records)

def remove_line_sep(data):
    if isinstance(data, str):
        return _remove_newlines(data)
    if isinstance(data, (list, tuple)):
        r = []
        for d in data:
            d2 = remove_line_sep(d)
            r.append(d2)
        return r
    if isinstance(data, dict):
        d = {}
        for k,v in data.items():
            k2 = remove_line_sep(k)
            v2 = remove_line_sep(v)
            d[k2] = v2
        return d
    return data

def _remove_newlines(string, replacement=None):
    replacement = replacement or r"\t"
    string = string.replace(os.linesep, replacement)
    string = string.replace("\r", replacement)
    string = string.replace("\n", replacement)
    return string