import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import requests
import json
import re
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urljoin

# Configure Chrome options
chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

# Automatic ChromeDriver management
service = Service(ChromeDriverManager().install())

# Initialize WebDriver
driver = webdriver.Chrome(service=service, options=chrome_options)

# Ensure downloads directory exists
if not os.path.exists('downloads'):
    os.makedirs('downloads')

# Credentials
username = os.getenv('USERNAME')
password = os.getenv('PASSWORD')
login_url = 'https://fatal5.com/account/login'
target_url = 'https://fatal5.com/search/index'

if not username or not password:
    print("Error: Set USERNAME and PASSWORD as environment variables.")
    driver.quit()
    exit()

# --------------------------
# Enhanced Login Flow
# --------------------------
try:
    print("Initiating login sequence...")
    driver.get(login_url)
    
    # Wait for form elements with extended timeout
    WebDriverWait(driver, 20).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#Email, #Password, input[type='submit']"))
    )

    # Fill credentials
    driver.find_element(By.ID, "Email").send_keys('biraj.mukherjee@maersk.com')
    driver.find_element(By.ID, "Password").send_keys('Submarineisland2023!')
    
    # Click submit button using corrected selector
    submit_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
    submit_button.click()

    # Verify login through dashboard element
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, ".dashboard-header, .logout-link"))
    )
    print("Login credentials validated!")

    # Explicit navigation to target page
    print("Navigating to search interface...")
    driver.get(target_url)
    
    # Final verification using combined checks
    WebDriverWait(driver, 15).until(
        lambda d: "search/index" in d.current_url.lower() or 
        EC.presence_of_element_located((By.CSS_SELECTOR, ".search-results-table"))(d)
    )
    print(f"Successfully reached target URL: {driver.current_url}")

except Exception as e:
    print(f"Login/navigation failed: {str(e)}")
    print("Current URL:", driver.current_url)
    
    # Attempt recovery if on wrong page
    if "incident/index" in driver.current_url:
        print("Detected incident page - attempting direct navigation...")
        try:
            driver.get(target_url)
            WebDriverWait(driver, 10).until(EC.url_contains("/search/index"))
            print("Recovery successful!")
        except Exception as recovery_error:
            print(f"Recovery failed: {str(recovery_error)}")
            driver.save_screenshot("recovery_error.png")
            driver.quit()
            exit()
    else:
        driver.save_screenshot("login_error.png")
        driver.quit()
        exit()

# --------------------------
# Robust Cookie Transfer
# --------------------------
try:
    print("Validating WebDriver connection...")
    # Active connection check
    driver.current_url  
    
    print("Transferring session cookies...")
    session = requests.Session()
    selenium_cookies = driver.get_cookies()
    
    # Set cookies with domain validation
    for cookie in selenium_cookies:
        session.cookies.set(
            name=cookie['name'],
            value=cookie['value'],
            domain=cookie.get('domain') or '.fatal5.com'  # Fallback domain
        )
        
except Exception as e:
    print(f"Cookie transfer failed: {str(e)}")
    print("Attempting recovery...")
    
    try:
        if driver.service.process.pid:
            print("Refreshing session...")
            driver.refresh()
            selenium_cookies = driver.get_cookies()
    except:
        print("Critical connection failure - please restart script")
        driver.quit()
        exit()

finally:
    if driver:
        driver.quit()
        print("WebDriver terminated cleanly")

# --------------------------
# Configure Retry Mechanism
# --------------------------
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount('https://', adapter)
session.mount('http://', adapter)

# --------------------------
# Scraping Logic
# --------------------------
base_url = 'https://fatal5.com/search/index'
current_url = base_url
all_data = []
max_pages = 20  # Safety limit to prevent infinite loops
page_count = 0

while current_url and page_count < max_pages:
    print(f"Scraping page {page_count + 1}: {current_url}")
    try:
        # Convert to absolute URL if needed
        if not current_url.startswith(('http://', 'https://')):
            current_url = urljoin(base_url, current_url)
            
        response = session.get(current_url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract table data
        table = soup.find('table', class_='table main table-condensed table-bordered table-hover')
        if not table:
            print("Table not found")
            break
        
        rows = table.find('tbody').find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 8:
                continue
            
            # Extract data from cells
            filename_link = cells[0].find('a')
            filename = filename_link.text.strip()
            relative_file_url = filename_link['href']
            
            # Fix URL formatting
            file_url = urljoin(base_url, relative_file_url)
            
            # Initialize variables before try block
            local_filename = None
            upload_status = 'not attempted'
            
            # Download file with error handling
            try:
                file_response = session.get(file_url, timeout=10)
                upload_status = 'download failed'  # Default status
                
                if file_response.status_code == 200:
                    content_disposition = file_response.headers.get('Content-Disposition', '')
                    filename_match = re.findall(r'filename="?(.+\.pdf)"?', content_disposition)
                    filename_to_use = filename_match[0] if filename_match else f"{filename}.pdf"
                    local_filename = os.path.join('downloads', filename_to_use)
                    
                    with open(local_filename, 'wb') as f:
                        f.write(file_response.content)
                    upload_status = 'success'
                    
            except Exception as file_error:
                print(f"File download failed: {str(file_error)}")
                upload_status = f'error: {str(file_error)}'
            
            # Store data with guaranteed initialized variables
            all_data.append({
                'filename': filename,
                'file_url': file_url,
                'local_path': local_filename or 'N/A',
                'upload_status': upload_status,
                'metadata': {
                    'fatal5': cells[1].text.strip(),
                    'activity': cells[2].text.strip(),
                    'equipment': cells[3].text.strip(),
                    'body_part': cells[4].text.strip(),
                    'injury': cells[5].text.strip(),
                    'area': cells[6].text.strip(),
                    'country': cells[7].text.strip()
                }
            })

        # Improved pagination handling
        next_link = soup.find('a', text=lambda t: t and 'Next' in t)
        if next_link:
            # Get absolute URL for next page
            relative_next = next_link.get('href')
            new_url = urljoin(base_url, relative_next)
            
            # Prevent infinite loop check
            if new_url == current_url:
                print("Reached duplicate page, stopping pagination")
                break
                
            current_url = new_url
            page_count += 1
            time.sleep(1.5)
        else:
            current_url = None  # Exit condition

    except Exception as e:
        print(f"Error during page {page_count + 1}: {str(e)}")
        break

# Save all data to JSON file
json_file = 'learning_packs.json'
with open(json_file, 'w') as f:
    json.dump(all_data, f, indent=4)

print(f"Completed scraping {page_count} pages")