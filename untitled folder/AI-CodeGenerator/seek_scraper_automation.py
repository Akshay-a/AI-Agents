import csv
import time
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urljoin

# --- Configuration ---
SEARCH_URL = "https://www.seek.com.au"
SEARCH_TERM = "AI engineer"
OUTPUT_CSV = "ai_jobs.csv"
MAX_JOBS_TO_SCRAPE = 10
# Timeouts (milliseconds)
GOTO_TIMEOUT = 70000
ACTION_TIMEOUT = 25000
# *** INCREASED DESCRIPTION TIMEOUT SIGNIFICANTLY ***
DESCRIPTION_WAIT_TIMEOUT = 60000 # Now 60 seconds
ELEMENT_WAIT_TIMEOUT = 10000
CLOUDFLARE_TIMEOUT = 15000
CLOUDFLARE_WAIT_AFTER_CLICK = 30000

# --- Selectors (Keep potentially flexible selectors) ---
KEYWORDS_INPUT_SELECTOR = 'input[data-testid="keywords-input"], input#keywords-input'
SEARCH_BUTTON_SELECTOR = 'button[data-automation="searchButton"]'
JOB_LIST_SELECTOR = 'div[data-testid="job-search-results"]'
JOB_CARD_SELECTOR = 'article[data-automation="normalJob"]'
# This is the one failing - double-check this selector manually on the failing URL if timeout increase doesn't work
DESCRIPTION_SELECTOR = 'div[data-automation="jobDescription"]'

# --- Helper Functions (Keep as before) ---
def clean_text(text): # ... (no change)
    if text: return text.strip().replace('\n', ' ').replace('\r', '')
    return "N/A"
def extract_experience(description): # ... (no change)
    matches = re.findall(r'(\d+(?:-\d+)?\+?)\s+years?', description, re.IGNORECASE)
    if matches: return ", ".join(matches) + " years experience"
    if re.search(r'senior|lead', description, re.IGNORECASE): return "Senior level likely"
    if re.search(r'junior|graduate', description, re.IGNORECASE): return "Junior level likely"
    return "N/A"
def extract_tech_stack(description): # ... (no change)
    tech_keywords = ['Python','Java','C++','JavaScript','React','Angular','Vue','SQL','NoSQL','MongoDB','PostgreSQL','MySQL','AWS','Azure','GCP','Docker','Kubernetes','TensorFlow','PyTorch','scikit-learn','Keras','Pandas','NumPy','Spacy','NLTK','LLM','LangChain','NLP','Computer Vision','Machine Learning','Deep Learning','Data Science','AI']
    found_tech = []
    desc_lower = description.lower()
    for tech in tech_keywords:
        pattern = r'\b' + re.escape(tech) + r'(?:s|\b|[\.,\(\)!])'
        if re.search(pattern, desc_lower, re.IGNORECASE): found_tech.append(tech)
    unique_tech = sorted(list(set(found_tech)))
    return ", ".join(unique_tech) if unique_tech else "N/A"
# --- Cloudflare Helper (Keep as before) ---
def handle_cloudflare_challenge(page, expected_element_after_success): # ... (no change)
    iframe_selectors = ['iframe[title="Widget containing a Cloudflare security challenge"]', 'iframe[src*="challenges.cloudflare.com"]', 'iframe[title*="Cloudflare"]']
    checkbox_selectors = ['input[type="checkbox"]', 'span.mark', '#cf-stage-managed-challenge-trigger', 'label:has-text("Verify you are human")']
    detected = False
    for iframe_selector in iframe_selectors:
        try:
            print(f"  Checking for Cloudflare iframe: {iframe_selector}")
            frame_handle = page.frame_locator(iframe_selector).first
            frame_handle.locator(checkbox_selectors[0]).wait_for(state="visible", timeout=CLOUDFLARE_TIMEOUT / 2)
            print("  Cloudflare challenge iframe detected.")
            detected = True
            clicked = False
            for cb_selector in checkbox_selectors:
                try:
                    print(f"    Attempting click: {cb_selector}")
                    frame_handle.locator(cb_selector).first.click(timeout=CLOUDFLARE_TIMEOUT / 2)
                    print("    Checkbox clicked.")
                    clicked = True; break
                except PlaywrightTimeoutError: pass
                except Exception as click_err: print(f"    Error clicking checkbox ({cb_selector}): {click_err}")
            if clicked:
                print(f"  Waiting after CF click (expecting: {expected_element_after_success})...")
                page.wait_for_selector(expected_element_after_success, state="visible", timeout=CLOUDFLARE_WAIT_AFTER_CLICK)
                print("  Cloudflare challenge likely passed.")
                time.sleep(2); return True
            else: print("  Could not click checkbox."); return False
        except PlaywrightTimeoutError: print(f"  Iframe/checkbox ({iframe_selector}) not found quickly.")
        except Exception as e: print(f"  Error checking CF iframe ({iframe_selector}): {e}")
    if not detected: print("  No Cloudflare challenge detected.")
    return detected
# --- End Cloudflare Helper ---

def scrape_seek():
    all_jobs_data = []
    with sync_playwright() as p:
        print("Launching browser...")
        # *** IMPORTANT: Use headless=False for debugging this timeout issue ***
        # browser = p.chromium.launch(headless=False)
        browser = p.chromium.launch(headless=True) # Change to False if timeout persists
        context = browser.new_context( user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36')
        context.set_default_timeout(ACTION_TIMEOUT)
        page = context.new_page()

        try:
            # --- Initial navigation and search (Keep as before) ---
            print(f"Navigating main tab to {SEARCH_URL}...")
            page.goto(SEARCH_URL, timeout=GOTO_TIMEOUT, wait_until='domcontentloaded')
            print("Initial navigation complete. Handling potential Cloudflare challenge...")
            handle_cloudflare_challenge(page, KEYWORDS_INPUT_SELECTOR)

            print("Waiting for keywords input field...")
            try:
                page.wait_for_selector(KEYWORDS_INPUT_SELECTOR, state="visible", timeout=ACTION_TIMEOUT)
                page.locator(KEYWORDS_INPUT_SELECTOR).first.fill(SEARCH_TERM)
            except PlaywrightTimeoutError:
                print(f"Error: Keywords input not visible.")
                page.screenshot(path="screenshot_error_keywords_input.png"); context.close(); browser.close(); return []

            print("Locating and clicking search button...")
            try:
                page.wait_for_selector(SEARCH_BUTTON_SELECTOR, state="visible", timeout=ACTION_TIMEOUT)
                page.locator(SEARCH_BUTTON_SELECTOR).click()
            except PlaywrightTimeoutError:
                print(f"Error: Search button not visible/clickable.")
                page.screenshot(path="screenshot_error_search_button.png"); context.close(); browser.close(); return []

            print("Waiting for search results...")
            try:
                page.wait_for_selector(f"{JOB_LIST_SELECTOR}, {JOB_CARD_SELECTOR}", state="visible", timeout=ACTION_TIMEOUT * 1.5)
            except PlaywrightTimeoutError:
                print(f"Error: Could not find job list/cards.")
                page.screenshot(path="screenshot_error_job_results.png"); context.close(); browser.close(); return []
            print("Search results loaded.")
            # --- End Initial Setup ---

            # --- Job Card Processing Loop ---
            job_cards = page.locator(JOB_CARD_SELECTOR)
            count = job_cards.count()
            print(f"Found {count} job card elements.")

            jobs_processed = 0
            for i in range(count):
                # ... (Job limit check) ...
                if MAX_JOBS_TO_SCRAPE is not None and jobs_processed >= MAX_JOBS_TO_SCRAPE: break

                print(f"\n--- Processing Job Card Index {i} (User count: {jobs_processed + 1}) ---")
                job_card = job_cards.nth(i)
                job_data = { # Initialize dict
                     "title": "N/A", "company": "N/A", "location": "N/A", "salary": "N/A",
                     "posted_date": "N/A", "experience": "N/A", "description_summary": "N/A", "url": "N/A"
                }
                job_url = None

                try:
                    # --- Extract basic info + URL from main page (Keep as before) ---
                    title_locator = job_card.locator('a[data-automation="jobTitle"]')
                    job_data["title"] = clean_text(title_locator.text_content(timeout=ELEMENT_WAIT_TIMEOUT))
                    href = title_locator.get_attribute('href', timeout=ELEMENT_WAIT_TIMEOUT)
                    if href: job_url = urljoin(SEARCH_URL, href); job_data["url"] = job_url
                    # ... (Extract company, location, salary, date - keep using .first for location) ...
                    company_locator = job_card.locator('a[data-automation="jobCompany"]')
                    job_data["company"] = clean_text(company_locator.text_content(timeout=ELEMENT_WAIT_TIMEOUT))
                    location_locator = job_card.locator('a[data-automation="jobLocation"]')
                    job_data["location"] = clean_text(location_locator.first.text_content(timeout=ELEMENT_WAIT_TIMEOUT))
                    try: # Salary
                        salary_locator = job_card.locator('span[data-automation="jobSalary"]')
                        if salary_locator.is_visible(timeout=1500): job_data["salary"] = clean_text(salary_locator.text_content())
                    except PlaywrightTimeoutError: pass
                    try: # Date
                        date_locator = job_card.locator('span[data-automation="jobListingDate"]')
                        if date_locator.is_visible(timeout=1500): job_data["posted_date"] = clean_text(date_locator.text_content())
                    except PlaywrightTimeoutError: pass

                    print(f"  Title: {job_data['title']}")
                    print(f"  URL: {job_url}")

                except Exception as e:
                    print(f"  Error extracting basic info for job card index {i}: {e}")
                    continue

                # --- Open New Tab and Scrape Description ---
                if job_url:
                    new_page = None
                    try:
                        print(f"  Opening new tab for: {job_url}")
                        new_page = context.new_page()
                        new_page.goto(job_url, timeout=GOTO_TIMEOUT, wait_until='domcontentloaded')
                        print("  New tab navigation initiated. Handling potential Cloudflare challenge...")
                        # CF check might not be needed here if previous log showed normal page, but keep for robustness
                        handle_cloudflare_challenge(new_page, DESCRIPTION_SELECTOR)

                        # *** INCREASED TIMEOUT IS APPLIED HERE ***
                        print(f"  Waiting for description '{DESCRIPTION_SELECTOR}' (up to {DESCRIPTION_WAIT_TIMEOUT}ms)...")
                        # Wait again after CF check, using the increased timeout
                        new_page.wait_for_selector(DESCRIPTION_SELECTOR, state="visible", timeout=DESCRIPTION_WAIT_TIMEOUT)
                        print("  Description container found in new tab.")

                        description_element = new_page.locator(DESCRIPTION_SELECTOR)
                        full_description = clean_text(description_element.inner_text(timeout=ELEMENT_WAIT_TIMEOUT)) # Reading text should be fast

                        job_data["experience"] = extract_experience(full_description)
                        tech_stack = extract_tech_stack(full_description)
                        job_data["description_summary"] = f"Tech Stack: {tech_stack}\n\nDescription:\n{full_description}"

                        print(f"  Experience Guessed: {job_data['experience']}")
                        print(f"  Tech Stack Found: {tech_stack}")

                    except PlaywrightTimeoutError as e:
                        # Make error message clearer about what failed
                        print(f"  Timeout error ({DESCRIPTION_WAIT_TIMEOUT}ms) occurred in new tab for job index {i} ({job_url}).")
                        print(f"  Specific step failed: Waiting for description selector '{DESCRIPTION_SELECTOR}' to be visible.")
                        # print(f"  Error details: {e}") # Uncomment for full trace
                        job_data["description_summary"] = f"Error fetching description from new tab ({job_url}). Timeout waiting for selector: {DESCRIPTION_SELECTOR}"
                        if new_page:
                            try: new_page.screenshot(path=f"screenshot_error_new_tab_job_idx_{i}.png"); print(f"  Screenshot saved.")
                            except Exception as img_err: print(f"Could not save screenshot: {img_err}")
                    except Exception as e:
                         print(f"  Unexpected error processing new tab for job index {i} ({job_url}): {e}")
                         job_data["description_summary"] = f"Unexpected Error processing new tab ({job_url})."
                    finally:
                        if new_page: new_page.close()
                else:
                    job_data["description_summary"] = "URL not found on search results page."

                all_jobs_data.append(job_data)
                jobs_processed += 1
                time.sleep(0.7)

            # --- End Job Card Loop ---

        # --- General Error Handling & Cleanup (Keep as before) ---
        except Exception as e:
             print(f"An unexpected error occurred during automation: {e}")
             try:
                 if 'page' in locals() and page.is_closed() == False : page.screenshot(path="screenshot_error_unexpected.png"); print("Screenshot saved.")
             except Exception as img_err: print(f"Could not save screenshot: {img_err}")
        finally:
            print("Closing browser context and browser...")
            if 'context' in locals(): context.close()
            if 'browser' in locals() and browser.is_connected(): browser.close()

    return all_jobs_data

# --- save_to_csv Function (Keep as before) ---
def save_to_csv(data): # ... (no change)
    if not data: print("No data collected, skipping CSV write."); return
    print(f"Saving data to {OUTPUT_CSV}...")
    headers = ["Job Title", "Company", "Location", "Salary", "Experience Required", "Posted Date"]
    try:
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            for job in data:
                row1 = [job.get("title", "N/A"), job.get("company", "N/A"), job.get("location", "N/A"), job.get("salary", "N/A"), job.get("experience", "N/A"), job.get("posted_date", "N/A")]
                writer.writerow(row1)
                row2 = [job.get("description_summary", "N/A")] + [''] * (len(headers) - 1)
                writer.writerow(row2)
        print(f"Successfully saved {len(data)} jobs to {OUTPUT_CSV}")
    except IOError as e: print(f"Error writing to CSV file {OUTPUT_CSV}: {e}")
    except Exception as e: print(f"An unexpected error occurred during CSV writing: {e}")
# --- End save_to_csv ---


# --- Main Execution ---
if __name__ == "__main__":
    job_data = scrape_seek()
    save_to_csv(job_data)