#!/usr/bin/env python3
from bs4 import BeautifulSoup
from re import compile
import requests
import gzip
import boto3
import pendulum
import json

ingredientSplit = compile(r'(?:[^,(]|\([^)]*\))+')
URL_PREFIX = "http://menuportal.dining.rutgers.edu/foodpro/"

knownUrls = {}
hit = 0
miss = 0

def scrapeNutritionReport(url):
    """Scrapes a Nutrition Report page, returns name, serving, calories, ingredients"""
    #print("scrapeNutritionReport {0}".format(url))
    if knownUrls.get(url) is not None:
        global hit
        hit += 1
        return knownUrls[url]
    else:
        global miss
        miss += 1
    
    try:
        page = requests.get(url)
    except ConnectionError:
        return {}
    
    soup = BeautifulSoup(page.content)
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
        e = soup.find(text=compile("INGREDIENTS")).parent
        p = e.parent
        e.decompose()
        ret['ingredients'] = [ing.strip() for ing in ingredientSplit.findall(p.string)]
    except AttributeError:
        pass
    
    knownUrls[url] = ret

    return ret

def scrapeMeal(url, dicts=0):
    """Parses meal, calls for scraping of each nutrition facts"""
    #print("scrapeMeal: {0} {1}".format(url, dicts))
    ret={}
    page = requests.get(url)
    soup = BeautifulSoup(page.content)
    soup.prettify()
    for link in soup.find("div", "menuBox").find_all("a", href=True):
        category = link.find_previous("p", style="margin: 3px 0;").string[3:-3]
        if not ret.get(category):
            ret[category]=[]
        ret[category].append(scrapeNutritionReport(URL_PREFIX+link['href']))
    #print("known urls so far:")
    #pprint(knownUrls)
    if dicts:
        return ret
    else:
        return [{
            "genre_name" : category,
            "items" : ret[category]
        } for category in ret.keys()]

def scrapeCampus(url, dicts=0):
    """Calls for the scraping of the meals of a campus"""
    #print("scrapeCampus: {0} {1}".format(url, dicts))
    meals = ('Breakfast', 'Lunch', 'Dinner', 'Knight Room')
    if dicts:
        return {meal: scrapeMeal(url + "&mealName=" + meal.replace(' ', '+')) for meal in meals}
    else:
        return [{
            "meal_name" : meal,
            "genres" : scrapeMeal(url + "&mealName=" + meal.replace(' ', '+'), dicts=0)
        } for meal in meals]

def scrape(dicts=0):
    """Calls for the scraping of the menus of each campus"""
    #print("scrape: {0}".format(dicts))
    prefix = URL_PREFIX + "pickmenu.asp?locationNum=0"
    # There doesn't seem to be a hall #2
    halls = (('Brower Commons', '1'), ('Livingston Dining Commons', '3'),
             ('Busch Dining Hall', '4'), ('Neilson Dining Hall', '5'))
    if dicts:
        return {hall[0]: scrapeCampus(prefix + hall[1]) for hall in halls}
    else:
        return [{
            "location_name" : hall[0],
            "meals" : scrapeCampus(prefix + hall[1], dicts=0)
        } for hall in halls]

def main():
    s3 = boto3.resource("s3")
    rufood_bucket = s3.Bucket("rufood")

    finaldict = scrape(dicts=True)

    timestamp = pendulum.now('US/Eastern').format('%Y-%m-%d %H:%M:%S')

    print("hits: {0}, misses: {1}, percent hit: {2}".format(hit, miss, (hit / (hit + miss))))

    finaljsonbytes = json.dumps(finaldict, sort_keys=True).encode()
    finaljsonbytescompressed = gzip.compress(finaljsonbytes, compresslevel=9)
    rufood_bucket.put_object(Key='latest.json', Body=finaljsonbytes, ACL='public-read', ContentType='application/json')
    rufood_bucket.put_object(Key='latest.json.gz', Body=finaljsonbytescompressed, ACL='public-read', ContentType='application/json', ContentEncoding='gzip', CacheControl='max-age=300')
    rufood_bucket.copy({'Bucket': 'rufood', 'Key': 'latest.json'}, '{0}.json'.format(timestamp))
    rufood_bucket.copy({'Bucket': 'rufood', 'Key': 'latest.json.gz'}, '{0}.json.gz'.format(timestamp))

if __name__=="__main__":
    main()
