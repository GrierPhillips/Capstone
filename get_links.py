import cPickle as pickle
from bs4 import BeautifulSoup
import math
from stem import Signal
from stem.control import Controller
import requesocks
from urlparse import urljoin
import boto3
from boto3.dynamodb.conditions import Key, Attr
import os
import threading
import numpy as np
from scipy import sparse
import sys
from ItemItemRecommender import ItemItemRecommender
import json
import multiprocessing


POOL_SIZE = multiprocessing.cpu_count()

def apply_defaults(cls):
    for i in xrange(20):
        setattr(cls, 's' + str(i), requesocks.session())
    return cls

@apply_defaults
class GolfAdvisor(object):
    '''
    Class containing methods for scraping information from the GolfAdvisor
    website.
    '''
    def __init__(self, courses=None, users=[], ratings_mat=None, review_table=None):
        # TODO: implement threading with tor for scraping in parallel perhaps using method found at http://stackoverflow.com/questions/14321214/how-to-run-multiple-tor-processes-at-once-with-different-exit-ips
        proxies = [9050] + range(9052,9071)
        self.sessions = [self.s0, self.s1, self.s2, self.s3, self.s4, self.s5,
                         self.s6, self.s7, self.s8, self.s9, self.s10, self.s11,
                         self.s12, self.s13, self.s14, self.s15, self.s16,
                         self.s17, self.s18, self.s19]
        for i, s in enumerate(self.sessions):
            s.proxies = {'http':  'socks5://127.0.0.1:{}'.format(proxies[i]),
                         'https': 'socks5://127.0.0.1:{}'.format(proxies[i])}
        # self.session = requesocks.session()
        # self.session.proxies = {'http':  'socks5://127.0.0.1:9050',
        #                         'https': 'socks5://127.0.0.1:9050'}
        self.url = 'http://www.golfadvisor.com/course-directory/'
        self.review_num = 0
        self.requests = 0
        self.courses = courses
        self.users = users
        self.missing_courses = []
        self.ratings_mat = ratings_mat
        self.review_table = review_table

    @staticmethod
    def renew_connection():
        '''
        Change tor exit node. This will allow cycling of IP addresses such that
        no address makes 2 requests in a row.
        INPUT:
            None
        OUTPUT:
            None
        '''
        with Controller.from_port(port = 9051) as controller:
            controller.authenticate(password="password")
            controller.signal(Signal.NEWNYM)

    def get_site(self, url, session_num=0):
        '''
        Condensed process for getting site html and changing ip address.
        INPUT:
            url: string. website to pull html from.
        OUTPUT:
            html: string. html of desired site.
        '''
        try:
            html = self.sessions[session_num].get(url).text
        except:
            self.renew_connection()
            html = self.sessions[session_num].get(url).text
        self.requests += 1
        if self.requests > 20:
            self.requests = 0
            self.renew_connection()
        return html

    def get_courses(self):
        '''
        Function to crawl through all cities, states, and countries to collect
        complete list of all course links.
        INPUT:
            self: uses self.url and self.browser
        OUTPUT:
            courses: a set of all courses listed on the website
        '''
        # TODO: For any future developments note that a list of all course links
        # are available 1000 per page through www.golfadvisor.com/sitemap_courses-%PAGENUM%.xml
        # the entire sitemap is available through http://www.golfadvisor.com/sitemap.xml
        # import pdb; pdb.set_trace()
        html = self.get_site(self.url)
        courses = set()
        soup = BeautifulSoup(html, 'html.parser')
        countries = soup.find_all('li', class_='col-sm-6')
        courses = self.walk_directory(countries, courses, self.url)
        self.courses = courses
        return courses

    def walk_directory(self, elements, courses, url):
        for element in elements:
            site = urljoin(url, element.a['href'])
            html = self.get_site(site)
            soup = BeautifulSoup(html, 'html.parser')
            sub_elements = soup.find_all('li', class_='col-sm-6')
            if len(sub_elements) == 0:
                courses.update([x.a['href'] for x in soup.\
                                find_all('div', class_='teaser')])
                print 'Courses updated with courses from {}'.format(element.a['href'])
            else:
                self.walk_directory(sub_elements, courses, site)
        return courses

    def get_all_reviews(self, url, session_num=0):
        '''
        Function to build the course document. Finds the total number of reivew
        pages and gets reviews from each.
        INPUT:
            url: string of the base course website
        OUTPUT:
            course_doc: json object of course info and nested reviews
        '''
        html = self.get_site(url, session_num=session_num)
        soup = BeautifulSoup(html, 'html.parser')
        course_info = self.get_course_info(soup, url)
        if course_info == None:
            return None, None
        course_revs = {}
        pages = self.check_pages(soup)
        for i in xrange(1, pages + 1):
            course_revs.update(self.get_reviews(url + '?page={}'.format(i)))
        return course_info, course_revs

    def get_reviews(self, url, session_num=0):
        '''
        Retrieve all reviews on a single page.
        INPUT:
            url: string of webpage address from which to retrieve reviews
        OUTPUT:
            reviews: list of review elements from page. Full html.
        '''
        html = self.get_site(url, session_num=session_num)
        soup = BeautifulSoup(html, 'html.parser')
        reviews = soup.find_all(itemprop='review')
        users = []
        for review in reviews:
            users.append(review.find(itemprop='author').text)
        reviews[:] = [str(review) for review in reviews]
        reviews = {users[i]: review for i, review in enumerate(reviews)}
        return reviews

    def get_course_info(self, soup, url):
        '''
        Create an entry for a golf course, including course stats and info.
        Brings in entire html of desired sections for parsing later.
        INPUT:
            soup: parsed html from BeautifulSoup
        OUTPUT:
            course_doc: a dictionary containing the course stats and info
        '''
        course_doc = {}
        try:
            name = soup.find(itemprop='name').text
        except:
            self.missing_courses.append(url.split('.com')[-1])
            return None
        course_doc['Course'] = url
        course_doc['Course_Id'] = self.courses.index(url.split('.com')[-1])
        course_doc['Name'] = name
        atts = str(soup.find(class_='course-essential-info-top'))
        course_doc['attributes'] = atts
        # TODO: Move this logic to the operations side when parsing docs
        '''# go through attributes and convert numbers to float or int
        for att in atts[:-1]:
            name, val = att.get_attribute('innerHTML').split()
            name = name[:-1]
            if val.find('.') != -1:
                val = float(val)
            # fix all values to yards
            elif 'meters' in val:
                val = int(round(int(val[:-7]) * 1.09361329834))
            elif 'yards' in val:
                val = int(val[:-6])
            course_doc[name] = val
        # last list element is an 'a' tag with attributes for id, lat, and long
        for att in atts[-1].get_attribute('innerHTML').strip().split()[3:6]:
            name, val = att.replace('\"', '').split('=')
            if val.find('.') != -1:
                val = float(val)
            course_doc[name] = val'''
        # replace address and info with complete html block
        '''address = self.browser.find_element_by_class_name('address')\
                  .get_attribute('innerHTML')
        key_info = self.browser.find_element_by_class_name('key-info')\
                   .find_elements_by_tag_name('div')
        arch_div = key_info.pop(3).get_attribute('innerHTML')
        text = BeautifulSoup(arch_div, 'html.parser').text
        text = text.strip().split(':\n')
        year_cleanr = re.compile('\([0-9]*\)')
        title_cleanr = re.compile(',\s[A-Z]r.')
        name, val = text[0], text[1].strip()
        val = re.sub(year_cleanr, '', val)
        val = re.sub(title_cleanr, '', val).split(',')
        for i in xrange(len(val)):
            val[i] = val[i].strip()
        course_doc[name] = val
        for key in key_info[2:]:
            name, val = key.get_attribute('innerHTML').strip().split(': ')
            course_doc[name] = val'''
        info = str(soup.find(class_='row course-info-top-row'))
        course_doc['info'] = info
        more = str(soup.find(id='more'))
        course_doc['more'] = more
        return course_doc

    '''
    def get_user_review(self, review):
        user_review = {}
        author = review.find_element_by_xpath(".//span[@itemprop='author']")\
                 .get_attribute('innerHTML')
        age = review.find_element_by_xpath(".//span[@class='context-value Age']")\
              .get_attribute('innerHTML')
        gen = review.find_element_by_xpath(".//span[@class='context-value Gender']")\
              .get_attribute('innerHTML')
        user_review['author'] = author
        user_review['age'] = age
        user_review['gender'] = gen

        return course_doc
        '''

    def check_pages(self, soup):
        '''
        Given the total number of reivews for a course determine the number
        of pages that are populated with reviews. There are 20 reviews per page.
        INPUT:
            soup: parsed html from BeautifulSoup
        OUTPUT:
            pages: int number of pages containing reviews
        '''
        review_count = float(soup.find(itemprop='reviewCount').text.strip('\)')\
                                 .strip('\('))
        pages = 1
        if review_count > 20:
            pages = int(math.ceil(review_count / 20))
        return pages

    def write_to_dynamodb(self, record, table):
        '''
        Write to dynamodb using boto3.
        INPUT:
            record: dictionary. course_doc containing keys = ['Course',
                'attributes', 'info', 'more', 'reviews']
            table: boto3 dynamodb table object
        OUTPUT;
            None
        '''

        table.put_item(Item=record)

    def get_and_store_reviews(self, urls, info_table, review_table, session_num=0):
        '''
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
        '''
        Setup and implement threads for parallel scraping of course reviews and
        writing results to dynamodb.
        INPUT:
            table: boto3 dynamodb table object
        OUTPUT:
            None
        '''
        jobs = []
        for i in range(len(self.sessions)):
            thread = threading.Thread(name=i,
                                      target=self.get_and_store_reviews,
                                      args=(links[i],
                                            info_table,
                                            review_table,
                                            i)
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
        for i in xrange(len(self.courses)):
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
        for i in xrange(209994):
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
        indices = range(len(self.courses))
        self.multiprocess_build_mat(POOL_SIZE, indices)
        with open('missing_users.pkl', 'w') as f:
            pickle.dump(self.missing_users, f)

    def parallel_query_reviews(self, function, num_cores, *args):
        num = int(math.ceil(len(self.courses) / float(num_cores)))
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

    def multiprocess_build_mat(self, pool_size, iterable):
        pool = multiprocessing.Pool(pool_size)
        pool.map(self.build_mat, iterable)
        pool.close()
        pool.join()



    def build_mat(self, indices):
        for i in indices:
            print 'Course index ', i, 'processed into ratings_mat'
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
        for i in xrange(len(self.courses)):
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
            soup = BeautifulSoup(html, 'html.parser')
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

    def parse_reviews(self, indices, review_table, user_table):
        self.error_items = {}

        for i in indices:
            print 'Course index', i, 'html parsed.'
            response = review_table.query(KeyConditionExpression=Key('Course_Id').eq(i))
            items = response['Items']
            while 'LastEvaluatedKey' in response.keys():
                response = review_table.query(
                    KeyConditionExpression=Key('Course_Id').eq(i),
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items += response['Items']
            for item in items:
                try:
                    parsed = item['Rating']
                except:
                    soup = BeautifulSoup(item['Review'], 'html.parser')
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
                    review_table.update_item(
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
                    user_table.update_item(
                        Key={
                             'User_Id': user_id
                        },
                        UpdateExpression="set Age = :a, Gender = :g, Skill = :s, Plays = :p, Handicap = :h",
                        ExpressionAttributeValues={
                            ':a': age,
                            ':g': gen,
                            ':s': skill,
                            ':p': plays,
                            ':h': hdcp
                        }
                    )


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
    review_table = ddb.Table('Course_Reviews')
    read_table = ddb.Table('Scrape_Status')
    users_table = ddb.Table('Users')
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
            ga = GolfAdvisor(load_courses(), load_users(), )
            ga.parallel_query_reviews(ga.parse_reviews, 16, review_table, users_table)
            with open('errors.pkl', 'w') as f:
                pickle.dump(ga.error_items, f)
            with open('users2.pkl', 'w') as f:
                pickle.dump(ga.users, f)

    # TODO: Implement test train split on ratings_mat using df.unstack().reset_index()
    # load matrix into pandas and change the names of the indices to user and course.
    # then call df.unstack().reset_index() to return user, course, rating matrix.
    # Finally drop nan values with df.drop(df[pd.isnull(df['rating'])].index)
