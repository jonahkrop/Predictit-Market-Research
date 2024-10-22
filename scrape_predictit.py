import pandas as pd
import numpy as np
import re
import os
import sys

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium import common
from datetime import datetime, timedelta
from webdriver_manager.chrome import ChromeDriverManager
from PIL import ImageColor
from time import sleep

'''
Go to a predictit market website based on the state, election type, and
district (where applicable). Choose a time frame for which to download
and clean up a .csv including prices and trade volumes for each party.

'''


def main(url, save_name, date_range):
    ''' Turn a Predicit.com market into a .csv of pricing & trading info.

    Take a url and date range, and download a .csv of prices and trading
    volume for the relevant predictit.com market. Also, clean up the .csv
    a little bit, rename it, and deposit it in my projects folder.

    '''

    market_name = download_market(url, date_range)

    # file name can't have a '?', so it converts to '_'
    name_list = list(market_name)
    name_list[-1] = '_'
    market_name = ''.join(name_list)

    # path and name for downloaded market .csv
    load_path = downloads + market_name + '.csv'

    # load in predictit market csv
    market = pd.read_csv(load_path)

    # send off to the cleaners
    market_clean = cleanup_predictit(market)

    # save cleaned predictit market to csv
    save_path = projects + save_name
    market_clean.to_csv(save_path, index=False)

    # remove downloaded file to prevent duplicate naming
    os.remove(load_path)

    return market_clean


def download_market(url, date_range):
    ''' Use a URL to download a Predicit.com market and clean into a .csv.

    Download a .csv of market prices and trading volume for a given state,
    election, and time frame. Also grab the name of the market to easily
    access the csv.

    '''

    # open up chrome
    driver = webdriver.Chrome()
    driver.get(url)

    # allow page to load
    sleep(5)

    soup = BeautifulSoup(driver.page_source, 'lxml')

    # grab market name
    name = soup.find('h1').text

    # determine how far back to get data
    if date_range == '24hr':
        driver.find_element_by_xpath("//*[contains(text(), '24hr')]").click()
    elif date_range == '7d':
        driver.find_element_by_xpath("//*[contains(text(), '7 Day')]").click()
    elif date_range == '30d':
        driver.find_element_by_xpath("//*[contains(text(), '30 Day')]").click()
    elif date_range == '90d':
        driver.find_element_by_xpath("//*[contains(text(), '90 Day')]").click()

    # download csv
    driver.find_element_by_class_name('charts-header__download').click()

    # allow time to download
    sleep(5)

    driver.quit()

    return name


def convert_date(day):
    '''
    Take 'Date' column from Predictit csv and return a datetime.

    '''

    day = datetime.strptime(day, '%m/%d/%Y %H:%M:%S %p').date()

    return day


def convert_price(price):
    '''
    Remove dollar sign from Predictit price column.

    '''

    price = price.split('$')[-1]

    return price


def cleanup_predictit(market):
    '''
    Clean up .csv downloaded from predictit.

        - convert 'Date' column to datetime
        - drop unneccesary price columns
        - rename resulting columns

    '''

    # convert to date column to datetime
    market['market_date'] = market['Date'].apply(convert_date)

    # remove dollar sign from price column
    market['price'] = market['CloseSharePrice'].apply(convert_price)

    market = market.drop(columns=['OpenSharePrice',
                                  'HighSharePrice',
                                  'LowSharePrice',
                                  'CloseSharePrice',
                                  'Date'
                                  ])

    market = market.rename(columns={'ContractName': 'contract',
                                    'TradeVolume': 'volume'
                                    })

    return market


if __name__ == "__main__":

    # set download folder path
    downloads = '/Users/JonahKrop/Downloads/'

    # set project folder path
    projects = '/Users/JonahKrop/Documents/Projects/predictit/'

    # set how far back to get data
    date_range = '30d'  # ['24hr', '7d', '30d', '90d']

    # set the url here
    url = 'https://www.predictit.org/markets/detail/6845/What-will-be-the-margin-in-the-MN-05-House-Democratic-primary'

    # file save name
    save_name = 'minnesota_dem_primary_margin.csv'

    market = main(url, save_name, date_range)
