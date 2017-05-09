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

from .utils import (check_pages, get_extras, get_key_info, get_layout,
                    get_tee_info, parse_address, parse_review, parse_user_info)

POOL_SIZE = cpu_count()


class DataHandler(object):

    """
    Class for collecting and writing data for GolfRecs.

    The DataHandler is capable of collecting data for courses. That is all
    course specific stats and info as well as a collection of all reviews,
    and the info for the users who wrote them.
    """

    def __init__(self, links, sessions):
        """
        Extract all data from HTML for course, users, and reviews.

        Args:
            soup (bs4.BeautifulSoup): BeautifulSoup instance of html from a
                course page.
        """
        self.courses = links
        self.sessions = sessions

    def get_reviews(self):
        """
        Collect data for all links in self.courses.

        Returns:
            course_info (list): A list of dictionaries describing all the
                courses in pages.
            users (list): A list of dictionaries describing the users who left
                reviews for the course.
            reviews (list): A list of dictionaries containing all of the
                review data.
        """
        links_lists = array_split(array(self.courses), POOL_SIZE - 1)
        with ProcessPoolExecutor() as extr:
            results = extr.map(
                self.get_all_courses,
                enumerate(links_lists)
            )
        course_info, users, reviews = [], [], []
        for result in results:
            course_info.extend(result[0])
            users.extend(result[1])
            reviews.extend(result[2])
        return course_info, users, reviews

    def get_all_courses(self, args):
        """
        Retrieve all documents for the given list of courses.

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
        with ThreadPoolExecutor() as extr:
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
        """
        Retrieve all course info, users, and reviews for a given course.

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
        response = session.get(url)
        soup = bs(response.content, 'html.parser')
        course_info = self._get_course_info(soup, url)
        if not course_info:
            return None, None, None
        users = []
        reviews = []
        pages = check_pages(soup)
        for i in range(1, pages + 1):
            page = url + '?page={}'.format(i)
            new_users, new_reviews = self.get_course_reviews(
                page,
                session_num
            )
            users.extend(new_users)
            reviews.extend(new_reviews)
        return course_info, users, reviews

    def _get_course_info(self, soup, url):
        """
        Create a document for a golf course, including course stats and info.

        Args:
            soup (bs4.BeautifulSoup): BeautifulSoup instance containing html
                for the main course page.
            url (string): The address of the main course page.
        Returns:
            course_doc (dict): Dictionary containing the course stats and info.
        """
        course_doc = {}
        course_doc['GA_Url'] = url
        course_doc['Course_Id'] = self.courses.index(url)
        course_doc['Name'] = soup.find(itemprop='name').text
        course_doc['Layout'] = get_layout(soup)
        course_doc.update(parse_address(soup))
        course_doc.update(get_key_info(soup))
        course_doc['Tees'] = get_tee_info(soup)
        course_doc.update(get_extras(soup))
        return course_doc

    def get_course_reviews(self, url, session_num):
        """
        Parse all reviews on a single page.

        Args:
            url (string): Page address from which to retrieve reviews.
            session_num (int): Integer representing which requests.Session to
                use.
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
            users.append(parse_user_info(review))
            cleaned_reviews.append(parse_review(review))
        return users, cleaned_reviews
