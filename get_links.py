from selenium import webdriver

path_to_chrome = '/Users/Doedy/Documents/Galvanize/Capstone/chromedriver'
# self.browser = webdriver.Chrome(executable_path=path_to_chrome)

urls = ['https://www.golfnow.com/course-directory/us', 'http://www.golfadvisor.com/course-directory/2-usa/']

class GolfNow(object):
    def __init__(self, url):
        self.browser = webdriver.Chrome(executable_path=path_to_chrome)
        self.url = url

    def get_golfnow_courses(self):
        self.browser.get(self.url)
        states = self.get_href_from_class('col-20')
        print states[0]
        # for href in hrefs:
        #     self.browser.get(href)
        #     cities = [city.find_element_by_tag_name('a').get_attribute('href') for city in self.browser.find_elements_by_class_name('city-cube')]
        #     for city in cities:
        #         self.browser.get(city)
        #         courses = []
        #         courses.append(self.browser.find_element_by_class_name('featured'))
        #         courses += [result.find_element_by_tag_name('a').get_attribute('href') for result in self.browser.find_elements_by_class_name('result')]
        self.browser.get(states[0])
        cities = self.get_href_from_class('city-cube')
        self.browser.get(cities[0])
        courses = self.get_href_from_class('featured')
        courses += self.get_href_from_class('result')
        return courses

    def get_href_from_class(self, class_name):
        elements = self.browser.find_elements_by_class_name(class_name)
        return [element.find_element_by_tag_name('a').get_attribute('href') for element in elements]

if __name__ == '__main__':
    gn = GolfNow(urls[0])
    print gn.get_golfnow_courses()
