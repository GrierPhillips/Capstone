"""Module for collecting data from GolfAdvisor.com.

This module contains methods for collecting user reviews of golf courses, as
well as course statistics, information, and user information.
"""

from concurrent.futures import (ThreadPoolExecutor, ProcessPoolExecutor,
                                as_completed)
from os import cpu_count

from lxml import etree
from numpy import array, array_split
import requests

from .data_handler import DataHandler
from .utils import renew_connection

POOL_SIZE = cpu_count()


class DataCollector(object):
    """Class containing methods for scraping information from GolfAdvisor.com.

    The DataCollector class is the main controller for all activities relating
    to the backend of collecting, storing, and updating data for the GolfRecs
    predictive model.

    Attributes:
        courses (numpy.ndarray): A NumPy array containing urls for courses.
        sessions (list of requests.sessions.Session): A list of requests
            sessions that are setup for making requests from multiple IP
            addresses.

    """

    def __init__(self):
        """Set up the GolfRecs class.

        The DataCollector class leverages tor and requests to construct an
        array of requests.Session objects that all utlize a different IP
        address to make requests. This method sets up these objects and sets
        their proxies accordingly.
        """
        self.courses = None
        self.sessions = []
        self._setup_sessions()

    def _setup_sessions(self):
        """Set up as many requests Sessions as there are cores available."""
        for _ in range(POOL_SIZE):
            self.sessions.append(requests.Session())
        self._setup_proxies()

    def _setup_proxies(self):
        """Set up proxies for all sessions."""
        all_proxies = [9050] + list(range(9052, 9052 + POOL_SIZE - 1))
        for index, session in enumerate(self.sessions):
            proxy = all_proxies[index]
            proxies = {
                'http': 'socks5://127.0.0.1:{}'.format(proxy),
                'https': 'socks5://127.0.0.1:{}'.format(proxy)
            }
            setattr(session, 'proxies', proxies)

    def get_courses(self):
        """Collect course links from golfadvisor.

        GolfAdvisor stores courses and their links in xml format with 1000
        courses per page at golfadvisor.com/sitemap_courses-#.xml where # is
        replaced with an integer starting at 1. As of last update there were
        34 pages containing courses.
        """
        sitemap = 'http://www.golfadvisor.com/sitemap_courses-#.xml'
        pages = array(
            [sitemap.replace('#', str(index)) for index in range(1, 35)]
        )
        page_lists = array_split(pages, POOL_SIZE)
        with ProcessPoolExecutor() as extr:
            results = extr.map(self._get_course_pages, enumerate(page_lists))
        courses = array([link for links in results for link in links])
        self.courses = courses

    def _get_course_pages(self, args):
        """Distribute calls to collect individual pages to multliple threads.

        Given a list of pages to collect, spread out the requests to multliple
        threads to improve performance.
        """
        sess, pages = args
        courses = []
        with ThreadPoolExecutor() as extr:
            threads = {
                extr.submit(self._get_page, sess, page): page for page in pages
            }
            for thread in as_completed(threads):
                data = thread.result()
                courses.extend(data)
        return courses

    def _get_page(self, session_num, page):
        """Collect all courses from a given page.

        Given a page url retrieve the xml, and parse out all of the course
        links.

        Args:
            page (string): A url for the sitemap page containing course links.
            session_num (int): Integer representing the session number to use
                for making requests.
        """
        session = self.sessions[session_num]
        response = session.get(page)
        xml = etree.fromstring(response.content)  # pylint: disable=E1101
        course_links = [course.text for course in xml.iter('{*}loc')]
        return course_links

    def get_reviews(self):
        """Collect data for all links in self.courses and store it in MongoDB.

        Once self.courses in populated with a list of links, this method will
        distribute the links among multiple processes to collect the reviews,
        users, and course info for each page of reviews.
        """
        if self.courses.size < 1:
            raise Exception(
                "No links exist for retrieving reviews. Either call " +
                "self.get_courses() or set self.courses equal to a list " +
                "of courses you wish to process."
            )

        courses_lists = array_split(
            self.courses,
            self.courses.size // (POOL_SIZE * 10)
        )
        for courses in courses_lists:
            handler = DataHandler(courses, self.sessions)
            try:
                results = handler.get_reviews()
                renew_connection()
            except Exception as err:  # pylint: disable=W0703
                print('Exception Occurred: {}'.format(err))
                renew_connection()
                results = handler.get_reviews()
            collections = ['Courses', 'Users', 'Reviews']
            filters = ['GA Id', 'Username', 'Review Id']
            for args in zip(collections, results, filters):
                handler.write_documents(*args)
