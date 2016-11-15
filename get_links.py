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

class GolfAdvisor(object):
    '''
    Class containing methods for scraping information from the GolfAdvisor
    website.
    '''
    def __init__(self):
        # TODO: implement threading with tor for scraping in parallel perhaps using method found at http://stackoverflow.com/questions/14321214/how-to-run-multiple-tor-processes-at-once-with-different-exit-ips
        proxies = [9050, 9052, 9053, 9054, 9055, 9056]
        self.s1 = requesocks.session()
        self.s2 = requesocks.session()
        self.s3 = requesocks.session()
        self.s4 = requesocks.session()
        self.s5 = requesocks.session()
        self.s6 = requesocks.session()
        self.sessions = [self.s1, self.s2, self.s3, self.s4, self.s5, self.s6]
        for i, s in enumerate(self.sessions):
            s.proxies = {'http':  'socks5://127.0.0.1:{}'.format(proxies[i]),
                         'https': 'socks5://127.0.0.1:{}'.format(proxies[i])}
        # self.session = requesocks.session()
        # self.session.proxies = {'http':  'socks5://127.0.0.1:9050',
        #                         'https': 'socks5://127.0.0.1:9050'}
        self.url = 'http://www.golfadvisor.com/course-directory/'
        self.review_num = 0

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

    def get_site(self, url):
        '''
        Condensed process for getting site html and changing ip address.
        INPUT:
            url: string. website to pull html from.
        OUTPUT:
            html: string. html of desired site.
        '''
        html = self.s1.get(url).text
        self.renew_connection()
        # self.requests += 1
        # if self.requests > 12:
        #     self.renew_connection()
            # self.requests = 0
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
        # import pdb; pdb.set_trace()
        html = self.get_site(self.url)
        courses = set()
        soup = BeautifulSoup(html, 'html.parser')
        countries = soup.find_all('li', class_='col-sm-6')
        courses = self.walk_directory(countries, courses, self.url)
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

    def get_all_reviews(self, url):
        '''
        Function to build the course document. Finds the total number of reivew
        pages and gets reviews from each.
        INPUT:
            url: string of the base course website
        OUTPUT:
            course_doc: json object of course info and nested reviews
        '''
        html = self.get_site(url)
        soup = BeautifulSoup(html, 'html.parser')
        course_info = self.get_course_info(soup)
        course_revs = []
        pages = self.check_pages(soup)
        for i in xrange(1, pages + 1):
            course_revs += self.get_reviews(url + '?page={}'.format(i))
        return course_info, course_revs

    def get_reviews(self, url):
        '''
        Retrieve all reviews on a single page.
        INPUT:
            url: string of webpage address from which to retrieve reviews
        OUTPUT:
            reviews: list of review elements from page. Full html.
        '''
        html = self.get_site(url)
        soup = BeautifulSoup(html, 'html.parser')
        reviews = soup.find_all(itemprop='review')
        reviews[:] = [str(review) for review in reviews]
        return reviews

    def get_course_info(self, soup):
        '''
        Create an entry for a golf course, including course stats and info.
        Brings in entire html of desired sections for parsing later.
        INPUT:
            soup: parsed html from BeautifulSoup
        OUTPUT:
            course_doc: a dictionary containing the course stats and info
        '''
        course_doc = {}
        name = soup.find(itemprop='name').text
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
            record: dictionary. course_doc containing keys = ['Name',
                'attributes', 'info', 'more', 'reviews']
            table: boto3 dynamodb table object
        OUTPUT;
            None
        '''

        table.put_item(Item=record)
        # if table.name == 'Course_Info':
        #     table.update_item(Key={'Name': record['Name']},
        #                       UpdateExpression='SET #r = :val1',
        #                       ExpressionAttributeValues={':val1': record['Review']},
        #                       ExpressionAttributeNames={'#r': 'Review'}))
        # else:
        #     table.update_item(Key={'Name': record['Name']},
        #                       UpdateExpression='SET #r = :val1',
        #                       ExpressionAttributeValues={':val1': record['Review']},
        #                       ExpressionAttributeNames={'#r': 'Review'}))

    def get_and_store_reviews(self, url, read_table, info_table, review_table):
        '''
        Complete pipeline for getting reviews from a list of pages, creating a
        course record in the form of a dictionary (primary key='Name'), and
        storing reviews in Dynamodb.
        INPUT:
            url: list. website addresses for a list of courses
            table: boto3 dynamodb table object
        OUTPUT:
            None
        '''
        # courses = read_table.scan(FilterExpression=Attr('Status').eq('not checked'))['Items']
        # course = courses[np.random.randint(len(courses))]
        name = url
        url = urljoin(self.url, name)
        read_table.update_item(Key={'Course': name},
                               UpdateExpression='SET #r = :val1, #s = :val2',
                               ExpressionAttributeValues={':val1': 'in process',
                                                          ':val2': 'checking'},
                               ExpressionAttributeNames={'#r': 'Result',
                                                         '#s': 'Status'})
        info, reviews = self.get_all_reviews(url)
        self.write_to_dynamodb(info, info_table)
        for review in reviews:
            review = {'Review_Id': self.review_num,
                      'Name': name,
                      'Review': review}
            self.write_to_dynamodb(review, review_table)
            self.review_num += 1
        read_table.update_item(Key={'Course': name},
                               UpdateExpression='SET #r = :val1, #s = :val2',
                               ExpressionAttributeValues={':val1': 'returned',
                                                          ':val2': 'checked'},
                               ExpressionAttributeNames={'#r': 'Result',
                                                         '#s': 'Status'})


    def parallel_scrape_reviews(self, links, read_table, write_table):
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
                                      args=(links[i], read_table, write_table))
            jobs.append(thread)
            thread.start()
        for j in jobs:
            j.join()

def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

if __name__ == '__main__':
    ga = GolfAdvisor()
    if os.path.exists('course_links.pkl'):
        with open('course_links.pkl', 'r') as f:
            courses = pickle.load(f)
        # n = int(math.ceil(len(courses) / 6.))
        # links = list(chunks(list(courses), n))
        courses = list(courses)
        ddb = boto3.resource('dynamodb', region_name='us-west-2')
        info_table = ddb.Table('Course_Info')
        review_table = ddb.Table('Course_Reviews')
        read_table = ddb.Table('Scrape_Status')
        for course in courses:
            ga.get_and_store_reviews(course, read_table, info_table, review_table)
    else:
        courses = ga.get_courses()
        with open('course_links.pkl', 'w') as f:
            pickle.dump(courses, f)
