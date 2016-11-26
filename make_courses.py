import cPickle as pickle
import boto3
import threading
import multiprocessing
import math

POOL_SIZE = multiprocessing.cpu_count()
dynamo = boto3.resource('dynamodb', region_name='us-west-2')
course_table = dynamo.Table('Courses')

class MakeCourses(object):
    def __init__(self):
        with open('course_links.pkl', 'r') as f:
            courses = list(pickle.load(f))
        self.courses = courses

    @staticmethod
    def chunks(l, n):
        """Yield successive n-sized chunks from l."""
        for i in range(0, len(l), n):
            yield l[i:i + n]

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

    def make_courses(self, courses):
        for i in courses:
            course = course_table.get_item(Key={'Course_Id': i})
            course = course.get('Item')
            if course:
                course = course['Name']
                self.courses[i] = course\

if __name__ == '__main__':
    mc = MakeCourses()
    mc.parallel_query_reviews(mc.make_courses, POOL_SIZE)
    with open('courses.pkl', 'w') as f:
        pickle.dump(mc.courses, f)
