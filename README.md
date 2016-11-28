# GolfRecs

GolfRecs is a webapp that leverages an Item-Item Collaborative Filter in order to provide golfers with course recommendations based on their past reviews. GolfRecs is able to provide recommendations by location so users can enter destinations when traveling, relocating, or looking for a new course to try near their hometown.

![GolfRecs Homepage](GolfRecs_Home.png "A view of the GolfRecs homepage")

## How it works

The engine behind GolfRecs is an Item-Item collaborative filter built from over 500,000 user reviews of courses all over the world. The system utilizes cosine_similarity to identify courses that are similar to those which a user has already rated highly and then filters those by location to ensure that only courses within 100 miles of a users desired location are returned. Currently the system is only setup to recommend courses for locations within the United States, but this will be expanded soon.
