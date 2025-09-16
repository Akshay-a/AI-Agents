from playwright.sync_api import sync_playwright

def get_html(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        print("Full page HTML:", page.content())
        job_listings = page.query_selector_all('div.kabgy40[data-search-sol-meta]')
        html_parts = [el.inner_html() for el in job_listings]
        html = ''.join(html_parts)
        browser.close()

print(get_html("https://www.seek.com.au/"))