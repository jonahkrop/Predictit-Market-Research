import predict_party

import pandas as pd
import numpy as np
import re
import unidecode

# from time import sleep
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium import common
from datetime import datetime
# from webdriver_manager.chrome import ChromeDriverManager
from PIL import ImageColor


def main(state, election):
    '''
    Scrape 538 for all polling. If a state doesn't have any polling in
    2020, just ignore it.

    '''

    polls, first_year = get_state_polling(state, election)

    # if there's no relevant polling, stop
    if (first_year != 2020) | (polls == 'stop'):
        print('No relevant polling for this state!')

    # otherwise, extract information
    else:
        final_results = pd.DataFrame()
        for n in range(len(polls)):
            day_results = extract_polling(polls[n])

            final_results = pd.concat([final_results, day_results], axis=0)

        # sometimes web scraping duplicates polls, not sure why
        results = final_results.drop_duplicates(keep='first')
        results = results.reset_index(drop=True)

        # 538 uses state name (and district) abbreviations in their polls.
        # annoyingly, they use different ones for Senate and House polls.
        if election == 'house':
            # 1) split state-dist. into two columns
            # 2) change long election mame to short
            new = zip(*results['state'].apply(extract_state_district))
            results['state'], results['district'] = new
            results.loc[results['election'] == 'U.S. House',
                        'election'] = 'house'

        elif election == 'senate':
            # 1) get senate poll state abbrvs.
            # 2) change long election name to short
            states = states_dict_senate()
            results['state'] = results['state'].map(states)
            results.loc[results['election'] == 'U.S. Senate',
                        'election'] = 'senate'
            results['district'] = 0

        results = results[[
            'poll_id',
            'election',
            'state',
            'district',
            'poll_date',
            'pollster',
            'sponsored',
            'pollster_grade',
            'poll_sample',
            'voter_type',
            'candidate',
            'party',
            'polling',
            'net_polling'
            ]]

        # save to csv
        docname = '%s_%s_polling.csv' % (state, election)
        results.to_csv(docname, index=False)
        print('Successfully scraped %s!' % state)


def get_state_polling(state, election):
    '''
    Grab 538's senate polling for a given state as far back as July, 2020. Ask
    the website to load more polls if necessary.

    '''

    # Set base url
    base_url = 'https://projects.fivethirtyeight.com/polls/'

    # open up chrome
    driver = webdriver.Chrome()
    driver.get(base_url + election + '/' + state)

    stop = 0
    while stop == 0:

        '''
        Extract html. If the last poll shown is more recent than July, request
        to show more polls. Continue requesting more polls until we get
        through July.
        '''

        # extract soup
        soup = BeautifulSoup(driver.page_source, 'lxml')

        # if state isn't available, return stuff
        if soup.text == '404 Not Found':
            polls = 'stop'
            recent = 'your state doesnt matter'
            stop = 1

        else:
            # get html for each poll on the page
            polls = soup.find_all('div', {'class': 'day-container'})

            # get most recent poll year
            recent = polls[0].find_all('h2',
                                       {'class': 'day'})[0].attrs['data-date']
            recent = datetime.strptime(recent, '%Y-%m-%d').year

            # get last poll date
            last = polls[-1].find_all('h2',
                                      {'class': 'day'})[0].attrs['data-date']
            last = datetime.strptime(last, '%Y-%m-%d').date()

            # if last poll was before July 2020, stop
            # otherwise show more, unless there's none to show
            if (last.month < 6) | (last.year < 2020):
                stop = 1
            else:
                try:
                    driver.find_element_by_class_name('show-more-wrap').click()
                except common.exceptions.ElementNotInteractableException:
                    print('all polls visible')
                    stop = 1

    driver.close()

    return polls, recent


def extract_polling(poll_day):
    '''
    538 groups polls by day, so it's possible to have multiple polls in one
    entry. Function takes the poll(s) of a given day and extracts:
        - the published day the poll(s)
        - the pollster name(s) for the poll(s)
        - 538's pollster grade(s)
        - sample size and consituency for the poll(s)
        - results of the poll(s)

    '''

    # extract publish date
    poll_date = poll_day.find_all('h2', {'class': 'day'})[0].attrs['data-date']

    # extract election type (house, senate, etc) -- html isn't consistent
    try:
        elec = poll_day.find('td', {
            'class': 'type hide-mobile single first'
            }).text
    except AttributeError:
        elec = poll_day.find('td', {
            'class': 'type hide-mobile single first last'
            }).text

    # save all polling results
    poll_results = poll_day.find_all('tr', {'class': 'visible-row'})

    result_columns = [
        'poll_id',
        'election',
        'state',
        'poll_date',
        'pollster',
        'sponsored',
        'pollster_grade',
        'poll_sample',
        'voter_type',
        'candidate',
        'party',
        'polling',
        'net_polling'
        ]

    # initialize df to update with each poll
    day_results = pd.DataFrame(columns=result_columns)

    for j in range(len(poll_results)):
        '''
        Loop through each poll on the given day. For each poll, extract:
            - pollster name
            - pollster grade
            - poll sample size
            - poll participant type
            - candidate name
            - candidate party
            - candidate performance
            - net polling

        '''

        # extract name of pollster
        pollster_name = poll_results[j].find_all('a',
                                                 {'target': '_blank'})[0].text
        # 538 marks sponsored polls with an '*'
        if pollster_name[-1] == '*':
            sponsored = 1
            pollster_name = pollster_name[:-1]
        else:
            sponsored = 0

        # extract 538's pollster grade, unless they don't have one
        try:
            pollster_grade = poll_results[j].find_all(
                'div', {'class': 'gradeText'}
                )[0].text
        except IndexError:
            pollster_grade = np.nan

        # extract strings of poll information (sample, voter type, election)
        # html has only closed <br> tags, so replace w/ commas to separate
        poll_info = poll_results[j].find_all(
            'td', {'class': 'dates hide-desktop'}
            )[0]
        [br.replace_with(', ') for br in poll_info.select('br')]
        sample = poll_info.text.split(', ')[-1].split(' ')[0]
        voter = poll_info.text.split(', ')[-1].split(' ')[1]
        state = poll_info.find('span').text.strip(' ')

        # extract strings of candidate + polling and parse
        results = poll_results[j].find_all(
            'td', {'class': 'answers hide-desktop'}
            )
        poll_result = results[0].text.split('%')[:-1]
        candidate, polling = candidate_polling(poll_result)

        # find net polling difference
        # if not dem, rep, or ind leading, then even
        try:
            net = poll_results[j].find_all(
                'td', {'class': 'net hide-mobile dem'}
                )[0].text
        except IndexError:
            try:
                net = poll_results[j].find_all(
                    'td', {'class': 'net hide-mobile rep'}
                    )[0].text
            except IndexError:
                try:
                    net = poll_results[j].find_all(
                        'td', {'class': 'net hide-mobile ind'}
                        )[0].text
                except IndexError:
                    net = 0
        # drop '+'
        net = int(net)

        # extract poll coloring to determine party affiliation
        poll_party = poll_results[j].find_all(
            'td', {'class': 'answers hide-desktop'}
            )
        party = hex_to_color(poll_party)

        # give a poll ID comprised of date + number
        poll_id = str(poll_date) + '-' + str(elec) + '-%s' % j

        # initialize df for storing data for a loop
        temp_results = pd.DataFrame(columns=result_columns)

        temp_results['candidate'] = candidate
        temp_results['polling'] = polling
        temp_results['net_polling'] = net
        temp_results['poll_date'] = poll_date
        temp_results['pollster'] = pollster_name
        temp_results['sponsored'] = sponsored
        temp_results['pollster_grade'] = pollster_grade
        temp_results['poll_sample'] = int(sample.replace(',', ''))
        temp_results['voter_type'] = voter
        temp_results['party'] = party
        temp_results['election'] = elec
        temp_results['state'] = state
        temp_results['poll_id'] = poll_id

        # add into the day's results
        day_results = pd.concat([day_results, temp_results], axis=0)

    return day_results


def candidate_polling(poll_result):
    '''
    For each candidate in a poll, extract the candidate name
    and polling result.
    '''

    candidate, polling = [], []
    for c in range(len(poll_result)):

        # remove any non-alphanumerics bc they fuck it up
        res = re.sub(r'\W+', '', poll_result[c])

        # change any accented characters to regular
        res = unidecode.unidecode(res)

        # extract letters and numbers from string into name + polling
        pull = extract_text_int(res)

        candidate.append(pull[1])
        polling.append(pull[2])

    return candidate, polling


def hex_to_color(poll_party):
    '''
    Extract hex color from polling data and convert to RGB to determine
    candidate's political affiliation.
        - Rep. has highest red value
        - Dem. has highest blue value
        - Ind. has highest green value

    '''

    # filter to colormap data
    filt = poll_party[0].find_all('div', {'class': 'heat-map'})

    r, g, b = [], [], []
    for c in range(len(filt)):

        # extract hex color
        hex_color = filt[c].attrs['style'].split(':')[1][:-1]

        # convert to rgb
        rgb = ImageColor.getcolor(hex_color, 'RGB')

        r.append(rgb[0])
        g.append(rgb[1])
        b.append(rgb[2])

    color = pd.DataFrame(zip(r, g, b), columns=['red', 'green', 'blue'])
    color['party'] = predict_party.predict_party(color)

    return list(color['party'])


def extract_text_int(string):
    '''
    Extract the text and integers from a string and separate them.

    '''

    r = re.compile("([a-zA-Z]+)([0-9]+)")
    sep = r.match(string)

    return sep


def extract_state_district(state):
    '''
    For House elections, split state-district abbrev. into name and number.

    '''

    # split by hyphen
    state_code = state.split('-')[0]
    district = state.split('-')[1]

    # use dict of shortcuts and names to grab full name
    states = states_dict_house()
    state_name = states[state_code]

    return state_name, district


def states_dict_house():
    '''
    Return dictionary of 538 House abbreviations to full name.
    '''

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
    states['NH'] = 'new hampshire'
    states['NJ'] = 'new jersey'
    states['NM'] = 'new mexico'
    states['NY'] = 'new york'
    states['NC'] = 'north carolina'
    states['ND'] = 'north dakota'
    states['OH'] = 'ohio'
    states['OK'] = 'oklahoma'
    states['OR'] = 'oregon'
    states['PA'] = 'pennsylvania'
    states['PR'] = 'puerto rico'
    states['RI'] = 'rhode island'
    states['SC'] = 'south carolina'
    states['SD'] = 'south dakota'
    states['TN'] = 'tennessee'
    states['TX'] = 'texas'
    states['UT'] = 'utah'
    states['VT'] = 'vermont'
    states['VA'] = 'virginia'
    states['WA'] = 'washington'
    states['WV'] = 'west virginia'
    states['WI'] = 'wisconsin'
    states['WY'] = 'wyoming'

    return states


def states_dict_senate():
    '''
    Return dictionary of 538 Senate abbreviations to full name.
    '''

    states = {}
    states['Ala.'] = 'alabama'
    states['Alaska'] = 'alaska'
    states['Ariz.'] = 'arizona'
    states['AR'] = 'arkansas'
    states['Calif.'] = 'california'
    states['Colo.'] = 'colorado'
    states['Conn.'] = 'connecticut'
    states['Del.'] = 'delaware'
    states['Fla.'] = 'florida'
    states['Ga.'] = 'georgia'
    states['HI'] = 'hawaii'
    states['ID'] = 'idaho'
    states['Ill.'] = 'illinois'
    states['Ind.'] = 'indiana'
    states['Iowa'] = 'iowa'
    states['Kan.'] = 'kansas'
    states['Ky.'] = 'kentucky'
    states['LA'] = 'louisiana'
    states['Maine'] = 'maine'
    states['Md.'] = 'maryland'
    states['Mass.'] = 'massachusetts'
    states['Mich.'] = 'michigan'
    states['Minn.'] = 'minnesota'
    states['Miss.'] = 'mississippi'
    states['Mo.'] = 'missouri'
    states['Mont.'] = 'montana'
    states['Neb.'] = 'nebraska'
    states['Nev.'] = 'nevada'
    states['N.H.'] = 'new hampshire'
    states['N.J.'] = 'new jersey'
    states['N.M.'] = 'new mexico'
    states['N.Y.'] = 'new york'
    states['N.C.'] = 'north carolina'
    states['N.D.'] = 'north dakota'
    states['Ohio'] = 'ohio'
    states['Okla.'] = 'oklahoma'
    states['OR'] = 'oregon'
    states['Pa.'] = 'pennsylvania'
    states['R.I.'] = 'rhode island'
    states['S.C.'] = 'south carolina'
    states['S.D.'] = 'south dakota'
    states['Tenn.'] = 'tennessee'
    states['Texas'] = 'texas'
    states['Utah'] = 'utah'
    states['Vt.'] = 'vermont'
    states['Va.'] = 'virginia'
    states['Wash.'] = 'washington'
    states['W.Va.'] = 'west virginia'
    states['Wis.'] = 'wisconsin'
    states['Wyo.'] = 'wyoming'

    return states


if __name__ == "__main__":

    # set state & election type
    main('', 'senate')
    main('', 'house')
