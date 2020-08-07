import predict_party

import pandas as pd
import numpy as np
import re
import unidecode

from time import sleep
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium import common
from datetime import datetime
from webdriver_manager.chrome import ChromeDriverManager
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
            new = zip(*results['location'].apply(extract_state_district))
            results['location'], results['district'] = new

        elif election == 'senate':
            states = states_dict_senate()
            results['location'] = results['location'].map(states)
            results['district'] = 0

        results = results[[
            'election',
            'location',
            'district',
            'poll_date',
            'pollster',
            'pollster_grade',
            'poll_sample',
            'voter_type',
            'candidate',
            'party',
            'polling'
            ]]

        # save to csv
        docname = '%s_%s_polling.csv' % (state, election)
        results.to_csv(docname, index=False)
        print('Successfully scraped %s!' % state)


def get_state_polling(state, election):
    '''
    Grab 538's senate polling for a given state as far back as May, 2020. Ask
    the website to load more polls if necessary.

    '''

    # Set base url
    base_url = 'https://projects.fivethirtyeight.com/polls/'

    # open up chrome
    driver = webdriver.Chrome(ChromeDriverManager().install())
    driver.get(base_url + election + '/' + state)

    may = 0
    while may == 0:

        '''
        Extract html. If the last poll shown is more recent than May, request
        to show more polls. Continue requesting more polls until we get
        through May.
        '''
        
        # extract soup
        soup = BeautifulSoup(driver.page_source, 'lxml')

        # if state isn't available, return stuff
        if soup.text == '404 Not Found':
            polls = 'stop'
            recent = 'your state doesnt matter'
            may = 1

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

            # if last poll was before May 2020, stop
            # otherwise show more, unless there's none to show
            if (last.month < 5) | (last.year < 2020):
                may = 1
            else:
                try:
                    driver.find_element_by_class_name('show-more-wrap').click()
                except common.exceptions.ElementNotInteractableException:
                    print('all polls visible')
                    may = 1

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

    # extract html for pollster names for all polls
    pollster_names = poll_day.find_all('td', {'class': 'pollster'})

    # extract html for 538's pollster grades
    pollster_grades = poll_day.find_all('div', {'class': 'gradeText'})

    # extract html of all polling information (sample, voter type)
    poll_infos = poll_day.find_all('td', {'class': 'dates hide-desktop'})

    # extract hmtl of all polling results
    poll_results = poll_day.find_all('td', {'class': 'answers hide-desktop'})

    result_columns = [
        'election',
        'location',
        'poll_date',
        'pollster',
        'pollster_grade',
        'poll_sample',
        'voter_type',
        'candidate',
        'party',
        'polling'
        ]

    day_results = pd.DataFrame(columns=result_columns)
    for j in range(len(pollster_names)):
        '''
        Loop through each poll on the given day. For each poll, extract:
            - pollster name
            - pollster grade
            - poll sample size
            - poll participant type
            - candidate name
            - candidate party
            - candidate performance

        '''

        # extract name of pollster
        pollster_name = pollster_names[j].find_all('a',
                                                   {'target':
                                                    '_blank'})[0].text

        # extract 538's pollster grade, unless they don't have one
        try:
            pollster_grade = pollster_grades[j].text
        except IndexError:
            pollster_grade = np.nan

        # extract strings of poll information (sample, voter type, election)
        # html has only closed <br> tags, so replace w/ commas to separate
        poll_info = poll_infos[j]
        [br.replace_with(', ') for br in poll_info.select('br')]
        sample = poll_info.text.split(', ')[-1].split(' ')[0]
        voter = poll_info.text.split(', ')[-1].split(' ')[1]
        location = poll_info.find('span').text.strip(' ')

        # extract strings of candidate + polling and parse
        poll_result = poll_results[j].text.split('%')[:-1]
        candidate, polling = candidate_polling(poll_result)

        # extract poll coloring to determine party affiliation
        poll_party = poll_results[j].find_all('div', {'class': 'heat-map'})
        party = hex_to_color(poll_party)

        # initialize df for storing data for a loop
        temp_results = pd.DataFrame(columns=result_columns)

        temp_results['candidate'] = candidate
        temp_results['polling'] = polling
        temp_results['poll_date'] = poll_date
        temp_results['pollster'] = pollster_name
        temp_results['pollster_grade'] = pollster_grade
        temp_results['poll_sample'] = sample
        temp_results['voter_type'] = voter
        temp_results['party'] = party
        temp_results['election'] = elec
        temp_results['location'] = location

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
    r, g, b = [], [], []
    for c in range(len(poll_party)):

        # extract hex color
        hex_color = poll_party[c].attrs['style'].split(':')[1][:-1]

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


def extract_state_district(location):
    '''
    For House elections, split state-district abbrev. into name and number.

    '''

    # split by hyphen
    state_code = location.split('-')[0]
    district = location.split('-')[1]

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
    state = ''
    election = 'house'
    
    main(state, election)
