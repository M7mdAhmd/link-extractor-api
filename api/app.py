from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import traceback
import logging
import threading
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

driver = None
driver_lock = threading.Lock()

def initialize_driver():
    global driver
    if driver is None:
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.binary_location = "/usr/bin/google-chrome-stable"
        
        try:
            service = Service(executable_path="/usr/bin/chromedriver")
            driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("Chrome WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Chrome WebDriver: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    return driver

def get_final_url(driver, initial_url):
    try:
        logger.info(f"Getting final URL for: {initial_url}")
        driver.get(initial_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        final_url = driver.current_url
        logger.info(f"Final URL resolved to: {final_url}")
        return final_url
    except Exception as e:
        logger.error(f"Error getting final URL for {initial_url}: {str(e)}")
        return initial_url

def extract_links(driver, url):
    try:
        logger.info(f"Attempting to load URL: {url}")
        driver.get(url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        soup = BeautifulSoup(driver.page_source, "lxml")
        links = soup.find_all("a", {"class": "go-link propper-link popper ico-btn"})
        if not links:
            links = soup.find_all("a", {"class": "go-link"})
        if not links:
            raise Exception("No links found on the page. Please verify the URL contains the expected content.")
        
        extracted_links = []
        base_url = "https://www.primewire.tf"
        for link in links:
            href = link.get('href')
            if href:
                initial_url = urljoin(base_url, href)
                final_url = get_final_url(driver, initial_url)
                extracted_links.append({
                    "initial": initial_url,
                    "final": final_url
                })
        return extracted_links
    except Exception as e:
        logger.error(f"Error in extract_links: {str(e)}")
        logger.error(traceback.format_exc())
        raise

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "API is running successfully!",
        "endpoints": {
            "/extract": "POST - Extract links from a URL"
        },
        "message": "This API is running with Selenium and Chrome in a Docker container on Railway"
    })

@app.route('/extract', methods=['POST'])
def extract():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({"error": "URL is required"}), 400
        if not url.startswith(('http://', 'https://')):
            return jsonify({"error": "Invalid URL. Please include http:// or https://"}), 400
        
        logger.info(f"Received request to extract links from: {url}")
        with driver_lock:
            driver = initialize_driver()
            try:
                links = extract_links(driver, url)
                if not links:
                    return jsonify({"error": "No links found on the page. Please verify the URL contains the expected content."}), 404
                return jsonify({"links": links})
            except Exception as e:
                logger.error(f"Error during extraction: {str(e)}")
                return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)