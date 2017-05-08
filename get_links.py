"""
Module for collecting data from GolfAdvisor.com.

This module contains methods for collecting user reviews of golf courses, as
well as course statistics, information, and user information.
"""
# import requesocks
# import boto3
# from boto3.dynamodb.conditions import Key, Attr
# from ItemItemRecommender import ItemItemRecommender
# from stem import Signal
# from stem.control import Controller

from decimal import Decimal
import json
from math import ceil
import multiprocessing as mp
import os
import pickle as pickle
import threading
from urllib.parse import urljoin
import sys

from bs4 import BeautifulSoup as bs
from lxml import etree
import numpy as np
import requests
from scipy import sparse

POOL_SIZE = mp.cpu_count()


class GolfAdvisor(object):
    """
    Class containing methods for scraping information from GolfAdvisor.com.
    """
    def __init__(self, courses=None):
        self.sessions = []
        self.setup_sessions()
        self.courses = courses

    def setup_sessions(self):
        """Setup as many requests Sessions as there are cores available."""
        for _ in range(40):
            self.sessions.append(requests.Session())
        self._setup_proxies()

    def _setup_proxies(self):
        """Setup proxies for all sessions."""
        all_proxies = [9050] + list(range(9052, 9091))
        for index, session in enumerate(self.sessions):
            proxy = all_proxies[index]
            proxies = {
                'http': 'socks5://127.0.0.1:{}'.format(proxy),
                'https': 'socks5://127.0.0.1:{}'.format(proxy)
            }
            setattr(session, 'proxies', proxies)

    def get_courses(self):
        """
        Collect course links from golfadvisor.

        GolfAdvisor stores courses and their links in xml format with 1000
        courses per page at golfadvisor.com/sitemap_courses-#.xml where # is
        replaced with an integer starting at 1. As of last update there were
        34 pages containing courses.

        Returns:
            course_links (list): A list of urls for all of the courses
                contained in the sitemap.
        """
        sitemap = 'http://www.golfadvisor.com/sitemap_courses-#.xml'
        pages = np.array(
            [sitemap.replace('#', str(index)) for index in range(1, 35)]
        )
        page_lists = np.array_split(pages, POOL_SIZE)
        pool = mp.Pool()
        results = pool.starmap(
            self._get_course_pages,
            zip(page_lists, range(len(page_lists)))
        )
        pool.close()
        pool.join()
        course_links = [link for links in results for link in links]
        return course_links

    def _get_course_pages(self, pages, session_num):
        """
        Distribute calls to collect individual pages to multliple threads.

        Given a list of pages to collect, spread out the requests to multliple
        threads to improve performance.
        """
        threads = []
        queue = mp.Queue()
        for page in pages:
            thread = threading.Thread(
                target=self._get_courses_page,
                args=(page, session_num, queue)
            )
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()
        queue.put(None)
        course_links = []
        while True:
            result = queue.get()
            if result is None:
                return course_links
            course_links.extend(result)

    def _get_courses_page(self, page, session_num, queue):
        """
        Collect all courses from a given page.

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
        queue.put(course_links)

    def get_all_reviews(self, url, session_num=0):
        """
        Function to build the course document. Finds the total number of reivew
        pages and gets reviews from each.

        Args:
            url (string): A string of the main course page.
        Returns:
            users (list): A list of dictionaries describing the users who left
                reviews for the course.
            reviews (list): A list of dictionaries containing all of the
                review data.
        """
        session = self.sessions[session_num]
        response = session.get(url)
        soup = bs(response.content, 'html.parser')
        course_info = self._get_course_info(soup, url)
        if course_info is None:
            return None, None
        users = []
        reviews = []
        pages = self.check_pages(soup)
        for i in range(1, pages + 1):
            page = url + '?page={}'.format(i)
            new_users, new_reviews = self.get_reviews(page)
            users.extend(new_users)
            reviews.extend(new_reviews)
        return users, reviews

    def get_reviews(self, url, session_num=0):
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

    @staticmethod
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

    def write_to_dynamodb(self, record, table):
        """
        Write to dynamodb using boto3.
        INPUT:
            record: dictionary. course_doc containing keys = ['Course',
                'attributes', 'info', 'more', 'reviews']
            table: boto3 dynamodb table object
        OUTPUT;
            None
        """

        table.put_item(Item=record)

    def get_and_store_reviews(self, course_links, session_num=0):
        """
        Complete pipeline for getting reviews from a list of pages, creating a
        course record in the form of a dictionary (primary key='Course'), and
        storing reviews in Dynamodb.
        INPUT:
            url: list. website addresses for a list of courses
            table: boto3 dynamodb table object
        OUTPUT:
            None
        '''
        for url in urls:
            url = urljoin(self.url, url)
            info, reviews = self.get_all_reviews(url, session_num=session_num)
            if info == None:
                continue
            self.write_to_dynamodb(info, info_table)
            for review in reviews:
                self.users.append(review)
                review = {'Username': review,
                          'Course_Id': self.courses\
                                           .index(url.split('.com')[-1]),
                          'Course': url,
                          'Review': reviews[review]}
                self.write_to_dynamodb(review, review_table)
            print url.split('.com')[-1], "loaded into Dynamo"


    def parallel_scrape_reviews(self, links, info_table, review_table):
        """
        Setup and implement threads for parallel scraping of course reviews and
        writing results to dynamodb.
        INPUT:
            table: boto3 dynamodb table object
        OUTPUT:
            None
        """
        jobs = []
        for i in range(len(self.sessions)):
            thread = threading.Thread(
                name=i,
                target=self.get_and_store_reviews,
                args=(
                    links[i],
                    info_table,
                    review_table,
                    i
                )
            )
            jobs.append(thread)
            thread.start()
        for j in jobs:
            j.join()

    @staticmethod
    def chunks(l, n):
        """Yield successive n-sized chunks from l."""
        for i in range(0, len(l), n):
            yield l[i:i + n]

    def create_users_table(self, reviews_table, users_table):
        users = set()
        for i in range(len(self.courses)):
            response = reviews_table.query(
                KeyConditionExpression=Key('Course_Id').eq(i)
            )
            for item in response['Items']:
                user = item['Username']
                users.add(user)
        self.users = list(users)
        with users_table.batch_writer() as batch:
            for i, user in enumerate(list(self.users)):
                batch.put_item(Item={'User_Id': i, 'Username': user})

    def get_users(self, users_table):
        for i in range(209994):
            response = users_table.query(
                KeyConditionExpression=Key('User_Id').eq(i)
            )
            self.users.append(response['Items'][0]['Username'])
        with open('users.pkl', 'w') as f:
            pickle.dump(self.users, f)

    def get_overall_data(self):
        highest_user_id = len(self.users)
        highest_course_id = len(self.courses)
        self.missing_users = []
        self.ratings_mat = sparse.lil_matrix((highest_user_id, highest_course_id))
        # total_records = review_table.item_count
        self.parallel_query_reviews(self.build_mat, POOL_SIZE)
        # indices = range(len(self.courses))
        # self.multiprocess_build_mat(POOL_SIZE, indices)
        with open('missing_users.pkl', 'w') as f:
            pickle.dump(self.missing_users, f)

    def parallel_query_reviews(self, function, num_cores, *args):
        # import pdb; pdb.set_trace()
        num = int(ceil(len(self.courses) / float(num_cores)))
        links = list(self.chunks(range(len(self.courses)), num))
        jobs = []
        for i in range(num_cores):
            arg = (links[i], ) + tuple(args)
            thread = threading.Thread(name=i,
                                      target=function,
                                      args=arg)
            jobs.append(thread)
            thread.start()
        for j in jobs:
            j.join()

    def parse_course_info(self, indices):
        for i in indices:
            response = self.info_table.get_item(Key={'Course_Id': i})
            item = response['Item']
            new_item = {}
            new_item['Course'] = item['Course']
            new_item['Course_Id'] = item['Course_Id']
            new_item['Name'] = item['Name']
            try:
                soup = bs(item['attributes'], 'html.parser')
            except:
                self.missing_courses.append(i)
            atts = {'Holes': None, 'Par': None, 'Length': None, 'Slope': None, 'Rating': None}
            try:
                for items in soup.find_all('li')[:5]:
                    splits = items.text.split(': ')
                    if splits[0].startswith('\n'):
                        continue
                    elif splits[0] == 'Length':
                        if 'meters' in splits[-1]:
                            atts[splits[0]] = int(round(int(splits[1].split()[0]) * 0.9144))
                        else:
                            atts[splits[0]] = int(splits[1].split()[0])
                    elif splits[0] == 'Rating':
                        atts[splits[0]] = Decimal(splits[1])
                    else:
                        atts[splits[0]] = int(splits[1])
                try:
                    atts['Lattitude'] = soup.find(class_='btn-layout')['data-course-lat']
                    atts['Longitude'] = soup.find(class_='btn-layout')['data-course-lng']
                except:
                    atts['Lattitude'] = None
                    atts['Longitude'] = None
                new_item.update(atts)
            except:
                self.missing_courses.append(i)
            try:
                soup = bs(item['info'], 'html.parser')
                address_item = {'Address': None,
                                'City': None,
                                'State': None,
                                'Postal_Code': None,
                                'Country': None,
                                 'Phone': None,
                                 'Website': None,
                                 'Images': None,
                                 'Built': None,
                                 'Type': None,
                                 'Season': None}
                try:
                    address = soup.find_all(class_='address')
                    add_atts = ['Address', 'City', 'State', 'Postal_Code', 'Country']
                    for j, line in enumerate(address):
                        if j == 0:
                            line = line.text.split(',')[0]
                            address_item[add_atts[j]] = line
                        elif line.text == '':
                            continue
                        else:
                            address_item[add_atts[j]] = line.text
                    # print address_item
                except:
                    address = None
                try:
                    phone = soup.find(itemprop='telephone').text
                    if phone == '':
                        phone = None
                    address_item['Phone'] = phone
                except:
                    phone = None
                try:
                    website = soup.find(itemprop='sameAs').text
                    if website == '':
                        website = None
                    address_item['Website'] = website
                except:
                    website = None
                try:
                    image_links = []
                    images = soup.find_all('script')
                    for image in images:
                        url = json.loads(image.text)['contentUrl']
                        image_links.append(url)
                    if image_links == []:
                        image_links = None
                    address_item['Images'] = image_links
                except:
                    image_links = None
                try:
                    divs = soup.find_all('div')
                    for j in range(-5, 0):
                        try:
                            class_ = divs[j]['class']
                        except:
                            class_ = 'None'
                        if class_ != 'more-info-icon':
                            continue
                        elif class_ == 'None':
                            splits = divs[j].text.split(': ')
                            if splits[0] == 'Built':
                                address_item[splits[0]] = int(splits[1])
                            else:
                                address_item[splits[0]] = splits[1]
                except:
                    divs = None
                new_item.update(address_item)
            except:
                self.missing_courses.append(i)
            print('Course ', i, 'successfully parsed')
            # try:
            #     soup = bs(item['more'], 'html.parser')
            #     more_info = {'Carts': None,
            #                  'Pull-carts': None,
            #                  'Clubs': None,
            #                  'Caddies': None,
            #                  'GPS': None,
            #                  'Practice Instruction'
            #                  'Driving range': None,
            #                  'Pitching_chipping area': None,
            #                  'Putting green': None,
            #                  'Practice bunker': None,
            #                  'Simulator': None,
            #                  'Teaching pro': None,
            #                  'Golf schoolacademy': None,
            #                  'Walking': None,
            #                  'Spikes': None,
            #                  'Credit Cards': None,
            #                  'Dress_Code': None}
            #     more = soup.find_all('div')
            #     for item in more[3:6]:
            #         sub_item = item.spit(': ')
            #         more_info[sub_item[0]] = sub_item[1]
            #     for item in more[7:13]:
            #         sub_item = item.split(': ')
            #         more_info[sub_item[0]] = sub_item[1]
            #     for item in more[14:17]:
            #         sub_item = item.split(': ')
            #         more_info[sub_item[0]] = sub_item[1]
            #     new_item.update(more_info)
            # except:
            #     self.missing_courses.append(i)
            self.course_table.put_item(Item=new_item)
            # except:
            #     print '\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\nCourse' ,i, 'Failed\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n'


    def build_mat(self, indices):
        for i in indices:
            print('Course index ', i, 'processed into ratings_mat')
            response = self.review_table.query(KeyConditionExpression=Key('Course_Id').eq(i))
            ratings = []
            users = []
            for item in response['Items']:
                rating = item['Rating']
                ratings.append(rating)
                try:
                    users.append(self.users.index(item['Username']))
                except:
                    self.missing_users.append(item['Username'])
            for user, rating in zip(users, ratings):
                self.ratings_mat[user, i] = rating

    def check_missing(self, info_table):
        missing_course_ids = []
        for i in range(len(self.courses)):
            response = info_table.query(
                KeyConditionExpression=Key('Course_Id').eq(i)
            )
            if response['Count'] == 0:
                missing_course_ids.append(i)
        return missing_course_ids

    def check_missing_exists(self, courses, session_num=0):
        for course in courses:
            url = urljoin(self.url, course)
            html = self.get_site(url, session_num=session_num)
            soup = bs(html, 'html.parser')
            try:
                exists = soup.find(class_='container simple-page-wrapper').h1.text
            except:
                continue
            if exists == 'Page not found':
                new_course = self.fill_result_from_google(url, course, session_num=session_num)
                self.missing_courses[self.missing_courses.index(course)] = new_course
                self.courses[self.courses.index(course)] = new_course

    def parallel_missing(self, n):
        links = list(self.chunks(self.missing_courses, n))
        jobs = []
        for i in range(len(self.sessions)):
            thread = threading.Thread(name=i,
                                      target=self.check_missing_exists,
                                      args=(links[i], i))
            jobs.append(thread)
            thread.start()
        for j in jobs:
            j.join()

    def fill_result_from_google(self, url, course, session_num=0):
        api_key = os.environ['GOOGLE_API_KEY']
        cse_id = os.environ['GOOGLE_CSE_ID']
        search_term = ' '.join(url.split('courses/')[1].split('-')[1:])
        html = self.get_site('https://www.googleapis.com/customsearch/v1?key={}&cx={}&q={}'.format(api_key, cse_id, search_term), session_num=session_num)
        results = json.loads(html)
        for result in results['items']:
            link = result['link']
            if link.split('.com')[-1] == course:
                continue
            elif link.split('.com')[-1] in courses:
                continue
            return link.split('.com')[-1]

    def parse_reviews(self, indices):
        self.error_items = {}

        for i in indices:
            print('Course index', i, 'html parsed.')
            response = self.review_table.query(KeyConditionExpression=Key('Course_Id').eq(i))
            items = response['Items']
            while 'LastEvaluatedKey' in response.keys():
                response = self.review_table.query(
                    KeyConditionExpression=Key('Course_Id').eq(i),
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items += response['Items']
            for item in items:
                try:
                    parsed = item['Rating']
                except:
                    soup = bs(item['Review'], 'html.parser')
                    try:
                        review_id = int(soup.div.div['id'].split('-')[-1])
                    except:
                        review_id = None
                        error_items[i] = item
                    text = soup.span.text
                    text += ' '.join(soup.find(itemprop='reviewBody')\
                        .text.strip().split('\n'))
                    # import pdb; pdb.set_trace()
                    try:
                        user_id = self.users.index(item['Username'])
                        user_item = {'Username': item['Username'], 'User_Id': user_id}
                    except:
                        self.users.append(item['Username'])
                        user_id = self.users.index(item['Username'])
                    try:
                        age = soup.find(class_='context-value Age').text
                    except:
                        age = None
                    try:
                        gen = soup.find(class_='context-value Gender').text
                    except:
                        gen = None
                    try:
                        skill = soup.find(class_='context-value SkillLevel').text
                    except:
                        skill = None
                    try:
                        plays = soup.find(class_='context-value PlayFrequency').text
                    except:
                        plays = None
                    try:
                        hdcp = soup.find(class_='context-value Handicap').text
                    except:
                        hdcp = None
                    rating = soup.find(itemprop='ratingValue').text
                    try:
                        played = soup.find(class_='review-play-date').text.split()[-1]
                    except: None
                    try:
                        prev_played = soup.find(class_='label label-default context-value-standalone FirstTime').text
                    except:
                        prev_played = None
                    try:
                        walk = soup.find(class_='label label-default context-value-standalone WalkOrRide').text
                    except:
                        walk = None
                    try:
                        holes = soup.find(class_="label label-default context-value-standalone 9HoleGame").text
                    except:
                        holes = None
                    try:
                        weather = soup.find(class_="label label-default context-value-standalone Weather").text
                    except:
                        weather = None
                    try:
                        pace = soup.find(class_="sec-rating-value Pace").text.strip()
                    except:
                        pace = None
                    try:
                        layout = soup.find(class_="sec-rating-value CourseLayout").text.strip()
                    except:
                        layout = None
                    try:
                        conditions = soup.find(class_="sec-rating-value CourseConditions").text.strip()
                    except:
                        conditions = None
                    try:
                        staff = soup.find(class_="sec-rating-value StaffFriendliness").text.strip()
                    except:
                        staff = None
                    try:
                        value = soup.find(class_="sec-rating-value ValueForTheMoney").text.strip()
                    except:
                        value = None
                    try:
                        amenities = soup.find(class_="sec-rating-value OverallFacilitiesCondition").text.strip()
                    except:
                        amenities = None
                    try:
                        difficulty = soup.find(class_="context-value CourseDifficulty").text
                    except:
                        difficulty = None
                    try:
                        recommend = soup.find(class_="review-recommend-yes review-recommend col-xs-12").p.text
                    except:
                        recommend = None
                    positive = int(soup.find(class_="btn btn-link submit-feedback-link submit-review-positive-feedback-link").span.text)
                    negative = int(soup.find(class_="btn btn-link submit-feedback-link submit-review-negative-feedback-link").span.text)
                    self.review_table.update_item(
                        Key={
                             'Course_Id': i,
                             'Username': item['Username']
                        },
                        UpdateExpression="set Review_Id = :rid, Review = :rev, User_Id = :uid, Rating = :rat, Date_Played = :dp, Previously_Played = :pp, Walk_Or_Ride = :wor, Holes = :h, Weather = :w, Pace_of_Play = :pop, Course_Layout = :cl, Course_Conditions = :cc, Staff_Friendliness = :sf, Value_for_the_Money = :vfm, Amenieites = :am, Course_Difficulty = :cd, Recommendation = :rec, Positive_Feedback = :pos, Negative_Feedback = :neg",
                        ExpressionAttributeValues={
                            ':rid': review_id,
                            ':rev': text,
                            ':uid': user_id,
                            ':rat': rating,
                            ':dp': played,
                            ':pp': prev_played,
                            ':wor': walk,
                            ':h': holes,
                            ':w': weather,
                            ':pop': pace,
                            ':cl': layout,
                            ':cc': conditions,
                            ':sf': staff,
                            ':vfm': value,
                            ':am': amenities,
                            ':cd': difficulty,
                            ':rec': recommend,
                            ':pos': positive,
                            ':neg': negative}
                    )
                    # self.user_table.update_item(
                    #     Key={
                    #          'User_Id': user_id
                    #     },
                    #     UpdateExpression="set Age = :a, Gender = :g, Skill = :s, Plays = :p, Handicap = :h",
                    #     ExpressionAttributeValues={
                    #         ':a': age,
                    #         ':g': gen,
                    #         ':s': skill,
                    #         ':p': plays,
                    #         ':h': hdcp
                    #     }
                    # )
                    user_atts = {'Age': age, 'Gender': gen, 'Skill': skill, 'Plays': plays, 'Handicap': hdcp}
                    user_item.update(user_atts)
                    self.user_table.put_item(Item=user_item)


if __name__ == '__main__':
    def load_courses():
        with open('course_links.pkl', 'r') as f:
            return list(pickle.load(f))

    def load_users():
        with open('users.pkl', 'r') as f:
            return list(pickle.load(f))

    def load_ratings_mat():
        with open('ratings_mat.pkl', 'r') as f:
            return pickle.load(f)



    ddb = boto3.resource('dynamodb', region_name='us-west-2')
    info_table = ddb.Table('Courses_Info')
    review_table = ddb.Table('Course_Reviews_Raw')
    read_table = ddb.Table('Scrape_Status')
    users_table = ddb.Table('Users')
    course_table = ddb.Table('Courses')
    if len(sys.argv) == 1:
        if not os.path.exists('course_links.pkl'):
            ga = GolfAdvisor()
            courses = ga.get_courses()
            with open('course_links.pkl', 'w') as f:
                pickle.dump(courses, f)
        else:
            ga = GolfAdvisor(load_courses())
            n = int(math.ceil(len(courses) / 20.))
            links = list(ga.chunks(ga.courses, n))
            ga.parallel_scrape_reviews(links, info_table, review_table)
    else:
        if sys.argv[1] == 'missing':
            ga = GolfAdvisor(load_courses())
            missing_courses = ga.check_missing(info_table)
            links = [ga.courses[x] for x in missing_courses]
            if len(links) < 20:
                ga.get_and_store_reviews(links, info_table, review_table)
                ga.check_missing_exists(ga.missing_courses)
                missing_links = ga.missing_courses
                ga.get_and_store_reviews(missing_links,
                                         info_table,
                                         review_table)
            else:
                n = int(math.ceil(len(links) / 20.))
                links = list(ga.chunks(links, n))
                ga.parallel_scrape_reviews(links, info_table, review_table)
                ga.parallel_missing(n)
                missing_links = ga.missing_courses
                missing_links = list(ga.chunks(missing_links, n))
                ga.parallel_scrape_reviews(missing_links,
                                           info_table,
                                           review_table)
            with open('missing_courses.pkl', 'w') as f:
                pickle.dump(ga.missing_courses, f)
            with open('course_links.pkl', 'w') as f:
                pickle.dump(ga.courses, f)
        elif sys.argv[1] == 'model':
            ga = GolfAdvisor(load_courses(), load_users(), ratings_mat=load_ratings_mat(), review_table=review_table)
            recommender = ItemItemRecommender(neighborhood_size=75)
            # ga.get_overall_data()
            with open('ratings_mat.pkl', 'w') as f:
                pickle.dump(ga.ratings_mat, f)
            recommender.fit(ga.ratings_mat)
            with open('recommender.pkl', 'w') as f:
                pickle.dump(recommender, f)
        elif sys.argv[1] == 'parse':
            ga = GolfAdvisor(load_courses(), load_users(), review_table=review_table, user_table=users_table)
            ga.parallel_query_reviews(ga.parse_reviews, POOL_SIZE)
            with open('errors.pkl', 'w') as f:
                pickle.dump(ga.error_items, f)
            with open('users2.pkl', 'w') as f:
                pickle.dump(ga.users, f)
        elif sys.argv[1] == 'parse_courses':
            ga = GolfAdvisor(load_courses(), load_users(), info_table=info_table, course_table=course_table)
            ga.parallel_query_reviews(ga.parse_course_info, POOL_SIZE)
            with open('missing_course_info.pkl', 'w') as f:
                pickle.dump(ga.missing_courses, f)

    # TODO: Implement test train split on ratings_mat using df.unstack().reset_index()
    # load matrix into pandas and change the names of the indices to user and course.
    # then call df.unstack().reset_index() to return user, course, rating matrix.
    # Finally drop nan values with df.drop(df[pd.isnull(df['rating'])].index)
