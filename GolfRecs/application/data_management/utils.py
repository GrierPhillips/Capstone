"""This module provides utility functions that are used within GolfRecs."""

from math import ceil
from operator import itemgetter

from bs4 import BeautifulSoup as bs
from fake_useragent import UserAgent
from pymongo import UpdateOne
from stem.control import Controller
from stem import Signal


def get_extras(soup):
    """Return a dictionary of extra information about the course.

    Some courses contain extra information about driving range, carts,
    spikes, lessons, etc... Collect and return this information as a
    dictionary with keys as the information and values as a 'Yes' or 'No'.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance containing course
            html.
    Returns:
        extras (dict): Dictionary of course extras.

    """
    try:
        extras_groups = soup.find(id='more').find_all(class_='col-sm-4')
    except AttributeError:
        return {}
    extras_lists = [group.find_all('div') for group in extras_groups]
    extras = dict(
        [extra.text.split(': ', 1) for lst in extras_lists for extra in lst]
    )
    return extras


def get_tee_info(soup):
    """Return a dictionary of tees.

    Given the html for a course, return a dictionary of tees where the tee
    names are the keys and the values are dictionaries containing the
    stats for that tee (length, par, slope, rating).

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance containing course
            html.
    Returns:
        tees (dict): Dictionary of tee documents.

    """
    rows = soup.find_all('tr')
    tees = {}
    try:
        headings = [head.text for head in rows[0].find_all('th')]
        all_tees = [value.text.strip().split('\n') for value in rows[1:]]
        for tee in all_tees:
            tees[tee[0].replace('.', '').replace('$', '')] = dict(
                zip(headings[1:], tee[1:])
            )
        return tees
    except IndexError:
        return {}


def get_key_info(soup):
    """Return dictionary of key info about the course extracted from html.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance containing course
            html.
    Returns:
        key_info (dict): They pieces of key info provided about the course.

    """
    try:
        info = soup.find(class_='key-info clearfix').find_all('div')[2:]
    except AttributeError:
        return {}
    item_pairs = [item.text.split(':', 1) for item in info]
    key_info = dict([list(map(str.strip, pair)) for pair in item_pairs])
    return key_info


def parse_address(soup):
    """Return dictionary of address items for the course extracted from html.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance containing course
            html.
    Returns:
        address (dict): Dictionary containing the mailing address and all
            of the components of the address.

    """
    address = dict()
    address_info = soup.find(itemprop='address').find_all('li')
    for item in address_info:
        if 'itemprop' in item.attrs:
            if item['itemprop'] == 'sameAs':
                address['Website'] = item.text
            else:
                address[item.attrs['itemprop']] = item.text
        else:
            address[item.attrs['class'][0]] = item.text
    return address


def get_layout(soup):
    """Return dictionary of course layout from the html.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance containing course
            html.
    Returns:
        layout (dictionary): Dictionary containing all elements of the
            course layout that are present: Holes, Par, Length, Slope,
            and Rating.

    """
    try:
        info = soup.find(class_='course-essential-info-top').find_all('li')
    except AttributeError:
        return {}
    layout = dict([child.text.split(': ') for child in info][:-1])
    return layout


def parse_review(review):
    """Return a dictionary of review information.

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
    id_ = review.find(class_='row')['id'].split('-')[1]
    review_info['Review Id'] = id_
    review_info['Rating'] = review.find(itemprop='ratingValue').text
    try:
        review_info['Played On'] = review.find(class_='review-play-date').text
    except AttributeError:
        pass
    try:
        review_info['Title'] = review.find(itemprop='name').text
    except AttributeError:
        pass
    for label in review.find_all(class_='label'):
        review_info[label.text] = '1'
    try:
        ratings = review.find(class_='review-secondary-ratings')\
            .find_all('span')
        ratings = [rating.text.strip(':\n\t\xa0') for rating in ratings]
        review_info.update(dict(zip(ratings[::2], ratings[1::2])))
    except AttributeError:
        pass
    paragraphs = review.find(class_='review-body').find_all('p')
    text = ' '.join([paragraph.text for paragraph in paragraphs])
    review_info['Review'] = text
    return review_info


def parse_user_info(review):
    """Return a dictionary of user information.

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
    user_attrs = [item.text.strip() for item in info.find_all('span')]
    user_info = {}
    try:
        user_info['Userpage'] = info.find('a')['href']
    except TypeError:
        pass
    user_info['Username'] = user_attrs[0]
    first_att_index = get_first_index(':', user_attrs)
    if first_att_index > 1:
        for att in user_attrs[1:first_att_index + 1]:
            user_info[att] = 1
    keys = map(lambda x: x.strip(':'), user_attrs[first_att_index::2])
    user_info.update(
        dict(zip(keys, user_attrs[first_att_index + 1::2]))
    )
    return user_info


def get_first_index(substring, items):
    """Return the index of the first occurrence of substring in list.

    Args:
        substring (string): The string to search for in list.
        items (list): The list to search for substring in.
    Returns:
        index (int): Index of the first occurrence of substring or -1 if the
            substring does not occur.

    """
    for index, val in enumerate(items):
        if val.endswith(substring):
            return index
    index = -1
    return index


def check_pages(soup):
    """Return the number of pages of reviews a course has.

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


def get_course_info(soup, url):
    """Create a document for a golf course, including course stats and info.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance containing html
            for the main course page.
        url (string): The address of the main course page.
    Returns:
        course_doc (dict): Dictionary containing the course stats and info.

    """
    course_doc = {}
    course_doc['GA Url'] = url
    course_doc['GA Id'] = int(url.split('-')[0].split('/')[-1])
    course_doc['Name'] = soup.find(itemprop='name').text
    course_doc['Layout'] = get_layout(soup)
    course_doc.update(parse_address(soup))
    course_doc.update(get_key_info(soup))
    course_doc['Tees'] = get_tee_info(soup)
    course_doc.update(get_extras(soup))
    return course_doc


def renew_connection():
    """Change tor exit node. This will allow cycling of IP addresses."""
    with Controller.from_port(port=9051) as controller:
        controller.authenticate(password="password")
        controller.signal(Signal.NEWNYM)  # pylint: disable=E1101


def make_mongo_update(document, filter_, id_name=None, id_=None):
    """Create an update object for a bulk update.

    The update will include the unique user or course id for documents
    about users or courses.

    Args:
        document (dict): Dictionary containing all object attributes.
        filter_ (string): String representing the name of the field to use as a
            filter.
        id_name (string): String represinting the name of the Id field for the
            given document type.
        id_ (int): Integer representing the unique id of the document (used as
            index for constructing ratings matrix).
    Returns:
        update (pymongo.Operations.UpdateOne): Update operation for use in
            pymongo bulk update.

    """
    if isinstance(id_, int):
        document.update({id_name: id_})
    update = UpdateOne(
        {filter_: document[filter_]},
        {'$set': document},
        upsert=True
    )
    return update


def get_new_docs(key, collection, docs):
    """Return a tuple containing all new documents.

    Collect the distinct values for a given key residing in a given
    collection and return the documents in docs that do not have a key
    already in the collection.

    Args:
        key (string): The name of the field to acquire the distinct values
            of.
        collection (pymongo.collection.Collection): The collection to
            search for distinct values of the given key.
        docs (list): A list of dictionaries representing documents of
            courses, users, or reviews.
    Returns:
        docs (tuple): A tuple of documents not already stored in the
            given collection.

    """
    docs = {doc[key]: doc for doc in docs}
    existing = set(collection.distinct(key))
    new = set([id_ for id_ in docs]).difference(existing)
    if new:
        docs = itemgetter(*new)(docs)
        if isinstance(docs, dict):
            docs = (docs, )
        return docs


def ip_error(session, url):
    """Raise an error containing the ip address of the failing session.

    When a session fails making a request raise a ConnectionError along with
    the url that was requested and the ip address of the session making the
    request.

    Args:
        session (requests.sessions.Session): The session used to make the
            original failed request.
        url (string): The url that was being requested when the failure
            occurred.

    """
    soup = bs(
        session.get('http://www.iplocation.net/find-ip-address').text,
        'html.parser'
    )
    ip_ = soup.find(style='font-weight: bold; color:green;').text
    raise ConnectionError(
        'Connection to {} failed using IP address {}'.format(url, ip_)
    )


def get_response(session, url):
    """Return a response or raise an error if the response is not acquired.

    Args:
        session (requests.session.Session): Session for making the request.
        url (string): Website to request.
    Returns:
        response (requests.models.Response): Response object of sucessful
            request.

    """
    agent = UserAgent()
    rand = agent.random
    try:
        response = session.get(url, headers={'User-Agent': rand})
    except Exception:  # pylint: disable=W0703
        ip_error(session, url)
    if response.status_code != 200:
        ip_error(session, url)
    return response
