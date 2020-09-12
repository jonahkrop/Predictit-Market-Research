"""
Created on Sat Sep 12 13:49:13 2020

@author: JonahKrop
"""

import time
import os

'''
Execute all the files necessary to produce today's Predictit market targets.

1) Scrape 538 polling on House and Senate races
2) Pull down the last 30 days of market pricing from several Predicit markets
3) Make predictions for market prices and identify markets that are mispriced

Total takes 10 minutes to finish.
'''

# start timing
t1 = time.time()

# scrape senate and house polling from 538
import scrape_538
t2 = time.time()
print('Finished scraping 538 after %.2f minutes \n' % ((t2 - t1) / 60))

# scrape all the senate + house predictit markets (slow)
import scrape_predictit_all
t3 = time.time()
print('Finished scraping predictit after %.1f minutes \n' % ((t3 - t2) / 60))

# make predictions for market pricing and return targets in a .csv
os.environ['R_HOME'] = '/Library/Frameworks/R.framework/Resources'
import rpy2.robjects as robjects
r_source = robjects.r['source']
r_source('market_price_modeling.R')
t4 = time.time()
print('Finished marketplace predictions after %.1f minutes' % ((t4-t3) / 60))
