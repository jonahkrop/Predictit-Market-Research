library(lme4)
library(dplyr)
#library(tidyr)
#library(plyr)
setwd("~/Documents/Projects/predictit")
#options(scipen = 999)

polling_setup <- function(){

  # Do  a bunch of preparation for polling data:
  #   - combine house and senate
  #   - convert to datetimes
  #   - drop GA to ignore special elections
  #   - filter to top 2 candidates in a market
  #   - calculate sum of polling for a poll
  #
  #
  # Then, some analysis:
  #   - draw polling from a normal distribution using mean = polling
  #     and sd related to time out from election
  #   - calculate polling for a candidate as a percent of total
  #   - calculate net polling between top 2 candidates in a poll
  # 

  
  # combine senate and house polls into one
  senate_polls = read.csv('_senate_polling.csv')
  house_polls = read.csv('_house_polling.csv')
  polls = rbind(senate_polls, house_polls)
  
  # ignore states with special elections
  polls <- polls[polls$state != 'georgia',]
  
  # convert to datetime
  polls$poll_date <- as.Date(polls$poll_date, '%Y-%m-%d')
  
  # limit poll recency
  polls <- polls[polls$poll_date >= '2020-07-01',]
  
  #######################################
  # calculate sum of polling for a poll #
  #######################################
  
  # group by each poll_id
  poll_total <- polls %>% 
    group_by(poll_id) %>% 
    summarise(total_polling = sum(polling), .groups='drop')
  
  # merge total polling by poll and party
  polls <- merge(polls, poll_total, by = 'poll_id')
  
  ########################################################
  # Use time until election to calc uncertainty for poll #
  # and use uncertainty to draw polling from normal dist #
  ########################################################
  
  # find weeks out from election day and add in polling error
  polls$weeks_out <- as.integer((as.Date('2020-11-03') - polls$poll_date) / 7)
  polls$polling_error <- round(2 * (polls$weeks_out ^ 0.25), 1)
  
  # redraw polling from a normal distribution w/ mean = polling and sd = polling error
  polls$polling <- round(apply(polls[c('polling', 'polling_error')], 1, function(x) rnorm(1, mean=x[1], sd=x[2])))
  
  ##################################################
  # calculate net polling between top 2 candidates #
  ##################################################
  
  # rank performers in each poll
  polls$poll_rank <- (polls %>%
                      group_by(poll_id) %>%
                      mutate(ranks = order(order(polling, decreasing=TRUE))))$ranks
  
  # filter to top 2 candidates in each poll
  polls <- polls[polls$poll_rank <=2,]
  
  # add opponent rank to join in opponent polling
  polls$opponent_rank <- 1
  polls$opponent_rank[polls$poll_rank == 1] <-  2
  
  # join in opponent polling
  polls <- merge(polls,
                 polls[c('poll_id', 'opponent_rank', 'polling')], 
                 by.x=c('poll_id', 'poll_rank'), 
                 by.y=c('poll_id', 'opponent_rank'))
  colnames(polls)[colnames(polls) == 'polling.x'] <- 'polling'
  colnames(polls)[colnames(polls) == 'polling.y'] <- 'opponent_polling'

  # calculate net polling between candidate #1 and #2
  polls$net_polling <- polls$polling - polls$opponent_polling
  
  # if net polling is large, cap it at 10
  polls$net_polling[polls$net_polling > 10] <- 10
  polls$net_polling[polls$net_polling < -10] <- -10

  
  ###########################################
  # calculate polling as a percent of total #
  ###########################################
  
  # calculate candidate polling as percent of total
  polls$percent <- round(polls$polling / polls$total_polling, 2)
  
  
  # save columns and eliminate duplicates, just in case
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


all_results <- data_frame()
markets <- market_setup()

# simulate predictions 1000 times
start <- Sys.time()
for (i in 1:250){
  
  #print(i)

  # Simulate market pricing using polling drawn from a normal distribution. Each
  # loop re-draws polling numbers. Group and average the results by market.
  
 # (re)load in polls
  polls <- polling_setup()
  
  # merge together markets with polling
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
  df$poll_weight <- -0.008 * as.numeric(df$poll_recency) + 1
  
  # don't use polls that came out in the future
  # and limit to semi-recent polls
  data <- df[df$poll_recency >= 0 & df$poll_recency <= 14,]
  
  # use past polls to predict today's prices
  today <- Sys.Date() - 1
  train <- data[data$market_date < today,]
  test <- data[data$market_date == today,]
  
  model <- lmer('price ~ percent + net_polling + (1|incumbency) + (1|contract)', data=train)
  
  # predict today's market prices
  test$price_predict <- predict(model, test)

  # calc weighted average price estimate for each market based on 
  # the age of polls used to make the prediction
  test_num <- test %>% 
    group_by(election, state, district, contract, market_date, price) %>% 
    summarise(num = sum(price_predict * poll_weight), .groups='drop')
  test_denom <- test %>% 
    group_by(election, state, district, contract, market_date, price) %>% 
    summarise(denom = sum(poll_weight), .groups='drop')
  
  # combine to predicted price from downweighted past predictions
  test_final <- merge(test_num, test_denom)
  test_final$predict_price <- round(test_final$num / test_final$denom, 2)

  results <- test_final[c('election', 'state', 'district', 'contract',
                          'market_date', 'price', 'predict_price')]
  
  all_results <- rbind(all_results, results)
  
}
stop <- Sys.time()
print((stop - start))

# find avg. price by market
final_results <- all_results %>% 
  group_by(election, state, district, contract, market_date, price) %>% 
  summarise(price_predict = mean(predict_price), .groups='drop')

final_results$price_predict <- round(final_results$price_predict, 2)

final_results$price_resid <- final_results$price - final_results$price_predict

# set targets where residual >= $0.06
targets <- final_results[abs(final_results$price_resid) >= 0.06,]

save_name <- paste(today, 'targets.csv', sep='-')
path_out = '~/Documents/Projects/predictit/daily targets/'
write.csv(targets, paste(path_out, save_name, sep=''), row.names = FALSE)

print('Targets Acquired')
