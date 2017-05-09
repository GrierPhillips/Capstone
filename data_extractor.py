"""
Module for parsing course pages from GolfAdvisor.com

This module contains methods for collecting course info, users, and reviews
from a given list of courses on the GolfAdvisor domain.
"""
from concurrent.futures import (ProcessPoolExecutor, ThreadPoolExecutor,
                                as_completed)
from math import ceil
from os import cpu_count

from bs4 import BeautifulSoup as bs
from numpy import array, array_split

POOL_SIZE = cpu_count()


class DataExtractor(object):
    """
    Extract all data from HTML for course, users, and reviews.

    Args:
        soup (bs4.BeautifulSoup): BeautifulSoup instance of html from a course
            page.
    """

    def __init__(self, links, sessions):
        self.courses = links
        self.sessions = sessions

    def get_reviews(self):
        """
        Collect reviews for all links in self.courses.

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
                self._get_all,
                enumerate(links_lists)
            )
        course_info, users, reviews = [], [], []
        for result in results:
            course_info.extend(result[0])
            users.extend(result[1])
            reviews.extend(result[2])
        return course_info, users, reviews

    def _get_all(self, args):
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
                    self._get_all_course_reviews,
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

    def _get_all_course_reviews(self, session_num, url):
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
        pages = self._check_pages(soup)
        for i in range(1, pages + 1):
            page = url + '?page={}'.format(i)
            new_users, new_reviews = self.get_course_reviews(page)
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
        course_doc['Layout'] = self._get_layout(soup)
        course_doc.update(self._parse_address(soup))
        course_doc.update(self._get_key_info(soup))
        course_doc['Tees'] = self._get_tee_info(soup)
        course_doc.update(self._get_extras(soup))
        return course_doc

    @staticmethod
    def _get_extras(soup):
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

    @staticmethod
    def _get_tee_info(soup):
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

    @staticmethod
    def _get_key_info(soup):
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

    @staticmethod
    def _parse_address(soup):
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

    @staticmethod
    def _get_layout(soup):
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

    def get_course_reviews(self, url, session_num=0):
        """
        Parse all reviews on a single page.

        Args:
            url (string): Page address from which to retrieve reviews.
        Returns:
            clearned_reviews (list): List of cleaned reviews stored as
                dictionaries.
            users (list): List of users stored as dictionaries.
        """
        session = self.sessions[session_num]
        response = session.get(url)
        soup = bs(response.content, 'html.parser')
        reviews = soup.find_all(itemprop='review')
        users = []
        cleaned_reviews = []
        for review in reviews:
            users.append(self._parse_user_info(review))
            cleaned_reviews.append(self._parse_review(review))
        return users, reviews

    @staticmethod
    def _parse_review(review):
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

    @staticmethod
    def _parse_user_info(review):
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

    @staticmethod
    def _check_pages(soup):
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
