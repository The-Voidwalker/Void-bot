"""Module for machine learning utilities."""

import pandas as pd
import nltk
from nltk.corpus import stopwords
import string
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import SGDClassifier


def process_text(text):
    """Take input text and tokenize it."""
    nopunc = [char for char in text if char not in string.punctuation]
    nopunc = ''.join(nopunc)

    clean_words = [word for word in nopunc.split() if word.lower() not in stopwords.words('english')]
    return clean_words


def train():
    """Build and fit a vectorizer and classifier using data from a dataset.csv.

    This file must be in the same directory as ml.py.
    This method should be threaded properly!
    """
    nltk.download('stopwords', quiet=True)
    df = pd.read_csv('dataset.csv')
    vectorizer = CountVectorizer(analyzer=process_text)
    messages_bow = vectorizer.fit_transform(df['text'].values.astype(str))
    classifier = SGDClassifier(loss='hinge', alpha=1e-6, tol=1e-6)
    classifier.fit(messages_bow, df['abuse'])
    classifier2 = SGDClassifier(loss='log', alpha=1e-5, tol=1e-5)
    classifier2.fit(messages_bow, df['abuse'])
    return (vectorizer, classifier, classifier2)
