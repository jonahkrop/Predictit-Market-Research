library(lme4)

market = read.csv('iowa_senate.csv')
polls = read.csv('iowa_senate_polling.csv')

market$market_date <- as.Date(market$market_date)
polls$poll_date <- as.Date(polls$poll_date)

df <- merge(market, polls, left_on='contract', right_on='party')
df$time_diff <- df$market_date - df$poll_date

# drop market days w/ polls that didn't exist yet
df <- df[df$time_diff > 0,]

model <- lmer('price ~ polling +
                       poll.sample +
                       volume +
                       time_diff +
                       (1|pollster) + 
                       (1|pollster_grade) +
                       (1|voter.type) +
                       (1|party)', data=df)

summary(model)

df$predict_price <- predict(model, df)

cor(df$price, df$predict_price, method='pearson')

ranef(model)


