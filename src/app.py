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
import platform
import pytz

est_timezone = pytz.timezone('EST')

testing = True
test_file_html='test.html'

prev_alert_html = None
prev_alert_html_length = None
content_changed = False
length_changed = False
html = None

url = "https://www.ontario.ca/page/ontario-immigrant-nominee-program-oinp"

def check_diff():

    if not testing:

        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox') # Required when running as root user; otherwise there are "no sandbox" errors

        try:

            driver_file_name = ''
            if "Linux" in platform.platform(): driver_file_name = './drivers/chromedriver-v90-linux'
            elif "macOS" in platform.platform(): driver_file_name = './drivers/chromedriver-v90-mac'
            else:
                print("Cannot identify the current OS")
                sys.exit(-1)

            driver = webdriver.Chrome(driver_file_name, options=chrome_options, service_args=['--verbose', '--log-path=/tmp/chromedriver.log'])
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

        with open(test_file_html,'r') as file:
            html = file.read()

    soup = BeautifulSoup(html, "html.parser")
    alert_html_soup = soup.select('div.alert-box')
    try:
        alert_html = alert_html_soup[0]
    except IndexError as e:
        return {"content-changed": False, "length-changed": True, "html": f'There has been a change in the number of alert boxes in this page, which resulted in an error when parsing the site.<br><br>Error: {e}'}
    alert_html_length = len(alert_html_soup)

    global prev_alert_html
    global prev_alert_html_length
    
    # Check if either the contents or the number of alert boxes changed
    if ((hash(prev_alert_html) != hash(alert_html)) and (prev_alert_html)) or ((hash(prev_alert_html_length) != hash(alert_html)) and (prev_alert_html_length)):
        content_changed = True

    if (prev_alert_html_length != alert_html_length) and (prev_alert_html_length):
        length_changed = True
    
    else:
        content_changed = False
        length_changed = False
    
    prev_alert_html = alert_html
    
    message_html = alert_html
    if length_changed: message_html = f'There has been a change in the number of alert boxes in this page.'

    return {"content-changed": content_changed, "length-changed": length_changed, "html": message_html}

def send_email(html_alert_box):

    if Path('env.py').exists():
        
        from env import ENV
        
        try:
            recipient_emails_str = ', '.join(ENV['recipient']['emails'])
            if testing: recipient_emails_str = ENV['recipient']['emails'][0]
            print(f'Sending notification e-mail to: {recipient_emails_str}... ',end='')
        
        except Exception as e:
            print('\n', e)
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
            try:
                message.set_content(html_alert_box.get_text())
            except Exception as e:
                message.set_content(f'There was a problem setting the content for this message:<br>{e}')

            html_template = ''
            with open('template.html','r') as file: html_template = file.read()
            html_message = html_template.replace('[alert-box]', str(html_alert_box)).replace('[url]', url)

            message.add_alternative(html_message, subtype='html')

            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
                server.login(sender_email, password)
                server.send_message(message)

            print('Sent.')

        except Exception as e: print('\n', e)

    else: print('Unable to import env.py file. Won\'t send e-mail.')

def reset_settings():
    html = None
    content_changed = False
    length_changed = False

if __name__ == "__main__":

    if testing:
        print('\033[93m\033[1m' + ('-'*30) + '\n*** IN TESTING ENVIRONMENT ***\n' + ('-'*30))
        print(f'Using `{test_file_html}` as source of web-scrapping content\033[0m')
    
    start_date = est_timezone.localize(datetime(2021, 4, 22, 23, 50, 0)) # Apr 23, 2021 at 9 AM

    # seconds = 86400 # check every 24 hours
    seconds = 60 # check every minute

    print('Frequency: Every ', end='')
    if seconds < 60: print(f'{seconds} second(s)')
    elif (seconds/60) < 60: print(f'{int(seconds/60)} minutes(s)')
    else: print(f'{int(seconds/60/60)} hours(s)')

    print(f"Starting time: {format(start_date.strftime('%b %d, %Y at %I:%M %p %Z'))}\n")

    while True:

        now = est_timezone.localize(datetime.now())

        # Have not yet reached the start date
        if now <= start_date: time.sleep(60) # Try again in 60 seconds
        else:

            print(now.strftime('%b %d, %Y at %I:%M %p %Z'),': ', end='')

            res = check_diff()
            if res["length-changed"]:
                print(f'\033[91mThe number of alert boxes has changed\033[0m')
                send_email(res['html'])
                sys.exit(0)
            elif res["content-changed"]:
                print(f'\033[92mThere are content changes\033[0m')
                send_email(res['html'])
            else: print('No changes')

            reset_settings()

            time.sleep(seconds)