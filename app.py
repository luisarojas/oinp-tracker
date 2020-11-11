from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

from pathlib import Path
from datetime import datetime, timedelta
from email.message import EmailMessage
import time
import sys
import smtplib
import ssl
import socket

testing = False

prev_alert_html = None
changed = False
html = None

url = "https://www.ontario.ca/page/ontario-immigrant-nominee-program-oinp"

def check_diff():

    if not testing:

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox') # Required when running as root user; otherwise there are "no sandbox" errors

        try:

            driver = webdriver.Chrome('./drivers/chromedriver-linux', options=chrome_options, service_args=['--verbose', '--log-path=/tmp/chromedriver.log'])
            driver.get(url)

            # Wait for a maximum of 10 seconds for an element matching the given criteria to be found
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'alert-box'))
            )

            html = driver.page_source

        finally:
            driver.close()
            driver.quit()
    else:

        with open('test.html','r') as file:
            html = file.read()

    soup = BeautifulSoup(html, "html.parser") 
    alert_html = soup.select('div.alert-box')[1]

    global prev_alert_html
    if (hash(prev_alert_html) != hash(alert_html)) and (prev_alert_html): changed = True
    else: changed = False
    
    prev_alert_html = alert_html
    return {"changed": changed, "html": alert_html}

def send_email(html_alert_box):

    if Path('env.py').exists():
        
        from env import ENV
        
        try:
            recipient_emails_str = ', '.join(ENV['recipient']['emails'])
            if testing: recipient_emails_str = ENV['recipient']['emails'][0]
            print(f'\033[92mThere are changes\033[0m. Sending notification e-mail to: {recipient_emails_str}')
        
        except Exception as e:
            print(e)
            print('Error: Unable to properly read recipient emails from env.py file')
            sys.exit(-1)
        
        try:

            port = 465  # For SSL
            smtp_server = "smtp.gmail.com"
            sender_email = ENV['sender']['email']
            password = ENV['sender']['password']

            subject = '🆕 OINP Update'
            if testing: subject += ' - Test'

            message = EmailMessage()
            message['Subject'] = subject
            message['From'] = sender_email
            message['To'] = recipient_emails_str
            message.set_content(html_alert_box.get_text())

            html_template = ''
            with open('template.html','r') as file: html_template = file.read()
            html_message = html_template.replace('[alert-box]', str(html_alert_box)).replace('[url]', url)

            message.add_alternative(html_message, subtype='html')

            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
                server.login(sender_email, password)
                server.send_message(message)

        except Exception as e: print(e)

def reset_settings():
    html = None
    changed = False

if __name__ == "__main__":

    if testing: print('\033[93m\033[1m' + ('-'*30) + '\n*** IN TESTING ENVIRONMENT ***\n' + ('-'*30) + '\033[0m')
    
    seconds = 3600 # check every hour until next_start; then, check every 24 hours
    next_start = datetime(2020, 11, 11, 9, 0, 0) # Nov 11, 2020 at 9 AM

    print(f'Checking every {int(seconds/60)} minutes\n')

    while True:

        now = datetime.now() - timedelta(hours=5) # Digital Ocean server is on +5 timezone
        print(now.strftime('%b %d, %Y at %I:%M %p'),': ', end='')

        if (now >= next_start): seconds = 86400

        res = check_diff()
        if res["changed"] or testing: send_email(res["html"])
        else: print('No changes')

        reset_settings()
        
        input()
        time.sleep(seconds)