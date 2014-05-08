#!/bin/python2
from bs4 import BeautifulSoup
import re
import urllib2
import json
import sys

ingredientSplit = re.compile(r'(?:[^,(]|\([^)]*\))+')
URL_PREFIX = "http://menuportal.dining.rutgers.edu/foodpro/"
outfile = sys.argv[1]

def scrapeNutritionReport(url):
	"""Scrapes a Nutrition Report page, returns name, serving, calories, ingredients"""
	page = urllib2.urlopen(url).read()
	soup = BeautifulSoup(page)
	ret = {}

	# Get item name
	try:
		ret['name'] = soup.find(id="content-text").find_all("h2")[1].string
	except AttributeError:
		pass

	# Get serving size
	try:
		ret['serving'] = soup.find(id="facts").find("p", "").string[len("Serving Size "):]
	except AttributeError:
		pass

	# Get calorie count.
	try:
		ret['calories'] = int(soup.find(id="facts").find("p", "strong").string[len("Calories "):])
	except AttributeError:
		pass

	# Get ingredient list
	try:
		e = soup.find(text=re.compile("INGREDIENTS")).parent
		p = e.parent
		e.decompose()
		ret['ingredients'] = [ing.strip() for ing in ingredientSplit.findall(p.string)]
	except AttributeError:
		pass

	return ret

def scrapeMeal(url):
	"""Parses meal, calls for scraping of each nutrition facts"""
	page = urllib2.urlopen(url).read()
	soup = BeautifulSoup(page)
	soup.prettify()
	return [scrapeNutritionReport(URL_PREFIX + link['href']) for link in
	        soup.find("div", "menuBox").find_all("a", href=True)]

def scrapeCampus(url):
	"""Calls for the scraping of the meals of a campus"""
	# TODO: Add takeout?
	meals = ('Breakfast', 'Lunch', 'Dinner')
	return {meal: scrapeMeal(url + "&mealName=" + meal) for meal in meals}

def scrape():
	"""Calls for the scraping of the menus of each campus"""
	prefix = URL_PREFIX + "pickmenu.asp?locationNum=0"
	# There doesn't seem to be a hall #2
	halls = (('Brower Commons', '1'), ('Livingston Dining Commons', '3'),
	         ('Busch Dining Hall', '4'), ('Neilson Dining Hall', '5'))
	return {hall[0]: scrapeCampus(prefix + hall[1]) for hall in halls}

output = open(outfile, 'w')
json.dump(scrape(), output, indent=1)
output.close()
