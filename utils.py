"""
GolfRecs.utils

This module provides utility functions that are used within GolfRecs.
"""

from math import ceil


def get_extras(soup):
    """
    Return a dictionary of extra information about the course.

    Some courses contain extra information about driving range, carts,
    spikes, lessons, etc... Collect and return this information as a
    dictionary with keys as the information and values as a 'Yes' or 'No'.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance containing course
            html.
    Returns:
        extras (dict): Dictionary of course extras.
    """
    extras_groups = soup.find(id='more').find_all(class_='col-sm-4')
    extras_lists = [group.find_all('div') for group in extras_groups]
    extras = dict(
        [extra.text.split(': ') for lst in extras_lists for extra in lst]
    )
    return extras


def get_tee_info(soup):
    """
    Return a dictionary of tees.

    Given the html for a course, return a dictionary of tees where the tee
    names are the keys and the values are dictionaries containing the
    stats for that tee (length, par, slope, rating).

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance containing course
            html.
    Returns:
        tees (dict): Dictionary of tee documents.
    """
    rows = soup.find('tr')
    tees = {}
    headings = [head.text for head in rows[0].find_all('th')]
    all_tees = [value.text.strip().split('\n') for value in rows[1:]]
    for tee in all_tees:
        tees[tee[0]] = dict(zip(headings[1:], tee[1:]))
    return tees


def get_key_info(soup):
    """
    Return dictionary of key info about the course extracted from html.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance containing course
            html.
    Returns:
        key_info (dict): They pieces of key info provided about the course.
    """
    info = soup.find(class_='key-info clearfix').find_all('div')[2:]
    key_info = dict([item.text.split(': ') for item in info])
    return key_info


def parse_address(soup):
    """
    Return dictionary of address items for the course extracted from html.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance containing course
            html.
    Returns:
        address (dict): Dictionary containing the mailing address and all
            of the components of the address.
    """
    address = dict()
    address_info = soup.find_all(class_='address')
    for item in address_info:
        if 'itemprop' in item.keys():
            address[item.attrs['itemprop']] = item.text
        else:
            address[item.attrs['class'][0]] = item.text
    return address


def get_layout(soup):
    """
    Return dictionary of course layout from the html.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance containing course
            html.
    Returns:
        layout (dictionary): Dictionary containing all elements of the
            course layout that are present: Holes, Par, Length, Slope,
            and Rating.
    """
    info = soup.find(class_='course-essential-info-top').find_all('li')
    layout = dict([child.text.split(': ') for child in info][:-1])
    return layout


def parse_review(review):
    """
    Return a dictionary of review information.

    Given a BeautifulSoup element extract the components of the review and
    organize them into a dictionary.

    Args:
        review (bs4.element.Tag): A BeautifulSoup tag element that contains
            all of the information for a single review.
    Returns:
        review_info (dict): A dictionary containing all of the provided
            review components.
    """
    review_info = {}
    review_info['Rating'] = review.find(itemprop='ratingValue').text
    review_info['Played On'] = review.find(class_='review-play-date').text
    review_info['Title'] = review.find(itemprop='name').text
    for label in review.find_all(class_='label'):
        review_info[label.text] = '1'
    ratings = review.find(class_='review-secondary-ratings')\
        .find_all('span')
    ratings = [rating.text.strip(':\n\t\xa0') for rating in ratings]
    review_info.update(dict(zip(ratings[::2], ratings[1::2])))
    return review_info


def parse_user_info(review):
    """
    Return a dictionary of user information.

    Given a BeautifulSoup element extract the user attributes form the html
    and organize them into a dictionary.

    Args:
        review (bs4.element.Tag): A BeautifulSoup tag element that contains
            all of the information for a single review.
    Returns:
        user_info (dict): A dictionary containing all of the provided
            user information.
    """
    info = review.find(
        class_='bv_review_user_details col-xs-8 col-sm-12'
    )
    user_attrs = [item for item in info.find_all('span')]
    user_attrs = [item.text.strip() for item in user_attrs]
    user_info = {}
    user_info['Userpage'] = info.find('a')['href']
    user_info['Username'] = user_attrs[0]
    keys = map(lambda x: x.strip(':'), user_attrs[1::2])
    user_info.update(
        dict(zip(keys, user_attrs[2::2]))
    )
    return user_info


def check_pages(soup):
    """
    Return the number of pages of reviews a course has.

    Given the total number of reivews for a course determine the number
    of pages that are populated with reviews. Each page has 20 reviews.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance containing course
            html.
    Returns:
        pages (int): Number of pages containing reviews.
    """
    review_count = int(soup.find(itemprop='reviewCount').text.strip('()'))
    pages = 1
    if review_count > 20:
        pages = ceil(review_count / 20)
    return pages
