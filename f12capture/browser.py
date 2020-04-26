import json
import asyncio
from datetime import datetime
from urllib.parse import urlparse

from pyppeteer import launch
from pyppeteer import errors as pyp_errors

from click_helper import echo_warning, echo_error

class Browser(object):
    '''Wrapper for Puppeteer
    Also since puppeter is supposed to be used asynchronous, this class provides methods that basically wraps
    start to end of what happens in puppeter within async loop that is invoked within the ctx of the method
    '''
    XHR = "xhr"
    DEFAULT_TIMEOUT = 60000     #1 min

    #events
    LOAD = "load"
    DOMLOADED = "domcontentloaded"
    NETWORK0 = "networkidle0"
    NETWORK2 = "networkidle2"

    @staticmethod
    def guess_wait_for(wait_for_text):
        if not wait_for_text:
            return None
        if "load" in wait_for_text.lower():
            return Browser.LOAD
        elif "DOM" in wait_for_text.lower():
            return Browser.DOMLOADED
        elif "NET" in wait_for_text.lower() and "2" in wait_for_text.lower():
            return Browser.NETWORK2
        elif "NET" in wait_for_text.lower():
            return Browser.NETWORK0
    
    @staticmethod
    def get_url_parts(url):
        u = urlparse(url)
        return u
      
    @staticmethod
    def url_ends_with(url, end_string):
        if not (url and end_string):
            return False
        #tries to parse given url to determine if url path ends with given string. This is done so that
        #if url has query parts (eg: example.com/image.png?q=small), those will be ignored and we can 
        #truly compare with path. As a fallback (unable to parse), this method uses url string directly
        url = str(url).strip().lower()
        end_string = end_string.strip().lower()
        try:
            url_parts = Browser.get_url_parts(url)
            if url_parts.path:
                if url_parts.path.strip().endswith(end_string):
                    return True
        except:
            pass
        return url.endswith(end_string)
    
    @staticmethod
    def url_contains(url, contains_string):
        if not (url and contains_string):
            return False
        url = str(url).strip().lower()
        contains_string = contains_string.strip().lower()
        return contains_string in url
    
    @staticmethod
    def url_is_domain(url, domain):
        if not (url and domain):
            return False
        domain_parts = Browser.get_url_parts(domain.strip().lower())
        url_parts = Browser.get_url_parts(url.strip().lower())
        if url_parts and url_parts.netloc:
            actual_domain = url_parts.netloc.strip()
            expected_domain = domain_parts.netloc.strip()
            if actual_domain.endswith(expected_domain):
                return True
        return False
    
    @staticmethod
    def url_is_image(url):
        image_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".gif", ".bmp"]
        for img in image_extensions:
            if Browser.url_ends_with(url, img):
                return True
        return False

    def __init__(self, url):
        self.url = url
        self._requests = []
        self._lock = asyncio.Lock()
    
    def capture_xhr(self, timeout, wait_for, ignore_images=False):
        #asyncio.run(self.capture_xhr_async())
        page_options = self.get_page_options(timeout, wait_for)
        asyncio.get_event_loop().run_until_complete(self.capture_xhr_async(page_options, ignore_images))
        return self._requests
    
    def filter_requests(self, requests, include_domain, exclude_domain, include_url_contains, exclude_url_contains,
        include_url_ends, exclude_url_ends, ignore_redirect):
        if not isinstance(requests, (list, tuple)):
            requests = [requests]
        #in case none of the filter is requested, return all
        if not any([include_domain, exclude_domain, include_url_contains, exclude_url_contains,
            include_url_ends, exclude_url_ends, ignore_redirect]):
            return requests
        results = []
        for r in requests:
            tmp_r = r
            if tmp_r and include_domain:
                tmp_r = r if Browser.url_is_domain(r.url, include_domain) else None
            if tmp_r and exclude_domain:
                tmp_r = None if Browser.url_is_domain(r.url, exclude_domain) else r
            if tmp_r and include_url_contains:
                tmp_r = r if Browser.url_contains(r.url, include_url_contains) else None
            if tmp_r and exclude_url_contains:
                tmp_r = None if Browser.url_contains(r.url, exclude_url_contains) else r
            if tmp_r and include_url_ends:
                tmp_r = r if Browser.url_ends_with(r.url, include_url_ends) else None
            if tmp_r and exclude_url_ends:
                tmp_r = None if Browser.url_ends_with(r.url, exclude_url_ends) else r
            if tmp_r and ignore_redirect:
                status = int(r.response_code) if r.response_code else 0
                tmp_r = None if (status >= 300 and status < 400) else r
            if tmp_r:
                results.append(r)
        return results
    
    async def capture_xhr_async(self, page_options, ignore_images=False):
        browser = await launch()
        page = await browser.newPage()
        await page.setRequestInterception(True)
        page.on('request', lambda req: asyncio.ensure_future(self.intercept_start(req, ignore_images)))
        page.on('requestfinished', lambda req: asyncio.ensure_future(self.intercept_end(req)))
        page.on('requestfailed', lambda req: asyncio.ensure_future(self.intercept_end(req)))
        timeout = page_options.get('timeout') or Browser.DEFAULT_TIMEOUT
        try:
            await page.goto(self.url, **page_options)
            if not page_options.get('waitUntil'):
                await page.waitFor(timeout)
        except pyp_errors.TimeoutError:
            echo_warning(f"Timed out waiting after {int(timeout/1000)}s") 
        except Exception as ex:
            echo_error(f"Something went wrong while waiting for page {str(ex)}", raise_=True) 
        await browser.close()
    
    async def intercept_start(self, request, ignore_images):
        if not hasattr(request, "start_time"):
            request.start_time = datetime.utcnow()
        if ignore_images:
            u = request.url
            #covers only common types
            if (Browser.url_is_image(u)):
                await request.abort()
            else:
                await request.continue_()
        else:
            await request.continue_()
    
    async def intercept_end(self, request):
        if request.resourceType == Browser.XHR:
            url = request.url
            method = request.method
            headers = request.headers
            data = request.postData
            response = request.response
            if response:
                status_code = response.status
                response_obj = ""
                try:
                    response_obj = await response.text()
                    #if it is json, treat as json
                    try:
                        response_obj = json.loads(response_obj)
                    except:
                        pass
                except:
                    pass
                response_headers = response.headers
                is_cached = response.fromCache
            
            #capture elapsed time
            elapsed_time = 0
            if hasattr(request, "start_time"):
                end_time = datetime.utcnow()
                elapsed_time = (end_time - request.start_time).total_seconds() * 1000       #milliseconds
                elapsed_time = round(elapsed_time, 2)

            #build request object
            r = Request(url, method, headers, data, response_headers, status_code, response_obj, elapsed_time, is_cached)
            async with self._lock:
                self._requests.append(r)

    def get_page_options(self, timeout, wait_for):
        page_options = {}
        timeout_ = (int(timeout) * 1000) if timeout else Browser.DEFAULT_TIMEOUT
        page_options['timeout'] = timeout_
        if timeout and (not wait_for):
            return page_options
        wait_for = wait_for or [Browser.LOAD, Browser.NETWORK0]
        if not isinstance(wait_for, (list,tuple)):
            wait_for = [wait_for]
        for wait in wait_for:
            wait = Browser.guess_wait_for(wait)
            if wait:
                page_options['waitUntil'] = page_options.get('waitUntil', [])
                page_options['waitUntil'].append(wait)
        return page_options
  

class Request(object):
    def __init__(self, url, method, request_headers, request_body, response_headers, response_code, response_body, elapsed_time, is_cached):
        self.url = url
        self.method = method
        self.request_headers = request_headers or {}
        self.request_body = request_body
        self.response_headers = response_headers or {}
        self.response_code = response_code
        self.response_body = response_body
        self.elapsed_time = elapsed_time
        self.is_cached = is_cached
    
    def __repr__(self):
        return f"{self.method} - {self.url} - <Response code {self.response_code} returned in {self.elapsed_time} ms>"
    
    @property
    def header(self):
        d = self.to_dict()
        return list(d.keys())
    
    def to_dict(self):
        return self.__dict__.copy()