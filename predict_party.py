import pandas as pd
import numpy as np
import seaborn as sns
from sklearn.svm import SVC

'''
Use a linear SVC to classify polling result RGB color as a political party.
Only need to use green and blue. All Rep. and many Ind. have r = 255, while
green and blue vary for all 3 options. 

'''

# uncomment to view relationship

# df = pd.read_csv('rgb_party.csv')
# sns.scatterplot(df.blue, df.green, hue=df.party)


def predict_party(rgb):

    df = pd.read_csv('rgb_party.csv')
    
    x = df[['green', 'blue']]
    y = df['party']
    
    # set linear SVC
    model = SVC(kernel='linear').fit(x, y)
    
    party = model.predict(rgb[['green', 'blue']])
    
    return party


