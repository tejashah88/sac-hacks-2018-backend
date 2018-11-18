from mongoengine import *

class SourceSchool(Document):
    name = StringField(required=True)
    code = StringField(required=True, unique=True)
    targets = ListField(ReferenceField(TargetSchool))

class TargetSchool(Document):
    name = StringField(required=True)
    code = StringField(required=True, unique=True)
    # minGPA = FloatField()
    majors = ListField(ReferenceField(Major))

class Major(Document):
    name = StringField(required=True)
    code = StringField(required=True, unique=True)
    courses = ListField(ReferenceField(CoursePair))
    target = ReferenceField(TargetSchool)

class CoursePair(Document):
    source = ReferenceField(Course)
    target = ReferenceField(Course)
    targetSchools = ListField(ReferenceField(TargetSchool))

class Course(Document):
    name = StringField(required=True)
    id = StringField(required=True)