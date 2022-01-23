import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
import time

try:
    from user_config import username, password
except ImportError as error:
    print(error, "Make sure you've set the username and password variables in a file called user_config.py "
                 "in the root directory")
    quit()


def enter_search_conditions(driver, location_division, date):
    # Select Location
    select = Select(driver.find_element(By.ID, 'cboHSLocationGroup'))
    select.select_by_value(location_division[0])

    # Select Search Types
    select = Select(driver.find_element(By.ID, 'cboHSSearchBy'))
    select.select_by_value('Courtroom')

    # Select Courtroom
    select = Select(driver.find_element(By.ID, 'selHSCourtroom'))
    select.select_by_visible_text(location_division[1])

    # Search by Date From
    from_date = driver.find_element(By.ID, 'SearchCriteria_DateFrom')
    from_date.clear()
    from_date.send_keys(date.strftime('%m/%d/%Y'))

    # Search by Date To
    to_date = driver.find_element(By.ID, 'SearchCriteria_DateTo')
    to_date.clear()
    to_date.send_keys(date.strftime('%m/%d/%Y'))

    # submit form
    driver.find_element(By.ID, "btnHSSubmit").click()


def scrape_data(driver, location, date):
    # wait for data to load into table
    while 'No items to display' in driver.find_element(By.ID, 'hearingResultsGrid').text:
        time.sleep(1)

    parties = []
    charges = []

    pageCounter = 1

    last_page = int(driver.find_element(By.XPATH, "//a[@title='Go to the last page']").get_attribute('data-page'))

    while pageCounter <= last_page:
        # wait for data to load into table
        while 'No items to display' in driver.find_element(By.ID, 'hearingResultsGrid').text:
            time.sleep(1)

        # find the table body
        table = driver.find_element(By.ID, 'hearingResultsGrid').find_element(By.TAG_NAME, 'tbody')

        # grab all of the rows
        rows = table.find_elements(By.TAG_NAME, 'tr')

        for row in rows:
            # get case number
            case_number = row.find_element(By.TAG_NAME, 'a').get_attribute('title')

            # click into the case details
            row.find_element(By.TAG_NAME, 'a').click()

            # party info
            party_data = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'divPartyInformation_body')))

            # start a record for this case number
            party_info = {'Case Number': case_number, 'Judge': location[0], 'Courtroom': location[1],
                          'Hearing Date': date}

            # If there are multiple parties, get only defendant info.
            # This check is needed when parties include states or other bodies.
            party_divs = party_data.find_elements(By.XPATH, "*")
            for party_div in party_divs:
                if 'Defendant' in party_div.text:
                    # add the party info up to Race data, skip the rest
                    for data_section in party_div.find_elements(By.TAG_NAME, 'p')[:3]:
                        field = data_section.find_element(By.TAG_NAME, 'span').text
                        value = data_section.text.split('\n')[1]

                        party_info[field] = value

            parties.append(party_info)

            # Charges
            charge_div = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'chargeInformationDiv')))

            # get columns
            cols = charge_div.find_element(By.TAG_NAME, 'thead').text.split('\n')
            cols = [str.strip(i) for i in cols]
            cols.insert(0, 'Charge Number')

            for charge in charge_div.find_element(By.TAG_NAME, 'tbody').find_elements(By.CLASS_NAME, 'k-master-row'):
                charge_data = []
                for details in charge.find_elements(By.TAG_NAME, 'td'):
                    if len(details.text) > 0:
                        charge_data.append(details.text)

                charge_row = {'Case Number': case_number}
                for i in range(len(charge_data)):
                    charge_row[cols[i]] = charge_data[i]

                charges.append(charge_row)

            driver.find_element(By.ID, 'tcControllerLink_1').click()

        driver.find_element(By.XPATH, "//a[@title='Go to the next page']").click()

        pageCounter += 1

    # navigate back to search hearings page
    driver.find_element(By.ID, 'tcControllerLink_0').click()

    return pd.DataFrame.from_records(parties), pd.DataFrame.from_records(charges)


while __name__ == '__main__':
    # --- define search conditions ---
    location_division = [('Division I - Judge Paula Skahan', 'Division 1'),
                         ('Division IX - Judge W. Mark Ward', 'Division 9')]

    dates = pd.date_range(start='01/10/2022', end='01/14/2022')

    # url to the Shelby County CJS portal
    url = "https://cjs.shelbycountytn.gov/CJS/Account/Login"

    # instantiate chrome webdriver and load the url
    s = Service('C:\webdrivers\chromedriver.exe')
    driver = webdriver.Chrome(service=s)
    driver.get(url)

    # input user credentials
    username_input = driver.find_element(By.ID, 'UserName')
    username_input.clear()
    username_input.send_keys(username)

    password_input = driver.find_element(By.ID, 'Password')
    password_input.clear()
    password_input.send_keys(password)

    # navigate to hearings page
    driver.find_element(By.CSS_SELECTOR, "button.btn-primary").click()
    driver.find_element(By.ID, "portlet-26").click()

    party_dfs = []
    charges_dfs = []

    for location in location_division:
        for date in dates:
            print(f'Currently processing {location} on {date}.')

            enter_search_conditions(driver, location, date)

            parties, charges = scrape_data(driver, location, date)

            party_dfs.append(parties)
            charges_dfs.append(charges)

    party_df = pd.concat(party_dfs, ignore_index=True)
    charges_df = pd.concat(charges_dfs, ignore_index=True)

    try:
        party_df.to_csv('data/party_data.csv')
        charges_df.to_csv('data/charges_data.csv')

        print('Data successfullly saved to /data')

    except:
        print('Data could not be written. Check file access.')

    quit()
