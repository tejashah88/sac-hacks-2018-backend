from requests import get
from requests.exceptions import RequestException
from contextlib import closing
from bs4 import BeautifulSoup

import json

from string import Template
import os

def simple_get(url, type='binary'):
	"""
	Attempts to get the content at `url` by making an HTTP GET request.
	If the content-type of response is some kind of HTML/XML, return the
	text content, otherwise return None.
	"""
	try:
		with closing(get(url, stream=True)) as resp:
			if is_good_response(resp):
				return resp.content if type == 'binary' else resp.text
			else:
				return None

	except RequestException as e:
		print('Error during requests to {0} : {1}'.format(url, str(e)))
		return None


def is_good_response(resp):
	"""
	Returns True if the response seems to be HTML, False otherwise.
	"""
	content_type = resp.headers['Content-Type'].lower()
	return (resp.status_code == 200
			and content_type is not None
			and content_type.find('html') > -1)

def load_parsable_html(filename):
	html = BeautifulSoup(open(filename), 'html.parser')
	return html

def get_parsable_html(url):
	raw_html = simple_get(url)
	html = BeautifulSoup(raw_html, 'html.parser')
	return html

def ensure_write_file(filename, contents):
	os.makedirs(os.path.dirname(filename), exist_ok=True)
	with open(filename, "w") as f:
		f.write(contents)

######################################

def gen_source_schools():
	html = get_parsable_html("http://www.assist.org/web-assist/welcome.html")
	source_schools = []

	for option in html.select('option'):
		if option['value']:
			source_schools.append({
				'name': option.text,
				'code': option['value'].split(".")[0]
			})
	return source_schools

def gen_target_schools(source_school):
	html = get_parsable_html("http://web2.assist.org/web-assist/{0}.html".format(source_school))
	target_schools = []

	for option in html.select('form[name="other_inst"] option'):
		if option['value'] and "From:" not in option.text:
			#.replace("From:\xa0", "") \
			text = option.text \
				.replace("To:\xa0", "") \
				.strip()
			params = option['value'] \
				.split("?")[1] \
				.split("&")
			final_param = [*filter(lambda field: 'oia' in field, params)][0]
			code = final_param.split("=")[1]
			target_schools.append({
				'name': text,
				'code': code
			})
	return target_schools

def gen_target_majors(source_school, target_school):
	# ay is set to 16-17 to get latest agreement
	url = "http://web2.assist.org/web-assist/articulationAgreement.do?inst1=none&inst2=none&ia={0}&ay=16-17&oia={1}&dir=1"
	html = get_parsable_html(url.format(source_school, target_school))
	target_majors = []

	for option in html.select('form[name="major"] option'):
		if option['value'] and option['value'] != '-1':
			target_majors.append({
				'name': option.text.strip(),
				'code': option['value'],
				'destinationSchool': target_school
			})
	return target_majors

from Naked.toolshed.shell import execute_js, muterun_js


def get_course_reqs(source_school, target_school, major):
	url = Template("http://web2.assist.org/cgi-bin/REPORT_2/Rep2.pl?ia=$src&oia=$target&sia=$src&ria=$target&dora=$major&aay=16-17&ay=16-17&event=19&agreement=aa&dir=1&sidebar=false&rinst=left&mver=2&kind=5&dt=2")
	html = get_parsable_html(url.substitute(src=source_school, target=target_school, major=major))
	source_courses = []
	target_courses = []
	course_map = {}

	cmd = './src/agreement-parser/agreement-parser.js "' + '" "'.join([source_school, target_school, major]) + '"'
	response = muterun_js(cmd)

	if response.exitcode != 0:
		raise Exception(response.stderr)

	json_string = response.stdout.decode('utf-8')
	json_res = json.loads(json_string)

	# clean json

	def clean_courses(course_reqs):
		for course_req in course_reqs:
			if 'relation' in course_req:
				# parallel and/or
				# dun vorry bout it boi
				del course_req['relation']
				del course_req['parts']
			elif 'relation' in course_req['origin'] or 'relation' in course_req['destination']:
				# and/or
				# dun vorry bout it boi
				del course_req['origin']
				del course_req['destination']
			else:
				if 'valid' in course_req['origin'] and course_req['origin']['valid'] == False:
					del course_req['origin']
					del course_req['destination']
				elif 'valid' in course_req['destination'] and course_req['destination']['valid'] == False:
					del course_req['origin']
					del course_req['destination']
				else:
					if 'articulated' not in course_req['origin']:
						course_req['origin']['articulated'] = True
					if 'articulated' not in course_req['destination']:
						course_req['destination']['articulated'] = True


		return [*filter(lambda item: bool(item), course_reqs)]

	json_res['required'] = clean_courses(json_res['required'])
	if json_res.get('recommended'):
		json_res['recommended'] = clean_courses(json_res['recommended'])

	return json_res['required']

if __name__ == "__main__":
	course_reqs = get_course_reqs('DIABLO', 'UCB', 'ETH STD')#'DIABLO', 'UCB', 'EECS')
	print(json.dumps(course_reqs, indent=4))
#     total = 0
#     source_schools = gen_source_schools()
#     print(len(source_schools))
#     for sschool in source_schools:
#         target_schools = gen_target_schools(sschool['code'])
#         print("  " + str(len(target_schools)))
#         for tschool in target_schools:
#             target_majors = gen_target_majors(sschool['code'], tschool['code'])
#             print("    " + str(len(target_majors)))
#             total += len(target_majors)

#             # for major in target_majors:
#             #     course_req_page = get_course_reqs_raw(sschool, tschool, major)
#             #     ensure_write_file("./data/raw/{0}/{1}/{2}.html".format(sschool['code'], tschool['code'], major['code']), course_req_page)
#                 #print("{0} => {1} => {2}".format(sschool['code'], tschool['code'], major))