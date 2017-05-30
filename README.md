# GolfRecs

GolfRecs is a webapp that leverages an Matrix Factorization in order to provide golfers with course recommendations based on their past reviews. GolfRecs is able to provide recommendations by location so users can enter destinations when traveling, relocating, or looking for a new course to try near their hometown.

![GolfRecs Homepage](GolfRecs_Home.png "A view of the GolfRecs homepage")

## How it works

The engine behind GolfRecs is a Matrix Factorization of over 500,000 user reviews of courses all over the world. The system utilizes a custom implementation of the ALS-WR algorithm to construct feature matrices for users and courses which can then be used to predict ratings for courses a user has yet to review. The system also implements a location filter that can limit results to courses within 100 miles of a selected location.
