# Predicitit-Market-Research
Use political polling to build models for predicting market prices on Predictit.com

## 1a) Scrape 538 polling data
Use `scrape_538.py` to scrape recent polling data from 538, as far back as like June? idk exactly. Adjust 'house' or 'senate' at the bottom. Also makes use of `rgb_party.csv` and `predict_party.py` to convert the poll coloring to political party.

produces the `_senate_polling.csv` or `_house_polling.csv` files.

## 1b) Pull down Predictit.com market info
Use `scrape_predictit_all.py` to automatically scrape all markets using the URL's in `predictit_market_urls.csv`, or, use `scrape_predictit.py` to plug in a single url and scrape that market. Gets the last 30 days.

produces the `all_predictit_markets.csv` file.

## 2) Predict market prices

Use `market_analysis.R` to build market price predictions using a lmer model. Does some data manipulation and merges markets and polling together. then makes predictions using the last month of market data and the previous 2 weeks of polling as relates to a market.
