"""
Module for collecting data from GolfAdvisor.com.

This module contains methods for collecting user reviews of golf courses, as
well as course statistics, information, and user information.
"""
# import boto3
# from boto3.dynamodb.conditions import Key, Attr
# from ItemItemRecommender import ItemItemRecommender

# from decimal import Decimal
# import json
from concurrent.futures import (ThreadPoolExecutor, ProcessPoolExecutor,
                                as_completed)
# from math import ceil
from os import cpu_count
# import os
# import pickle as pickle
# from urllib.parse import urljoin
# import sys

from lxml import etree
import numpy as np
import requests
# from scipy import sparse

from .data_handler import DataHandler


POOL_SIZE = cpu_count()


class GolfAdvisor(object):
    """
    Class containing methods for scraping information from GolfAdvisor.com.
    """
    def __init__(self, courses=None):
        self.sessions = []
        self._setup_sessions()
        self.courses = courses

    def _setup_sessions(self):
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
        with ProcessPoolExecutor() as extr:
            results = extr.map(self._get_course_pages, enumerate(page_lists))
        courses = [link for links in results for link in links]
        self.courses = courses

    def _get_course_pages(self, args):
        """
        Distribute calls to collect individual pages to multliple threads.

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
        return course_links

    def get_reviews(self):
        """
        Collect data for all links in self.courses.

        Once self.courses in populated with a list of links, this method will
        distribute the links among multiple processes to collect the reviews,
        users, and course info for each page of reviews.
        """
        if not self.courses:
            raise Exception(
                "No links exist for retrieving reviews. Either call " +
                "self.get_courses() or set self.courses equal to a list " +
                "of courses you wish to process."
            )
        handler = DataHandler(np.array(self.courses), self.sessions)
        course_info, users, reviews = handler.get_reviews()

    @staticmethod
    def write_to_dynamodb(record, table):
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
    #
    # def get_and_store_reviews(self, course_links, session_num=0):
    #     """
    #     Complete pipeline for getting reviews from a list of pages, creating a
    #     course record in the form of a dictionary (primary key='Course'), and
    #     storing reviews in Dynamodb.
    #     INPUT:
    #         url: list. website addresses for a list of courses
    #         table: boto3 dynamodb table object
    #     OUTPUT:
    #         None
    #     """
    #     for course in course_links:
    #         info, reviews = self.get_all_reviews(
    #             course,
    #             session_num=session_num
    #         )
    #         if info is None:
    #             continue
    #         # self.write_to_dynamodb(info, info_table)
    #         # TODO: create write_to_mongo method.
    #         for review in reviews:
    #             # self.users.append(review)
    #             review = {'Username': review,
    #                       'Course_Id': self.courses.index(course),
    #                       'Course': course,
    #                       'Review': reviews[review]}
    #             # self.write_to_dynamodb(review, review_table)
    #             # TODO: Again needs write_to_mongo method.
    #         print(course.split('.com')[-1], "loaded into Dynamo")
    #
    # def parallel_scrape_reviews(self, links, info_table, review_table):
    #     """
    #     Setup and implement threads for parallel scraping of course reviews and
    #     writing results to dynamodb.
    #     INPUT:
    #         table: boto3 dynamodb table object
    #     OUTPUT:
    #         None
    #     """
    #     jobs = []
    #     for i in range(len(self.sessions)):
    #         thread = threading.Thread(
    #             name=i,
    #             target=self.get_and_store_reviews,
    #             args=(
    #                 links[i],
    #                 info_table,
    #                 review_table,
    #                 i
    #             )
    #         )
    #         jobs.append(thread)
    #         thread.start()
    #     for j in jobs:
    #         j.join()
    #
    # @staticmethod
    # def chunks(list_, num):
    #     """
    #     Split a list into at most num chunks.
    #
    #     Args:
    #         list_ (list): A list to separate into chunks.
    #         num (int): Number of chunks to split list_.
    #     """
    #     chunk_size = ceil(len(list_) / num)
    #     for i in range(0, len(list_), chunk_size):
    #         yield list_[i:i + num]

    # def create_users_table(self, reviews_table, users_table):
    #     users = set()
    #     for i in range(len(self.courses)):
    #         response = reviews_table.query(
    #             KeyConditionExpression=Key('Course_Id').eq(i)
    #         )
    #         for item in response['Items']:
    #             user = item['Username']
    #             users.add(user)
    #     self.users = list(users)
    #     with users_table.batch_writer() as batch:
    #         for i, user in enumerate(list(self.users)):
    #             batch.put_item(Item={'User_Id': i, 'Username': user})
    #
    # def get_users(self, users_table):
    #     for i in range(209994):
    #         response = users_table.query(
    #             KeyConditionExpression=Key('User_Id').eq(i)
    #         )
    #         self.users.append(response['Items'][0]['Username'])
    #     with open('users.pkl', 'w') as f:
    #         pickle.dump(self.users, f)
    #
    # def get_overall_data(self):
    #     highest_user_id = len(self.users)
    #     highest_course_id = len(self.courses)
    #     self.missing_users = []
    #    self.ratings_mat = sparse.lil_matrix(
    #         (highest_user_id, highest_course_id)
    #    )
    #     # total_records = review_table.item_count
    #     self.parallel_query_reviews(self.build_mat, POOL_SIZE)
    #     # indices = range(len(self.courses))
    #     # self.multiprocess_build_mat(POOL_SIZE, indices)
    #     with open('missing_users.pkl', 'w') as f:
    #         pickle.dump(self.missing_users, f)

    # def parallel_query_reviews(self, function, num_cores, *args):
    #     # import pdb; pdb.set_trace()
    #     num = int(ceil(len(self.courses) / float(num_cores)))
    #     links = list(self.chunks(range(len(self.courses)), num))
    #     jobs = []
    #     for i in range(num_cores):
    #         arg = (links[i], ) + tuple(args)
    #         thread = threading.Thread(name=i,
    #                                   target=function,
    #                                   args=arg)
    #         jobs.append(thread)
    #         thread.start()
    #     for j in jobs:
    #         j.join()

    # def parse_course_info(self, indices):
    #     for i in indices:
    #         response = self.info_table.get_item(Key={'Course_Id': i})
    #         item = response['Item']
    #         new_item = {}
    #         new_item['Course'] = item['Course']
    #         new_item['Course_Id'] = item['Course_Id']
    #         new_item['Name'] = item['Name']
    #         try:
    #             soup = bs(item['attributes'], 'html.parser')
    #         except:
    #             self.missing_courses.append(i)
    #         atts = {
    #             'Holes': None,
    #             'Par': None,
    #             'Length': None,
    #             'Slope': None,
    #             'Rating': None
    #         }
    #         try:
    #             for items in soup.find_all('li')[:5]:
    #                 splits = items.text.split(': ')
    #                 if splits[0].startswith('\n'):
    #                     continue
    #                 elif splits[0] == 'Length':
    #                     if 'meters' in splits[-1]:
    #                         atts[splits[0]] = int(
    #                             round(int(splits[1].split()[0]) * 0.9144)
    #                         )
    #                     else:
    #                         atts[splits[0]] = int(splits[1].split()[0])
    #                 elif splits[0] == 'Rating':
    #                     atts[splits[0]] = Decimal(splits[1])
    #                 else:
    #                     atts[splits[0]] = int(splits[1])
    #             try:
    #                 atts['Lattitude'] = soup.find(class_='btn-layout')[
    #                     'data-course-lat'
    #                 ]
    #                 atts['Longitude'] = soup.find(class_='btn-layout')[
    #                     'data-course-lng'
    #                 ]
    #             except:
    #                 atts['Lattitude'] = None
    #                 atts['Longitude'] = None
    #             new_item.update(atts)
    #         except:
    #             self.missing_courses.append(i)
    #         try:
    #             soup = bs(item['info'], 'html.parser')
    #             address_item = {'Address': None,
    #                             'City': None,
    #                             'State': None,
    #                             'Postal_Code': None,
    #                             'Country': None,
    #                              'Phone': None,
    #                              'Website': None,
    #                              'Images': None,
    #                              'Built': None,
    #                              'Type': None,
    #                              'Season': None}
    #             try:
    #                 address = soup.find_all(class_='address')
    #                 add_atts = [
    #                     'Address',
    #                     'City',
    #                     'State',
    #                     'Postal_Code',
    #                     'Country'
    #                 ]
    #                 for j, line in enumerate(address):
    #                     if j == 0:
    #                         line = line.text.split(',')[0]
    #                         address_item[add_atts[j]] = line
    #                     elif line.text == '':
    #                         continue
    #                     else:
    #                         address_item[add_atts[j]] = line.text
    #                 # print address_item
    #             except:
    #                 address = None
    #             try:
    #                 phone = soup.find(itemprop='telephone').text
    #                 if phone == '':
    #                     phone = None
    #                 address_item['Phone'] = phone
    #             except:
    #                 phone = None
    #             try:
    #                 website = soup.find(itemprop='sameAs').text
    #                 if website == '':
    #                     website = None
    #                 address_item['Website'] = website
    #             except:
    #                 website = None
    #             try:
    #                 image_links = []
    #                 images = soup.find_all('script')
    #                 for image in images:
    #                     url = json.loads(image.text)['contentUrl']
    #                     image_links.append(url)
    #                 if image_links == []:
    #                     image_links = None
    #                 address_item['Images'] = image_links
    #             except:
    #                 image_links = None
    #             try:
    #                 divs = soup.find_all('div')
    #                 for j in range(-5, 0):
    #                     try:
    #                         class_ = divs[j]['class']
    #                     except:
    #                         class_ = 'None'
    #                     if class_ != 'more-info-icon':
    #                         continue
    #                     elif class_ == 'None':
    #                         splits = divs[j].text.split(': ')
    #                         if splits[0] == 'Built':
    #                             address_item[splits[0]] = int(splits[1])
    #                         else:
    #                             address_item[splits[0]] = splits[1]
    #             except:
    #                 divs = None
    #             new_item.update(address_item)
    #         except:
    #             self.missing_courses.append(i)
    #         print('Course ', i, 'successfully parsed')
    #         # try:
    #         #     soup = bs(item['more'], 'html.parser')
    #         #     more_info = {'Carts': None,
    #         #                  'Pull-carts': None,
    #         #                  'Clubs': None,
    #         #                  'Caddies': None,
    #         #                  'GPS': None,
    #         #                  'Practice Instruction'
    #         #                  'Driving range': None,
    #         #                  'Pitching_chipping area': None,
    #         #                  'Putting green': None,
    #         #                  'Practice bunker': None,
    #         #                  'Simulator': None,
    #         #                  'Teaching pro': None,
    #         #                  'Golf schoolacademy': None,
    #         #                  'Walking': None,
    #         #                  'Spikes': None,
    #         #                  'Credit Cards': None,
    #         #                  'Dress_Code': None}
    #         #     more = soup.find_all('div')
    #         #     for item in more[3:6]:
    #         #         sub_item = item.spit(': ')
    #         #         more_info[sub_item[0]] = sub_item[1]
    #         #     for item in more[7:13]:
    #         #         sub_item = item.split(': ')
    #         #         more_info[sub_item[0]] = sub_item[1]
    #         #     for item in more[14:17]:
    #         #         sub_item = item.split(': ')
    #         #         more_info[sub_item[0]] = sub_item[1]
    #         #     new_item.update(more_info)
    #         # except:
    #         #     self.missing_courses.append(i)
    #         self.course_table.put_item(Item=new_item)
    #         # except:
    #         #     print(
    #         #         '\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\nCourse',
    #         #         i,
    #         #         'Failed\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n'
    #         #     )

    # def build_mat(self, indices):
    #     for i in indices:
    #         print('Course index ', i, 'processed into ratings_mat')
    #         response = self.review_table.query(
    #             KeyConditionExpression=Key('Course_Id').eq(i)
    #         )
    #         ratings = []
    #         users = []
    #         for item in response['Items']:
    #             rating = item['Rating']
    #             ratings.append(rating)
    #             try:
    #                 users.append(self.users.index(item['Username']))
    #             except:
    #                 self.missing_users.append(item['Username'])
    #         for user, rating in zip(users, ratings):
    #             self.ratings_mat[user, i] = rating
    #
    # def check_missing(self, info_table):
    #     missing_course_ids = []
    #     for i in range(len(self.courses)):
    #         response = info_table.query(
    #             KeyConditionExpression=Key('Course_Id').eq(i)
    #         )
    #         if response['Count'] == 0:
    #             missing_course_ids.append(i)
    #     return missing_course_ids

    # def check_missing_exists(self, courses, session_num=0):
    #     for course in courses:
    #         url = urljoin(self.url, course)
    #         html = self.get_site(url, session_num=session_num)
    #         soup = bs(html, 'html.parser')
    #         try:
    #             exists = soup.find(class_='container simple-page-wrapper')\
    #                 .h1.text
    #         except:
    #             continue
    #         if exists == 'Page not found':
    #             new_course = self.fill_result_from_google(
    #                 url,
    #                 course,
    #                 session_num=session_num
    #             )
    #             self.missing_courses[
    #                 self.missing_courses.index(course)
    #             ] = new_course
    #             self.courses[self.courses.index(course)] = new_course
    #
    # def parallel_missing(self, n):
    #     links = list(self.chunks(self.missing_courses, n))
    #     jobs = []
    #     for i in range(len(self.sessions)):
    #         thread = threading.Thread(name=i,
    #                                   target=self.check_missing_exists,
    #                                   args=(links[i], i))
    #         jobs.append(thread)
    #         thread.start()
    #     for j in jobs:
    #         j.join()
    #
    # def fill_result_from_google(self, url, course, session_num=0):
    #     api_key = os.environ['GOOGLE_API_KEY']
    #     cse_id = os.environ['GOOGLE_CSE_ID']
    #     search_term = ' '.join(url.split('courses/')[1].split('-')[1:])
    #     html = self.get_site(
    #         'https://www.googleapis.com/customsearch/v1?key={}&cx={}&q={}'\
    #             .format(api_key, cse_id, search_term),
    #         session_num=session_num
    #     )
    #     results = json.loads(html)
    #     for result in results['items']:
    #         link = result['link']
    #         if link.split('.com')[-1] == course:
    #             continue
    #         elif link.split('.com')[-1] in courses:
    #             continue
    #         return link.split('.com')[-1]

# TODO: Implement test train split on ratings_mat using df.unstack()
# .reset_index() load matrix into pandas and change the names of the indices
# to user and course. Then call df.unstack().reset_index() to return user,
# course, rating matrix. Finally drop nan values with
# df.drop(df[pd.isnull(df['rating'])].index)
