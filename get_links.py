from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import cPickle as pickle
from bs4 import BeautifulSoup
import re
import math

dcap = dict(DesiredCapabilities.PHANTOMJS)
dcap["phantomjs.page.settings.userAgent"] = ("Chrome/15.0.87")

urls = ['https://www.golfnow.com/course-directory',
        'http://www.golfadvisor.com/course-directory/']

service_args = [
    '--proxy=127.0.0.1:9050',
    '--proxy-type=socks5',
    ]

class ReviewScraper(object):
    '''
    Base class for building specific golf review website scraping objects.
    '''
    def __init__(self, url):
        self.browser = webdriver.PhantomJS(desired_capabilities=dcap,
                                           service_args=service_args)
        print self.browser.get_window_size()
        self.browser.maximize_window()
        print self.browser.get_window_size()
        self.url = url

    def get_site(self, url):
        self.browser.get(url)
        self.browser.delete_all_cookies()

    def get_href_from_class(self, class_name):
        '''
        Function to pull links from withing elements of a specific class name.
        For example, given <div class='course'><a href=$LINK></div> the function
        would return $LINK.
        INPUT:
            self: uses self.browser
            class_name: string of the class name for the element we want to find
                links within
        OUTPUT:
            links: list of links contained within the specific class element
        '''
        elements = self.browser.find_elements_by_class_name(class_name)
        links = [element.find_element_by_tag_name('a').get_attribute('href') \
                 for element in elements]
        return links

class GolfNow(ReviewScraper):
    '''
    Class containing methods for scraping information from the GolfNow website.
    '''
    def get_courses(self):
        '''
        Function to crawl through all cities, states, and countries to collect
        complete list of all course links.
        INPUT:
            self: uses self.url and self.browser
        OUTPUT:
            courses: a set of all courses listed on the website
        '''
        self.get_site(self.url)
        countries = self.get_href_from_class('country-cube')
        courses = set()
        for country in countries:
            self.get_site(country)
            states = self.get_href_from_class('col-20')
            for state in states:
                self.get_site(state)
                cities = [city.find_element_by_tag_name('a')\
                          .get_attribute('href') for city in self.browser\
                          .find_elements_by_class_name('city-cube')]
                for city in cities:
                    self.get_site(city)
                    courses.update(self.browser\
                                   .find_element_by_class_name('featured'))
                    courses.update([result.find_element_by_tag_name('a')\
                                    .get_attribute('href') for result in \
                                    self.browser\
                                    .find_elements_by_class_name('result')])

        'Test Function to return course in aruba.'
        # self.get_site(countries[0])
        # states = self.get_href_from_class('col-20')
        # self.get_site(states[0])
        # cities = self.get_href_from_class('city-cube')
        # self.get_site(cities[0])
        # courses.update(self.get_href_from_class('featured'))
        # courses.update(self.get_href_from_class('result'))
        return courses

    def get_reviews(self, course_url):
        import pdb; pdb.set_trace()
        self.get_site(course_url)
        all_reviews = self.browser.find_element_by_id('ListReviews')
        rows = all_reviews.find_elements_by_class_name('row')

class GolfAdvisor(ReviewScraper):
    '''
    Class containing methods for scraping information from the GolfAdvisor
    website.
    '''
    def get_courses(self):
        '''
        Function to crawl through all cities, states, and countries to collect
        complete list of all course links.
        INPUT:
            self: uses self.url and self.browser
        OUTPUT:
            courses: a set of all courses listed on the website
        '''
        self.get_site(self.url)
        courses = set()
        countries = self.get_href_from_class('col-sm-6')
        for country in countries:
            self.get_site(country)
            states = self.get_href_from_class('col-sm-6')
            for state in states:
                self.get_site(state)
                cities = self.get_href_from_class('col-sm-6')
                for city in cities:
                    self.get_site(city)
                    courses.update(self.get_href_from_class('title'))
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
        course_doc = self.get_course_info()
        course_doc['reviews'] = []
        pages = self.check_pages()
        for i in xrange(pages):
            course_doc['reviews'] += self.get_review(url + '?page={}'.format(i))
        return course_doc

    def get_reviews(self, url):
        '''
        Retrieve all reviews on a single page.
        INPUT:
            self: uses self.browser for retrieving elements from page
            url: string of webpage address from which to retrieve reviews
        OUTPUT:
            reviews_list: list of review elements from page
        '''
        self.get_site(url)
        review = self.browser.find_element_by_id('reviewswrapper')
        reviews = review.find_elements_by_xpath(".//div[@itemprop='review']")
        reviews_list = []
        for review in reviews:
            review.get_attribute('outerHTML')
        return reviews_list

    def get_course_info(self):
        '''
        Create an entry for a golf course, including course stats and info
        INPUT:
            self: uses self.browser to find and return data
        OUTPUT:
            course_doc: a dictionary containing the course stats and info
        '''
        course_doc = {}
        name = self.browser.find_element_by_xpath("//span[@itemprop='name']")\
                                                  .get_attribute('innerHTML')
        course_doc['name'] = name
        '''atts = self.browser\
               .find_element_by_class_name('course-essential-info-top')\
               .find_elements_by_tag_name('li')'''
        # replace original atts value with outherhtml for parsing later
        atts = self.browser\
               .find_element_by_class_name('course-essential-info-top')\
               .get_attribute('outerHTML')
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
        info = self.browser\
               .find_element_by_xpath("//div[@class='row course-info-top-row']")\
               .get_attribute('outerHTML')
        course_doc['info'] = info
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

    def check_pages(self):
        '''
        Find the total number of review pages.
        OUTPUT:
            
        '''
        review_count = int(self.browser.\
                           find_element_by_xpath("//span[@itemprop='reviewCount']")\
                           .get_attribute('innerHTML').strip('\)').strip('\('))
        pages = 1
        if review_count > 20:
            pages = int(math.ceil(review_count / 20))
        return pages




if __name__ == '__main__':
    gn = GolfNow(urls[0])
    courses = gn.get_courses()
    # ga = GolfAdvisor(urls[1])
    # courses.update(ga.get_courses())
    with open('course_links.pkl', 'w') as f:
        pickle.dump(courses, f)
