library(lme4)
library(dplyr)
#library(tidyr)
#library(plyr)
setwd("~/Documents/Projects/predictit")
#options(scipen = 999)

polling_setup <- function(){
  
  # combine senate and house polls into one
  senate_polls = read.csv('_senate_polling.csv')
  house_polls = read.csv('_house_polling.csv')
  polls = rbind(senate_polls, house_polls)
  
  # ignore states with special elections
  polls <- polls[polls$state != 'georgia',]
  
  # convert to datetime
  polls$poll_date <- as.Date(polls$poll_date, '%Y-%m-%d')
  
  # limit to polls since June
  polls <- polls[polls$poll_date >= '2020-07-01',]
  
  # calc sum of polling for each poll and party in the poll, and max in each poll
  poll_total <- polls %>% group_by(poll_id) %>% summarise(total_polling = sum(polling))
  party_total <- polls %>% group_by(poll_id, party) %>% summarise(party_polling = sum(polling))
  max_polling <- polls %>% group_by(poll_id) %>% summarise(max_poll = max(polling))
  
  # merge total polling by poll and party
  polls <- merge(polls, poll_total, by = 'poll_id')
  polls <- merge(polls, party_total, by = c('poll_id', 'party'))
  polls <- merge(polls, max_polling, by = 'poll_id')
  
  polls$leader <- 1
  polls$leader[polls$polling != polls$max_poll] <- -1
  
  # calculate poll as percent of total
  polls$percent <- round(polls$party_polling / polls$total_polling, 2)

  # if |net polling| >= 10, just set to 10
  polls$net_polling[abs(polls$net_polling) >= 10] <- 10
  
  # net polling +/-
  polls$net_polling <- polls$net_polling * polls$leader
  
  
  polls <- polls[c('election', 'state', 'district', 'party', 'poll_date',
                   'pollster', 'sponsored', 'pollster_grade', 'poll_sample',
                   'voter_type', 'percent', 'net_polling')]
  
  polls <- distinct(polls)
  
  return(polls)
}


market_setup <- function(){
  
  markets = read.csv('all_predictit_markets.csv')
  markets$market_date <- as.Date(markets$market_date, '%Y-%m-%d')
  
  # ignore states with special elections
  markets <- markets[markets$state != 'georgia',]
  
  markets$contract[(markets$contract != 'Democratic') &
                  (markets$contract != 'Republican')] <- 'Independent'
  
  return(markets)
  
}

polls <- polling_setup()
markets <- market_setup()

# merge together markets with polling. For each day of a market for an 
# election, state, district and party, join in all the polling data going
# back to May.
df <- merge(markets,
            polls,
            by.x=c('election', 'state', 'district', 'contract'),
            by.y=c('election', 'state', 'district', 'party')
            )

# find date difference between market and poll
df$poll_recency <- as.integer(df$market_date - df$poll_date)

# if market is for incumbent, flag it
df$incumbency = 0
df$incumbency[df$incumbent == df$contract] <- 1

# add poll weight based on price
df$poll_weight <- -0.007 * as.numeric(df$poll_recency) + 1
#df$weighted_poll <- df$percent * df$poll_weight


# don't use polls that came out in the future
# and limit to semi-recent polls
data <- df[df$poll_recency >= 0 & df$poll_recency <= 14,]

# perform scaling 
scale_cols <- c('percent', 'poll_sample', 'volume')
#data[scale_cols] <- scale(data[scale_cols])

train <- data[data$market_date < '2020-09-3',]
test <- data[data$market_date >= '2020-09-3',]


model <- lmer('price ~ percent + (1|incumbency) + (1|contract) + (1|net_polling)', data=train)
# model <- lm('price ~ net_polling + incumbency', data=train)
# AIC(model)

# summary(model)
# ranef(model)

test$price_predict <- predict(model, test)
print(cor(test$price, test$price_predict) ^ 2)

test_num <- test %>% 
                 group_by(election, state, district, contract, market_date, price) %>% 
                 summarise(num = sum(price_predict * poll_weight))
test_denom <- test %>% 
                   group_by(election, state, district, contract, market_date, price) %>% 
                   summarise(denom = sum(poll_weight))

test_final <- merge(test_num, test_denom)
test_final$predict_price <- round(test_final$num / test_final$denom, 2)
test_final$price_resid <- test_final$price - test_final$predict_price

targets <- test_final[test_final$market_date == max(test_final$market_date) & abs(test_final$price_resid) > 0.05,]
targets <- targets[c('election', 'state', 'district', 'contract', 'price', 
                       'predict_price', 'price_resid')]

#write.csv(targets, 'predictit_targets.csv', row.names = FALSE)
