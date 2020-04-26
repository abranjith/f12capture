import os
import json
import click

from browser import Browser
from click_helper import echo_warning, echo_success, echo_error
from utils import guess_filename_from_url, write_to_csv

@click.command()
@click.option("--url", "-u", type=click.STRING, required=True, help="Valid URL for invoking in Chromium browser")
@click.option("--timeout", "-t", type=click.INT, help="Timeout in seconds. Default is 1 minute")
@click.option("--wait-for", "-w", type=click.STRING, multiple=True, help="Wait for this event to finish or timeout whichever happens first. Valid ones are load, domcontentloaded, networkidle0/idle2. Partial texts allowed (eg: net0, dom)")
@click.option("--include-domain", "-id", type=click.STRING, help="Includes only this domain")
@click.option("--exclude-domain", "-ed", type=click.STRING, help="Everything except this domain")
@click.option("--url-contains", "-uc", type=click.STRING, help="Includes URLs that contain this text in path (case insensitive)")
@click.option("--url-not-contains", "-unc", type=click.STRING, help="Excludes URLs that contain this text in path (case insensitive)")
@click.option("--url-endswith", "-ue", type=click.STRING, help="Includes URLs that end with this text in path (case insensitive)")
@click.option("--url-not-endswith", "-une", type=click.STRING, help="Excludes URLs that end with this text in path (case insensitive)")
@click.option("--ignore-redirect", "-ir", is_flag=True , default=False, help="Excludes redirected URLs")
@click.option("--ignore-images", "-ii", type=click.STRING, help="Excludes image URLs (best guess)")
@click.option("--output", "-o", type=click.Path(exists=True), help="Directory to place results")
@click.option("--fmt", "-f", type=click.Choice(["csv", "json"], case_sensitive=False), default="csv", help="Format of output file")
def cli(url, timeout, wait_for, include_domain, exclude_domain, url_contains, url_not_contains,
        url_endswith, url_not_endswith, ignore_redirect, ignore_images, output, fmt):
    url = ensure_valid_url(url)
    b = Browser(url)
    results = b.capture_xhr(timeout, wait_for, ignore_images)
    results = b.filter_requests(results, include_domain, exclude_domain, url_contains, url_not_contains,
        url_endswith, url_not_endswith, ignore_redirect)
    if not results:
        echo_warning("No XHR requests found for the given criteria")
        return
    file_path = None
    if output:
        dict_records = [r.to_dict() for r in results]
        fmt = fmt.lower() if fmt else "csv"
        filename = guess_filename_from_url(url, ext=fmt)
        file_path = os.path.join(output, filename)
        if fmt == "json":
            with open(file_path, "w") as fd:
                json.dump(dict_records, fd, indent=4)
        else:       #csv
            header = results[0].header
            write_to_csv(file_path, header, dict_records)

    for r in results:
        click.echo()
        click.echo(r)
    
    if file_path:
        if os.path.isfile(file_path):
            echo_success(f"File {file_path} created with results")

def ensure_valid_url(url):
    #urlparse recognizes a netloc only if it is properly introduced by ‘//
    url = url or ""
    u = Browser.get_url_parts(url.strip())
    if not u.scheme and not url.startswith("//"):
        url =  "//" + url
    u = Browser.get_url_parts(url.strip())
    if not u.netloc:
        echo_error(f"url {url} is not a valid url as host (domain) couldn't be determined", raise_=True)
    #default scheme as chromium doesn't seem to prefix in case of missing scheme
    if not u.scheme:
        u = u._replace(scheme="http")
    return u.geturl()
