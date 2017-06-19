"""
Module for parsing and storing course pages from GolfAdvisor.com.

This module contains methods for collecting course info, users, and reviews
from a given list of courses on the GolfAdvisor domain.
"""
from concurrent.futures import (ProcessPoolExecutor, ThreadPoolExecutor,
                                as_completed)
from os import cpu_count

from bs4 import BeautifulSoup as bs
from numpy import array, array_split
from pymongo import MongoClient
import yaml

from . import (check_pages, get_course_info, make_mongo_update, parse_review,
               parse_user_info)
from ..app.utils import get_next_sequence

POOL_SIZE = cpu_count()


class DataHandler(object):
    """Class for collecting and writing data for GolfRecs.

    The DataHandler class is capable of collecting data for courses. That is
    all course specific stats and info as well as a collection of all reviews,
    and the info for the users who wrote them.

    Attributes:
        courses (numpy.ndarray): A NumPy array containing urls for courses.
        sessions (list of requests.sessions.Session): A list of requests
            sessions that are setup for making requests from multiple IP
            addresses.
        database (string): The name of the database for storing data.
        secrets (dict): A dictionary containing MongoDB authorization info.

    """

    def __init__(self, courses, sessions, database, secrets=True):
        """Initialize DataHandler for use with multiple IP addresses.

        Args:
            courses (numpy.ndarray, optional): A NumPy array containing urls
                for courses.
            sessions (list of requests.sessions.Session, optional): A list of
                requests sessions that are setup for making requests from
                multiple IP addresses.Args:

        """
        if secrets:
            with open('./application/secrets.yaml', 'r') as secrets_file:
                self.secrets = yaml.load(secrets_file)
        self.courses = courses
        self.sessions = sessions
        self.database = database

    def get_reviews(self):
        """Collect data for all links in self.courses.

        Returns:
            course_info (list): A list of dictionaries describing all the
                courses in pages.
            users (list): A list of dictionaries describing the users who left
                reviews for the course.
            reviews (list): A list of dictionaries containing all of the
                review data.

        """
        links_lists = array_split(array(self.courses), POOL_SIZE)
        course_info, users, reviews = [], [], []
        with ProcessPoolExecutor() as extr:
            results = extr.map(
                self.get_all_courses,
                enumerate(links_lists)
            )
        for result in results:
            course_info.extend(result[0])
            users.extend(result[1])
            reviews.extend(result[2])
        return course_info, users, reviews

    def get_all_courses(self, args):
        """Retrieve all documents for the given list of courses.

        Args:
            args (tuple): Tuple containing session number and list of pages.
                sess (int): Integer representing the requests.Session to use.
                pages (list): List of course links.
        Returns:
            course_info (list): A list of dictionaries describing all the
                courses in pages.
            users (list): A list of dictionaries describing the users who left
                reviews for the course.
            reviews (list): A list of dictionaries containing all of the
                review data.

        """
        sess, pages = args
        course_info, users, reviews = [], [], []
        with ThreadPoolExecutor(max_workers=2) as extr:
            threads = {
                extr.submit(
                    self.get_all_course_reviews,
                    sess,
                    page
                ): page for page in pages
            }
            for thread in as_completed(threads):
                data = thread.result()
                course_info.append(data[0])
                users.extend(data[1])
                reviews.extend(data[2])
        return course_info, users, reviews

    def get_all_course_reviews(self, session_num, url):
        """Retrieve all course info, users, and reviews for a given course.

        Function to build the course document. Finds the total number of reivew
        pages and gets reviews from each. Also returns document for course info
        and profile of all users who reviewed the course.

        Args:
            url (string): A string of the main course page.
        Returns:
            course_info (dict): Dictionary of all the course stats and info.
            users (list): A list of dictionaries describing the users who left
                reviews for the course.
            reviews (list): A list of dictionaries containing all of the
                review data.

        """
        session = self.sessions[session_num]
        response = session.get(url, )
        if response.status_code != 200:
            soup = bs(
                session.get('http://www.iplocation.net/find-ip-address').text,
                'html.parser'
            )
            ip_ = soup.find(style='font-weight: bold; color:green;').text
            raise ConnectionError(
                'Connection to {} failed using IP address {}'.format(url, ip_)
            )
        soup = bs(response.content, 'html.parser')
        course_info = get_course_info(soup, url)
        if not course_info:
            print('Fialed in acquiring {}'.format(url))
            print('Response was: \n{}'.format(response.content))
            raise ConnectionError()
        users = []
        reviews = []
        pages = check_pages(soup)
        for i in range(1, pages + 1):
            page = url + '?page={}'.format(i)
            new_users, new_reviews = self.get_course_reviews(
                page,
                session_num,
                course_info['Name']
            )
            users.extend(new_users)
            reviews.extend(new_reviews)
        return course_info, users, reviews

    def get_course_reviews(self, url, session_num, name):
        """Parse all reviews on a single page.

        Args:
            url (string): Page address from which to retrieve reviews.
            session_num (int): Integer representing which requests.Session to
                use.
            name (string): Name of the course.
        Returns:
            users (list): List of users stored as dictionaries.
            clearned_reviews (list): List of cleaned reviews stored as
                dictionaries.

        """
        session = self.sessions[session_num]
        response = session.get(url)
        soup = bs(response.content, 'html.parser')
        reviews = soup.find_all(itemprop='review')
        users = []
        cleaned_reviews = []
        for review in reviews:
            user = parse_user_info(review)
            users.append(user)
            cleaned_review = parse_review(review)
            cleaned_review['Username'] = user['Username']
            cleaned_review['Course Name'] = name
            cleaned_review['GA Url'] = url
            cleaned_reviews.append(cleaned_review)
        return users, cleaned_reviews

    def write_documents(self, collection, documents, filter_):
        """Write documents to a mongodb collection.

        Args:
            database (string): The name of the database to insert documents
                into.
            collection (string): The name of the collection to insert documents
                into.
            documents (list of dict): A list of dictionaries (documents) to
                insert into the collection.
            filter_ (string): String representing the name of the field to use
                as a filter.

        """
        dbase = MongoClient()[self.database]
        db_secrets = self.secrets['MongoDB']
        dbase.authenticate(db_secrets['user'], db_secrets['pass'])
        coll = dbase[collection]
        updates = []
        for document in documents:
            if filter_ == 'GA Id':
                id_ = get_next_sequence('Courses')
                update = make_mongo_update(document, filter_, 'Course Id', id_)
            elif filter_ == 'Username':
                id_ = get_next_sequence('Users')
                update = make_mongo_update(document, filter_, 'User Id', id_)
            else:
                id_ = document['Review Id']
                update = make_mongo_update(document, filter_, 'Review Id', id_)
            updates.append(update)
        coll.bulk_write(updates)