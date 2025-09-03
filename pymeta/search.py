import os
import re
import sys
import logging
import threading
from time import sleep
from pymeta.logger import Log
from bs4 import BeautifulSoup
from tldextract import extract
from urllib.parse import urlparse, unquote
from datetime import datetime, timedelta
from camoufox.sync_api import Camoufox
logging.getLogger("tldextract").setLevel(logging.CRITICAL)
logging.getLogger("filelock").setLevel(logging.CRITICAL)


class Timer(threading.Thread):
    def __init__(self, timeout):
        threading.Thread.__init__(self)
        self.start_time = None
        self.running = None
        self.timeout = timeout

    def run(self):
        self.running = True
        self.start_time = datetime.now()
        logging.debug("Thread Timer: Started")

        while self.running:
            if (datetime.now() - self.start_time) > timedelta(seconds=self.timeout):
                self.stop()
            sleep(0.05)

    def stop(self):
        logging.debug("Thread Timer: Stopped")
        self.running = False


class PyMeta:
    def __init__(self, search_engine, target, file_type,  timeout, conn_timeout=3, proxies=[], jitter=0, max_results=50):
        self.search_engine = search_engine
        self.file_type = file_type.lower()
        self.conn_timeout = conn_timeout
        self.max_results = max_results
        self.timeout = timeout
        self.target = target
        self.jitter = jitter

        self.results = []
        self.regex = re.compile("[https|https]([^\)]+){}([^\)]+)\.{}".format(self.target, self.file_type))
        self.url = {
            'google': 'https://www.google.com/search?q=site:{}+filetype:{}&num=100&start={}',
            'bing': 'http://www.bing.com/search?q=site:{}%20filetype:{}&first={}'
        }

    def search(self):
        search_timer = Timer(self.timeout)
        search_timer.start()

        with Camoufox(headless=True) as browser:
            while search_timer.running:
                try:
                    url = self.url[self.search_engine].format(self.target, len(self.results))
                    page = browser.new_page()
                    response = page.goto(url, timeout=self.conn_timeout * 100000)
                    
                    if response is None:
                        Log.warn("No response for URL: {}".format(url))
                        page.close()
                        break

                    http_code = response.status
                    if http_code != 200:
                        Log.info("{:<3} | {:<4} - {} ({})".format(len(self.results), self.file_type, url, http_code))
                        Log.warn('None 200 response, exiting search ({})'.format(http_code))
                        page.close()
                        break

                    content = page.content()
                    resp = type('Response', (), {'status_code': http_code, 'content': content})
                    
                    self.page_parser(resp)
                    Log.info("{:<3} | {:<4} - {} ({})".format(len(self.results), self.file_type, url, http_code))
                    page.close()
                    sleep(self.jitter)
                except KeyboardInterrupt:
                    Log.warn("Keyboard interruption detected, stopping search...")
                    break

        search_timer.stop()
        return self.results

    def page_parser(self, resp):
        for link in extract_links(resp):
            try:
                self.results_handler(link)
            except Exception as e:
                Log.warn('Failed Parsing: {}- {}'.format(link.get('href'), e))

    def results_handler(self, link):
        url = str(link.get('href'))
        if self.regex.match(url):
            self.results.append(url)
            logging.debug('Added URL: {}'.format(url))


def get_statuscode(resp):
    try:
        return resp.status_code
    except:
        return 0

def clean_filename(filename):
    supported_extensions = ['pdf', 'xls', 'xlsx', 'csv', 'doc', 'docx', 'ppt', 'pptx']

    # Extract the extension and remove any query string or other characters after it
    match = re.search(r'\.({})($|\?)'.format('|'.join(supported_extensions)), filename, re.IGNORECASE)
    if match:
        filename = filename[:match.end(1)]
    else:
        return filename  # If no supported extension is found, return the original filename as is

    # Remove URL encoding and replace special characters with underscores
    decoded_filename = unquote(filename)
    cleaned_filename = re.sub(r'[^a-zA-Z0-9_.-]', '_', decoded_filename)

    return cleaned_filename

def download_file(url, dwnld_dir, timeout=6):
    try:
        logging.debug('Downloading: {}'.format(url))
        with Camoufox(headless=True) as browser:
            page = browser.new_page()
            response = page.goto(url, timeout=timeout * 1000)
            if response is None:
                Log.fail('Download Failed (no response) - {}'.format(url))
                return

            http_code = response.status
            if http_code != 200:
                Log.fail('Download Failed ({}) - {}'.format(http_code, url))
                page.close()
                return

            content = page.content()
            filename = clean_filename(url.split("/")[-1])
            with open(os.path.join(dwnld_dir, filename), 'wb') as f:
                if isinstance(content, str):
                    f.write(content.encode('utf-8'))
                else:
                    f.write(content)
            page.close()
    except Exception as e:
        logging.debug("Download Error: {}".format(e))
        pass

def extract_links(resp):
    links = []
    soup = BeautifulSoup(resp.content, 'lxml')
    for link in soup.find_all('a'):
        links.append(link)
    return links


def extract_subdomain(url):
    return urlparse(url).netloc


def extract_webdomain(url):
    x = extract(url)    # extract base domain from URL
    return x.domain+'.'+x.suffix if x.suffix else x.domain
