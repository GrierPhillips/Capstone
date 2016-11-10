from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import cPickle as pickle
import time

dcap = dict(DesiredCapabilities.PHANTOMJS)
dcap["phantomjs.page.settings.userAgent"] = ("Chrome/15.0.87")

urls = ['https://www.golfnow.com/course-directory', 'http://www.golfadvisor.com/course-directory/']

service_args = [
    '--proxy=127.0.0.1:9050',
    '--proxy-type=socks5',
    ]

class GolfNow(object):
    '''
    Class containing methods for scraping information from the GolfNow website.
    '''
    def __init__(self, url):
        self.browser = webdriver.PhantomJS(desired_capabilities=dcap, service_args=service_args)
        self.url = url

    def get_courses(self):
        '''
        Function to crawl through all cities, states, and countries to collect complete list of all course links.
        INPUT:
            self: uses self.url and self.browser
        OUTPUT:
            courses: a set of all courses listed on the website
        '''
        self.browser.get(self.url)
        self.browser.delete_all_cookies()
        countries = self.get_href_from_class('country-cube')
        courses = set()
        for country in countries:
            self.browser.get(country)
            states = self.get_href_from_class('col-20')
            for state in states:
                self.browser.get(state)
                cities = [city.find_element_by_tag_name('a').get_attribute('href') for city in self.browser.find_elements_by_class_name('city-cube')]
                for city in cities:
                    self.browser.get(city)
                    courses.update(self.browser.find_element_by_class_name('featured'))
                    courses.update([result.find_element_by_tag_name('a').get_attribute('href') for result in self.browser.find_elements_by_class_name('result')])

        'Test Function to return course in aruba.'
        # self.browser.get(countries[0])
        # self.browser.delete_all_cookies()
        # states = self.get_href_from_class('col-20')
        # self.browser.get(states[0])
        # self.browser.delete_all_cookies()
        # cities = self.get_href_from_class('city-cube')
        # self.browser.get(cities[0])
        # self.browser.delete_all_cookies()
        # courses.update(self.get_href_from_class('featured'))
        # courses.update(self.get_href_from_class('result'))
        return courses

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
        links = [element.find_element_by_tag_name('a').get_attribute('href') for element in elements]
        return links

    # def get_reviews(self, course_url):
    #     all_reviews = self.browser.find_element_by_id('ListReviews')
        # all_reviews.find_element_by_xpath()'.//*[@id="ListReviews"]/div[1]'

class GolfAdvisor(object):
    def __init__(self, url):
        self.browser = webdriver.PhantomJS(desired_capabilities=dcap)
        self.url = url

    def get_courses(self):
        '''
        Function to crawl through all cities, states, and countries to collect complete list of all course links.
        INPUT:
            self: uses self.url and self.browser
        OUTPUT:
            courses: a set of all courses listed on the website
        '''
        self.browser.get(self.url)
        self.browser.delete_all_cookies()
        courses = set()
        countries = self.get_href_from_class('col-sm-6')
        for country in countries:
            self.browser.get(country)
            self.browser.delete_all_cookies()
            states = self.get_href_from_class('col-sm-6')
            for state in states:
                self.browser.get(state)
                self.browser.delete_all_cookies()
                cities = self.get_href_from_class('col-sm-6')
                for city in cities:
                    self.browser.get(city)
                    self.browser.delete_all_cookies()
                    courses.update(self.get_href_from_class('title'))
        return courses

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
        links = [element.find_element_by_tag_name('a').get_attribute('href') for element in elements]
        return links

if __name__ == '__main__':
    gn = GolfNow(urls[0])
    courses = gn.get_courses()
    # ga = GolfAdvisor(urls[1])
    # courses.update(ga.get_courses())
    with open('course_links.pkl', 'w') as f:
        pickle.dump(courses, f)
