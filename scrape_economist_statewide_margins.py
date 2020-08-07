"""Scrape Presidential Projected Margins for Each State from Economist.

Note that we have to use selenium because the Economist made their webpage
load dynamically. Therefore, we have to pull up the site and scroll through
it rather than a simple urllib request. Otherwise, the html does not load
the projected marings"""
import pandas as pd
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from datetime import datetime
from selenium.webdriver.common.keys import Keys


def main():
    """Scrape."""
    # Set base url
    base_url = 'https://projects.economist.com/us-2020-forecast/president/'

    # Pulls states dict
    states = states_dict()

    # Initialize dataframe we'll ave
    df = pd.DataFrame(columns=['state', 'biden', 'trump', 'state_full'])

    # Open up chrome
    driver = webdriver.Chrome()

    # Pull margin for each state
    for state, state_full in states.items():
        # Display progress
        print(state)

        # Use selenium to pull up the web page
        driver.get(base_url + state_full)

        # Random stack overflow code to scroll through website
        heights = []
        script_text = 'return document.body.scrollHeight'
        for i in range(1, 500):
            bg = driver.find_element_by_css_selector('body')
            time.sleep(0.1)
            bg.send_keys(Keys.END)
            heights.append(driver.execute_script(script_text))
            try:
                bottom = heights[i - 16]
            except:
                pass
            if i % 16 == 0:
                new_bottom = heights[i - 1]
                if bottom == new_bottom:
                    break

        # Extract soup
        soup = BeautifulSoup(driver.page_source, 'lxml')

        # Get html for each candidates margin (not in particular order)
        candidate1 = soup.findAll('g', {'class': 'g-text'})[0]
        candidate2 = soup.findAll('g', {'class': 'g-text'})[1]

        # Get candidate support
        support1 = float(candidate1.text.split('%')[0])
        support2 = float(candidate2.text.split('%')[0])

        # Add state to dataframe
        r = len(df)
        df.at[r, 'state'] = state
        df.at[r, 'state_full'] = state_full

        # Determine if Biden is candidate 1 or 2 and add to dataframe
        if 'fill="#2e3c85"' in str(candidate1):
            df.at[r, 'biden'] = support1
            df.at[r, 'trump'] = support2
        else:
            df.at[r, 'biden'] = support2
            df.at[r, 'trump'] = support1

    # Add margin
    df['margin'] = df['biden'] - df['trump']

    # Get today's date
    today = datetime.today()
    stamp = str(today.month).zfill(2) + '_' + str(today.day).zfill(2)

    # Save to drive
    path = 'economist_projected_margins_' + stamp + '.csv'
    df.to_csv(path, index=False)


def states_dict():
    """Return dictionary of state abbreviation mapping to Economist name."""
    states = {}
    states['AL'] = 'alabama'
    states['AK'] = 'alaska'
    states['AZ'] = 'arizona'
    states['AR'] = 'arkansas'
    states['CA'] = 'california'
    states['CO'] = 'colorado'
    states['CT'] = 'connecticut'
    states['DE'] = 'delaware'
    states['FL'] = 'florida'
    states['GA'] = 'georgia'
    states['HI'] = 'hawaii'
    states['ID'] = 'idaho'
    states['IL'] = 'illinois'
    states['IN'] = 'indiana'
    states['IA'] = 'iowa'
    states['KS'] = 'kansas'
    states['KY'] = 'kentucky'
    states['LA'] = 'louisiana'
    states['ME'] = 'maine'
    states['MD'] = 'maryland'
    states['MA'] = 'massachusetts'
    states['MI'] = 'michigan'
    states['MN'] = 'minnesota'
    states['MS'] = 'mississippi'
    states['MO'] = 'missouri'
    states['MT'] = 'montana'
    states['NE'] = 'nebraska'
    states['NV'] = 'nevada'
    states['NH'] = 'new-hampshire'
    states['NJ'] = 'new-jersey'
    states['NM'] = 'new-mexico'
    states['NY'] = 'new-york'
    states['NC'] = 'north-carolina'
    states['ND'] = 'north-dakota'
    states['OH'] = 'ohio'
    states['OK'] = 'oklahoma'
    states['OR'] = 'oregon'
    states['PA'] = 'pennsylvania'
    states['RI'] = 'rhode-island'
    states['SC'] = 'south-carolina'
    states['SD'] = 'south-dakota'
    states['TN'] = 'tennessee'
    states['TX'] = 'texas'
    states['UT'] = 'utah'
    states['VT'] = 'vermont'
    states['VA'] = 'virginia'
    states['WA'] = 'washington'
    states['WV'] = 'west-virginia'
    states['WI'] = 'wisconsin'
    states['WY'] = 'wyoming'
    return states


if __name__ == "__main__":
    main()
