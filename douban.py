
# coding: utf-8
#!/usr/bin/env python

import sys
import re
import requests
from bs4 import BeautifulSoup
import datetime
import csv
import time
import signal

exit_flag = False
csvfile = None
    
headers = {'user-agent': 'Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/38.0'}

visited_doulist = set()
to_visited_doulist = set()
failed_doulist = set()

visited_doulist_idxs = set()
to_visited_doulist_idxs = set()
failed_doulist_idxs = set()

visted_movies = set()
to_visted_movies = set()
failed_movies = set()


def get_doulist_index_id(links):
    dlre = re.compile('http://movie.douban.com/subject/(\d+)/doulists')
    for link in links:
        url = link.get('href')
        match = re.search(dlre, url)
        if match:
            doulist_id = match.group(0)
            if doulist_id not in visited_doulist_idxs and doulist_id not in to_visited_doulist_idxs:
                to_visited_doulist_idxs.add(doulist_id)
                return doulist_id
    return None

def get_title(soup):
    title = ''
    try:
        element = soup.find('h1')
        title = element.find('span').contents[0].encode('utf8')
    except:
        title = None
    return title
    

def get_id_and_url(url):
    mid = 0
    reid = re.compile('http://movie.douban.com/subject/(\d+)')
    match = re.search(reid, url)
    if match:
        mid = match.group(1)
        url = match.group(0)    
    return (mid, url)

def get_rating(soup):
    rating = 0.0
    try:
        rating = float(soup.find(attrs={"class":"ll rating_num"}).contents[0])
    except:
        rating = 0.0
    return rating

def get_date_showing(soup):
    date_show = None
    try:
        element = soup.find('span', text="上映日期:")
        element = element.findNextSibling('span').contents[0]
        match = re.search(r'(\d+)-(\d+)-(\d+)', element)
        if match:
            date_show = datetime.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))  
    except:
        date_show = None
    return date_show

def get_imdb_link(soup):
    imdb_url = None
    try:
        imdb_url = soup.find('span', text="IMDb链接:")
        imdb_url = imdb_url.findNextSibling('a').get('href')   
    except:
        imdb_url = None
    return imdb_url

def get_num_of_votes(soup):
    num_votes = None
    try:
        num_votes = soup.find('a', href="collections")
        num_votes = int(num_votes.span.contents[0])
    except:
        num_votes = None
    return num_votes

def get_num_of_comments(soup, url):
    num_comments = None
    try:
        movie_url = url+'comments'
        num_comments = soup.find('a', href=movie_url).contents[0]
        renum = re.compile(u'全部 (\d+) 条')
        match = re.search(renum, num_comments)
        if match: 
            num_comments = int(match.group(1))
    except:
        num_comments = None
    return num_comments

def get_num_of_watched(soup, url):
    num_watched = None
    try:
        movie_url = url+'collections'
        num_watched = soup.find('a', href=movie_url).contents[0]
        renum = re.compile(u'(\d+)人看过')
        match = re.search(renum, num_watched)
        if match: 
            num_watched = int(match.group(1))
    except:
        num_watched = None
    return num_watched


def get_num_of_wanted(soup, url):
    num_want = None
    try:
        movie_url = url+'wishes'
        num_want = soup.find('a', href=movie_url).contents[0]
        renum = re.compile(u'(\d+)人想看')
        match = re.search(renum, num_want)
        if match: 
            num_want = int(match.group(1)) 
    except:
        num_want = None
    return num_want


def get_soup_content(url):
    soup = None
    try:
        html = requests.get(url, headers=headers, timeout=10)
        if html.status_code != 200:
            print 'get %s failed: %d '%(url, html.status_code)
            return None
        soup = BeautifulSoup(html.text)
    except:
        soup = None
    return soup
    

def get_movie_detail_info(url):
    movie_info = {}
    
    soup = get_soup_content(url)
    if not soup:
        print 'get movie info failed at ' + url
        return None
    
    movie_info['title'] = get_title(soup)
    movie_info['movie_id'], movie_info['movie_url'] = get_id_and_url(url)
    movie_info['rating'] = get_rating(soup)
    movie_info['date_show'] = get_date_showing(soup)
    movie_info['imdb_url'] = get_imdb_link(soup)
    movie_info['num_votes'] = get_num_of_votes(soup)
    movie_info['num_comments'] = get_num_of_comments(soup, url)
    movie_info['num_watched'] = get_num_of_watched(soup, url)
    movie_info['num_want'] = get_num_of_wanted(soup, url)   
    l = soup.find_all("a", text="全部")
    get_doulist_index_id(l);

    return movie_info


def get_doulist_ids_from_doulist_idx(url):    
    soup = get_soup_content(url)
    if not soup:
        print 'get movie info failed at ' + url
        return None

    links = soup.find_all("a")
    dlre = re.compile('http://www.douban.com/doulist/(\d+)/')
    for link in links:
        link_url = link.get('href')
        match = re.search(dlre, link_url)
        if match:
            doulist_id = match.group(0)
            ret = doulist_id
            if doulist_id not in visited_doulist and doulist_id not in to_visited_doulist:
                to_visited_doulist.add(doulist_id)
  

def get_movie_ids_from_doulist(links):
    dlre = re.compile('http://movie.douban.com/subject/(\d+)/')
    for link in links:
        url = link.get('href')
        match = re.search(dlre, url)
        if match:
            movie_id = match.group(0)
            ret = movie_id
            if movie_id not in visted_movies and movie_id not in to_visted_movies:
                to_visted_movies.add(movie_id)


def get_doulist_ids_from_doulist(links):
    dlre = re.compile('http://www.douban.com/doulist/(\d+)/')
    for link in links:
        url = link.get('href')
        match = re.search(dlre, url)
        if match:
            url = match.group(0)
            ret = url
            if url not in visited_doulist and url not in to_visited_doulist:
                to_visited_doulist.add(url)

                
def parse_doulist_page(url):
    soup = get_soup_content(url)
    if not soup:
        print 'get movie info failed at ' + url
        return None
    
    movie_links = soup.find_all("a")
    ret = get_movie_ids_from_doulist(movie_links)
    try:
        paginator = soup.find(attrs={"class":"paginator"})
        if paginator:
            doulist_links = paginator.find_all("a")
            get_doulist_ids_from_doulist(doulist_links)
    except:
        print "Unexpected error:", sys.exc_info()
        print 'parse doulist page failed: %s'%url
        return None
    return ret


def list_writer(file_name, lst):
    f = open(file_name, 'wb+')
    for line in lst:
        f.write(line+'\n')
    f.close()

    
def load_list(file_name, lst):
    try:
        f = open(file_name, 'r')
        for line in f:
            url = line[:-1]
            lst.add(url)
    except:
        pass
    
    
def load_saved_lists():
    load_list('visited_doulist.txt', visited_doulist)
    load_list('to_visited_doulist.txt', to_visited_doulist)
    load_list('failed_doulist.txt', failed_doulist)
    
    load_list('visited_doulist_idxs.txt', visited_doulist_idxs)
    load_list('to_visited_doulist_idxs.txt', to_visited_doulist_idxs)
    load_list('failed_doulist_idxs.txt', failed_doulist_idxs)
    
    load_list('visted_movies.txt', visted_movies)
    load_list('to_visted_movies.txt', to_visted_movies)
    load_list('failed_movies.txt', failed_movies)

def save_progress():
    list_writer('visited_doulist.txt', visited_doulist)
    list_writer('to_visited_doulist.txt', to_visited_doulist)
    list_writer('failed_doulist.txt', failed_doulist)
    
    list_writer('visited_doulist_idxs.txt', visited_doulist_idxs)
    list_writer('to_visited_doulist_idxs.txt', to_visited_doulist_idxs)
    list_writer('failed_doulist_idxs.txt', failed_doulist_idxs)
    
    list_writer('visted_movies.txt', visted_movies)
    list_writer('to_visted_movies.txt', to_visted_movies)
    list_writer('failed_movies.txt', failed_movies)


def signal_handler(signal, frame):
    global exit_flag
    global csvfile
    print('Ctrl+C pressed, stopping the worker....')
    exit_flag = True
    csvfile.close() 
    save_progress()
    sys.exit(0)
 

def get_movie_info_worker():
    global exit_flag
    global csvfile
    TOME_INTERVAL=4
    load_saved_lists()
    if len(to_visted_movies) == 0:  
        parse_doulist_page('http://www.douban.com/doulist/240962/')
        
    info = get_movie_detail_info('http://movie.douban.com/subject/3592854/')
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    csvfile = open('movie_db' + timestamp +'.csv', 'wb+')
    writer = csv.DictWriter(csvfile, fieldnames=info.keys())
    writer.writeheader()

    num_of_movies = 0
    num_of_doulistidx = 0
    num_of_doulist = 0
    
    signal.signal(signal.SIGINT, signal_handler)
    
    while((len(to_visted_movies) or 
           len(to_visited_doulist_idxs) or 
           len(to_visited_doulist) 
          ) and not exit_flag):
    
        for url in to_visted_movies.copy():
            info = get_movie_detail_info(url)
            if info:
                if url not in visted_movies:
                    visted_movies.add(url)
                writer.writerow(info)
                num_of_movies += 1
                print 'get %d movies: %s'% (num_of_movies, info['title'])
            else:
                print "failed to get movie: ", url
                failed_movies.add(url)
            to_visted_movies.remove(url)
            time.sleep(TOME_INTERVAL)

        for url in to_visited_doulist_idxs.copy():
            ret = get_doulist_ids_from_doulist_idx(url)
            if url not in visited_doulist_idxs:
                visited_doulist_idxs.add(url)
                num_of_doulistidx += 1
                if len(to_visited_doulist) > 50:
                    break
            print 'get %d doulist index'%num_of_doulistidx
            to_visited_doulist_idxs.remove(url)
            time.sleep(TOME_INTERVAL)

        for url in to_visited_doulist.copy():
            ret = parse_doulist_page(url)
            if  url not in visited_doulist:
                visited_doulist.add(url)
                if len(to_visted_movies) > 50:
                    break
                num_of_doulist += 1
            print 'get %d doulist page...'%num_of_doulist

            to_visited_doulist.remove(url)
            time.sleep(TOME_INTERVAL)

    csvfile.close() 
    save_progress()

if __name__ == '__main__':
    get_movie_info_worker()
