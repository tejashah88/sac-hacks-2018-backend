from flask import request
from flask_stupe import paginate#, schema_required
from flask_stupe.json import Stupeflask
from flask_cors import CORS

from fuzzywuzzy import fuzz, process

from werkzeug.contrib.cache import FileSystemCache

cache = FileSystemCache('cache-dir/', threshold=0, default_timeout=0)

#from pymongo import MongoClient
#from mongoengine import *

#from models import *

from scraper import gen_source_schools, gen_target_schools, gen_target_majors, get_course_reqs

import os
from dotenv import load_dotenv
load_dotenv()

#connect('big-data', host=os.environ.get('DB_URI'))

app = Stupeflask(__name__)
CORS(app)

# mongo = MongoClient(dbUri)
# db = mongo['database']
# schools = db['schools']
# majors = db['majors']
# courses = db['courses']

@app.route('/origin-codes', methods=['GET'])
def get_origin_codes():
	checked = cache.get(request.path)
	if checked:
		return checked

	origin_schools = gen_source_schools()
	response = {
		'status': 'success',
		'originSchools': origin_schools
	}

	cache.set(request.path, response)
	return response

@app.route('/destination-codes', methods=['GET'])
def get_destination_codes():
	source_school = request.args.get('origin', default='', type=str)

	checked = cache.get(request.path)
	if checked:
		return checked

	target_schools = gen_target_schools(source_school)
	response = {
		'status': 'success',
		'destinationSchools': target_schools
	}

	cache.set(request.path, response)
	return response

@app.route('/possible-destinations', methods=['GET'])
def get_possible_destinations():
	source_school = request.args.get('origin', default='', type=str)
	real_target_school = request.args.get('destination', default='', type=str)

	# checked = cache.get(request.path)
	# if checked:
	# 	return checked

	actual_majors = []
	if real_target_school:
		actual_majors = gen_target_majors(source_school, real_target_school)
	else:
		target_schools = gen_target_schools(source_school)
		actual_majors = []
		for target_school in target_schools:
			target_majors = gen_target_majors(source_school, target_school['code'])
			actual_majors += [*target_majors]

		actual_majors = actual_majors[:200]

		real_majors = {}
		actual_majors_strings = process.dedupe([major['name'] for major in actual_majors], threshold=90, scorer=fuzz.ratio)
		print('deduped')


		for mmajor in actual_majors:
			if mmajor['name'] in actual_majors_strings:
				real_majors[mmajor['name']] = []
				real_majors[mmajor['name']].append(mmajor['code'] + "[|]" + mmajor['destinationSchool'])

		#print(real_majors)
		print('real_majors part 1')

		for mmajor in actual_majors:
			(expected_major, score) = process.extractOne(mmajor['name'], actual_majors_strings, scorer=fuzz.ratio)
			real_majors[expected_major].append(mmajor['code'] + "[|]" + mmajor['destinationSchool'])
		print('done')

		print([*real_majors.items()][0])

		actual_majors = [{ 'name': name, 'blobs': blobs } for (name, blobs) in real_majors.items()]

		for maijer in actual_majors:
			print(maijer)
			maijer['codes'] = []
			for blob in maijer['blobs']:
				print(blob)
				[code, destination] = blob.split("[|]")
				maijer['codes'].append({
					'code': code,
					'destinationSchool': destination
				})
			del maijer['blobs']

		# for mayger in actual_majors:
		# 	courses = get_course_reqs(source_school, mayger['destinationSchool'], mayger['code'])
		# 	major['courses'] = courses

		#actual_majors = real_majors

	response = {
		'status': 'success',
		'majors': actual_majors
	}

	cache.set(request.path, response)
	return response


# @app.route('/possible-targets', methods=['GET'])
# def get_possible_target_schools():
# 	source_school = request.args.get('origin', default='', type=str)
# 	major = request.args.get('major', default='', type=str)

# 	checked = cache.get(request.path)
# 	if checked:
# 		return checked

# 	response = {
# 		'status': 'success',
# 		'source': source_school,
# 		'major': target_major
# 	}

# 	cache.set(request.path, response)
# 	return response

@app.route('/possible-majors', methods=['GET'])
def get_possible_majors():
	source_school = request.args.get('origin', default='', type=str)
	target_school = request.args.get('destination', default='', type=str)

	# checked = cache.get(request.path)
	# if checked:
	# 	return checked

	majors = gen_target_majors(source_school, target_school)
	for major in majors:
		courses = get_course_reqs(source_school, target_school, major['code'])
		major['courses'] = courses
		print(source_school, target_school, major['code'])

	final_majors = [*filter(lambda major: len(major['courses']) != 0, majors)]

	response = {
		'originSchool': source_school,
		'destinationSchool': target_school,
		'majors': final_majors
	}

	cache.set(request.path, response)
	return response


# @app.route('/get-courses', methods=['GET'])
# def get_courses():
# 	source_school = request.args.get('origin', default='', type=str)
# 	target_school = request.args.get('destination', default='', type=str)
# 	major = request.args.get('major', default='', type=str)

# 	checked = cache.get(request.path)
# 	if checked:
# 		return checked

# 	courses = get_course_reqs(source_school, target_school, major)

# 	response = {
# 		'originSchool': source_school,
# 		'destinationSchool': target_school,
# 		'major': major,
# 		'courses': courses
# 	}

# 	cache.set(request.path, response)
# 	return response

if __name__ == '__main__':
	app.run(debug=True, port=8080)