import boto3
import math
import threading
import multiprocessing
from geopy.geocoders import Nominatim
import cPickle as pickle
from decimal import Decimal
import geocoder

POOL_SIZE = multiprocessing.cpu_count()

class MakeLocations(object):
    def __init__(self, courses, course_table=None, state_table=None, city_table=None):
        self.courses = courses
        self.course_table = course_table
        self.state_table = state_table
        self.city_table = city_table
        self.geolocator = Nominatim()

    def parallel_query(self, function, num_cores, *args):
        # import pdb; pdb.set_trace()
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

    def make_locations(self, indices):
        for i in indices:
            response = self.course_table.get_item(Key={'Course_Id': i})
            item = response['Item']
            country = item['Country']
            state = item['State']
            city = item['City']
            name = item['Name']
            # print item
            try:
                site = self.geolocator.geocode(city + ', ' + state)
            except TypeError:
                print '\n\n\n\n\nCourse ', i, ' failed at geolocator\n\n\n\n', city, state, country
                site = self.geolocator.geocode(city)
            except AttributeError:
                print '\n\n\n\nCourse ', i, site, country, city, state, '\n\n\n\n'
            try:
                lat = site.latitude
                lng = site.longitude
                lat = Decimal(str(lat))
                lng = Decimal(str(lng))
            except:
                print '\n\n\n\nCourse ', i, ' failed at lat\n\n\n\n', site, city, state, country
            # print lat, lng
            try:
                self.state_table.update_item(
                    Key={
                        'Country': country,
                        'State': state
                    }
                )
            except:
                print '\n\n\n\nCourse ', i, 'failed at update state ', country, state
            if self.city_table.get_item(Key={'State': state, 'City': city}).get('Item'):
                self.city_table.update_item(
                    Key={
                        'State': state,
                        'City': city
                    },
                    UpdateExpression='SET Courses = list_append(Courses, :i), Latitude = :lat, Longitude = :lng',
                    ExpressionAttributeValues={
                        ':i': [name],
                        ':lat': lat,
                        ':lng': lng
                    }
                )
            else:
                city_item = {'State': state, 'City': city, 'Latitude': lat, 'Longitude': lng, 'Courses': [name]}
                self.city_table.put_item(Item=city_item)

    @staticmethod
    def chunks(l, n):
        """Yield successive n-sized chunks from l."""
        for i in range(0, len(l), n):
            yield l[i:i + n]

if __name__ == '__main__':
    db = boto3.resource('dynamodb', region_name='us-west-2')
    course_table = db.Table('Courses')
    state_table = db.Table('States')
    city_table = db.Table('Cities')
    with open('courses.pkl', 'r') as f:
        courses = pickle.load(f)
    ml = MakeLocations(courses, course_table=course_table, state_table=state_table, city_table=city_table)
    ml.parallel_query(ml.make_locations, POOL_SIZE)
