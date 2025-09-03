import os
import logging
from pymeta.logger import Log
from pymeta.search import clean_filename
from subprocess import getoutput
from shutil import move, which


def exif_check():
    # Check exiftool installed and auto-find its path
    exiftool_path = which('exiftool')
    # Arch 'fix'
    if not exiftool_path and os.path.exists('/usr/bin/vendor_perl/exiftool'):
        exiftool_path = '/usr/bin/vendor_perl/exiftool'
    if not exiftool_path:
        Log.warn("ExifTool not installed or not found in PATH, closing.")
        exit(0)
    try:
        version = getoutput(f'{exiftool_path} -ver')
        float(version)
        return True
    except Exception as e:
        Log.warn(f"ExifTool version parse failed: {e}")
        exit(0)


def report_source_url(urls, output_file):
    # Add source URLs to exif data
    with open(output_file, 'r', encoding="ISO-8859-1") as in_csv, open('.pymeta_tmp.csv', 'w') as out_csv:
        for r in in_csv:
            try:
                url = url_match(urls, r.split(',')[0])
                out_csv.write("{},{}".format(url, r))
            except Exception as e:
                logging.debug('URL ReParsing Error: {} = {}'.format(r, e))

    os.remove(output_file)
    move('.pymeta_tmp.csv', output_file)


def url_match(urls, filename):
    if filename == "SourceFile":
        return "SourceURL"

    for url in urls:
        if filename.split("/")[-1] in url:
            return url
        elif filename.split("/")[-1] == clean_filename(url.split("/")[-1]):
            return url
    return "n/a"

