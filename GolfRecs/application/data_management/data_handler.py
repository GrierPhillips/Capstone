"""
Module for parsing and storing course pages from GolfAdvisor.com.

This module contains methods for collecting course info, users, and reviews
from a given list of courses on the GolfAdvisor domain.
"""
from concurrent.futures import (ProcessPoolExecutor, ThreadPoolExecutor,
                                as_completed)
from functools import partial
from os import cpu_count

from bs4 import BeautifulSoup as bs
from numpy import array, array_split

from .utils import (check_pages, get_course_info, get_new_docs, get_response,
                    make_mongo_update, parse_review, parse_user_info)

POOL_SIZE = cpu_count()


class DataHandler(object):
    """Class for collecting and writing data for GolfRecs.

    The DataHandler class is capable of collecting data for courses. That is
    all course specific stats and info as well as a collection of all reviews,
    and the info for the users who wrote them.

    Attributes:
        sessions (list of requests.sessions.Session): A list of requests
            sessions that are setup for making requests from multiple IP
            addresses.
        database (string): The name of the database for storing data.

    """

    def __init__(self, sessions):
        """Initialize DataHandler for use with multiple IP addresses.

        Args:
            sessions (list of requests.sessions.Session, optional): A list of
                requests sessions that are setup for making requests from
                multiple IP addresses.Args:

        """
        self.sessions = sessions
        self.database = 'GolfRecs'

    def get_reviews(self, dbase, courses):
        """Collect data for all links in courses.

        Args:
            dbase (pymongo.database.Database): Database where Courses, Reviews,
                and Users collection resides.
            courses (numpy.ndarray): A NumPy array containing urls for courses.
        Returns:
            course_info (list): A list of dictionaries describing all the
                courses linked in courses.
            users (list): A list of dictionaries describing the users who left
                reviews for the course.
            reviews (list): A list of dictionaries containing all of the
                review data.

        """
        existing = set(dbase['Courses'].distinct('GA Url'))
        new = list(set(courses).difference(existing))
        new_courses = array(new)
        links_lists = array_split(new_courses, POOL_SIZE)
        course_info, userpages, reviews = [], {}, []
        with ProcessPoolExecutor() as extr:
            results = extr.map(
                self.get_all_courses,
                enumerate(links_lists)
            )
        for result in results:
            course_info.extend(result[0])
            userpages.update(result[1])
            reviews.extend(result[2])
        return userpages, course_info, reviews

    def get_users(self, dbase, userpages):
        """Collect data from all links in userpages.

        Args:
            dbase (pymongo.database.Database): Database where Users collection
                resides.
            # userpages (numpy.ndarray): A NumPy array containing urls for user
            #     profiles.
            userpages (dict): Dictionary of Username, Userpage pairs.
        Returns:
            users (list): List of dictionaries describing all the users linked
                in userpages.

        """
        coll = dbase.Users
        existing_userpages = set(coll.distinct('Username'))
        new_users = list(set(userpages.keys()).difference(existing_userpages))
        new_pages = {user: userpages[user] for user in new_users}
        users = array_split(array(list(new_pages.keys())), POOL_SIZE)
        pages = array_split(array(list(new_pages.values())), POOL_SIZE)
        user_docs = []
        with ProcessPoolExecutor() as extr:
            results = extr.map(
                self.get_all_users,
                enumerate(zip(users, pages))
            )
        for result in results:
            user_docs.extend(result)
        return users

    def get_all_courses(self, args):
        """Retrieve all documents for the given list of courses.

        Args:
            args (tuple): Tuple containing session number and list of pages.
        Returns:
            course_info (list): A list of dictionaries describing all the
                courses in pages.
            users (list): A list of dictionaries describing the users who left
                reviews for the course.
            reviews (list): A list of dictionaries containing all of the
                review data.

        """
        sess, pages = args
        course_info, userpages, reviews = [], {}, []
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
                userpages.update(data[1])
                reviews.extend(data[2])
        return course_info, userpages, reviews

    def get_all_users(self, args):
        """Retrieve all documents for the given list of users.

        Args:
            args (tuple): Tuple containing session number and list of pages.
        Returns:
            users (list): List of dictionaries desribing all of the users in
                pages.

        """
        sess, users, pages = args
        users = []
        with ThreadPoolExecutor(max_workers=2) as extr:
            threads = {
                extr.submit(
                    self.get_user_doc,
                    sess,
                    user,
                    page
                ): page for user, page in zip(users, pages)
            }
            for thread in as_completed(threads):
                user_doc = thread.result()
                users.append(user_doc)
        return users

    def get_all_course_reviews(self, session_num, url):
        """Retrieve all course info, users, and reviews for a given course.

        Function to build the course document. Finds the total number of reivew
        pages and gets reviews from each. Also returns document for course info
        and profile of all users who reviewed the course.

        Args:
            session_num (int): Integer representing which requests.Session to
                use.
            url (string): A string of the main course page.
        Returns:
            course_info (dict): Dictionary of all the course stats and info.
            users (list): A list of dictionaries describing the users who left
                reviews for the course.
            reviews (list): A list of dictionaries containing all of the
                review data.

        """
        session = self.sessions[session_num]
        response = get_response(session, url)
        soup = bs(response.content, 'html.parser')
        course_info = get_course_info(soup, url)
        if not course_info:
            print('Fialed in acquiring {}'.format(url))
            print('Response was: \n{}'.format(response.content))
            raise ConnectionError()
        userpages, reviews = {}, []
        pages = check_pages(soup)
        for i in range(1, pages + 1):
            page = url + '?page={}'.format(i)
            new_userpages, new_reviews = self.get_course_reviews(
                page,
                session_num,
                course_info['Name']
            )
            userpages.update(new_userpages)
            reviews.extend(new_reviews)
        return course_info, userpages, reviews

    def get_user_doc(self, session_num, username, url):
        """Get the user document from a user's profile page.

        Args:
            session_num (int): Integer representing which requests.Session to
                use.
            username (string): The username for the userpage to collect.
            url (string): The url for the user's profile page.
        Returns:
            user_doc (dict): A dictionary containing all user attributes.

        """
        session = self.sessions[session_num]
        response = get_response(session, 'http://www.golfadvisor.com' + url)
        soup = bs(response.content, 'html.parser')
        user_info = soup.find(class_='profile-top-part')
        location = user_info.find(class_='profile-location')
        if location:
            location = location.text.strip()
        atts = [
            span_item.text.strip('\xa0: ')
            for item in user_info.find_all('li')
            for span_item in item.find_all('span')
        ]
        user_doc = {key: value for (key, value) in zip(atts[::2], atts[1::2])}
        if location:
            user_doc.update({'Location': location, 'Username': username})
        else:
            user_doc.update({'Username': username})
        user_doc.update({'Userpage': url})
        return user_doc

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
        response = get_response(session, url)
        soup = bs(response.content, 'html.parser')
        reviews = soup.find_all(itemprop='review')
        userpages = {}
        cleaned_reviews = []
        for review in reviews:
            user = parse_user_info(review)
            if user.get('Userpage'):
                userpages[user] = user['Userpage']
            cleaned_review = parse_review(review)
            cleaned_review['User'] = user
            cleaned_review['Course Name'] = name
            cleaned_review['GA Url'] = url
            ga_id = int(url.split('-')[0].split('/')[-1])
            cleaned_review['GA Id'] = ga_id
            cleaned_reviews.append(cleaned_review)
        return userpages, cleaned_reviews

    def write_documents(self, dbase, collection, docs, filter_):
        """Write documents to a mongodb collection.

        Args:
            dbase (string): The name of the database to insert documents into.
            collection (string): Name of the collection where updates will be
                written.
            documents (list of dict): A list of dictionaries (documents) to
                insert into the collection.
            filter_ (string): String representing the name of the field to use
                as a filter.

        """
        updates = []
        coll = dbase[collection]
        if filter_ == 'GA Id':
            docs = get_new_docs('GA Id', coll, docs)
            if docs:
                updates = self.make_updates(docs, dbase, collection, filter_)
        elif filter_ == 'Username':
            docs = get_new_docs('Username', coll, docs)
            if docs:
                updates = self.make_updates(docs, dbase, collection, filter_)
        else:
            docs = get_new_docs('Review Id', coll, docs)
            if docs:
                updates = self.make_updates(docs, dbase, collection, filter_)
        if updates:
            coll.bulk_write(updates)

    def make_updates(self, docs, dbase, coll, filter_):
        """Construct all of the updates for the given documents.

        Given a tuple of documents, a database, a collection name, and a filter
        construct and return a list of UpdateOne objects for each document.

        Args:
            docs (tuple): Tuple of documents to create updates for.
            dbase (pymongo.database.Database): Database where Counter
                collection is stored.
            coll (string): Name of the collection where updates will be
                written.
            filter_ (string): String representing the name of the field to use
                as a filter.
        Returns:
            updates (list): List of UpdateOne objects to be used in a
                bulk_write operation.

        """
        update_keys = {
            'Users': 'User Id',
            'Courses': 'Course Id',
            'Reviews': 'Review Id2'
        }
        next_id = partial(self.get_next_sequence, dbase)
        updates = []
        for doc in docs:
            id_ = next_id(coll)
            update = make_mongo_update(doc, filter_, update_keys[coll], id_)
            updates.append(update)
        return updates

    @staticmethod
    def get_next_sequence(database, name):
        """Get the next unique id for a new item in a given collection.

        Args:
            name (string): Name of the collection to retrieve the next unique
            id for.
        Returns:
            next_id (int): Integer value for the next unique id to use.

        """
        counters = database.Counter
        seq_doc = counters.find_and_modify({'_id': name}, {'$inc': {'seq': 1}})
        next_id = int(seq_doc['seq'])
        return next_id
