#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import re
import string
import random
import requests
from bs4 import BeautifulSoup
import datetime
import csv
import time
import signal
import threading
import os

visited_doulist = set()
to_visit_doulist = set()

visited_doulist_idxs = set()
to_visit_doulist_idxs = set()

visited_movie = set()
to_visit_movie = set()

to_visit_people = set()
visited_people = set()

to_visit_peoplelist = set()
visited_peoplelist = set()

list_lock = threading.Lock()
file_lock = threading.Lock()

people_pattern = re.compile('http://movie.douban.com/people/(\w+)/')
movie_pattern = re.compile('http://movie.douban.com/subject/(\d+)/')
list_pattern = re.compile('http://www.douban.com/doulist/(\d+)/')
index_pattern = re.compile('http://movie.douban.com/subject/(\d+)/doulists')
peoplelist_pattern = re.compile('http://movie.douban.com/subject/(\d+)/collections')

def add_to_set(id, to_visit_set, visited_set):
    list_lock.acquire()
    if id not in visited_set:
        to_visit_set.add(id)
    list_lock.release()


def update_visit_data(id, to_visit_set, visited_set):
    list_lock.acquire()
    if id not in visited_set:
        visited_set.add(id)
    if id in to_visit_set:
        to_visit_set.remove(id)
    list_lock.release()


def parse_webpage_to_list(soup):
    links = soup.find_all('a')
    for link in links:
        try:
            link_url = link.get('href')
        except:
            continue   

        if not link_url:
            continue
        #match people
        match = re.search(people_pattern, link_url)
        if match:
            id = match.group(1)
            add_to_set(id, to_visit_people, visited_people)

        #match movie
        match = re.search(movie_pattern, link_url)
        if match:
            id = match.group(0) 
    #         print id
            add_to_set(id, to_visit_movie, visited_movie)
        
        #match doulist
        match = re.search(list_pattern, link_url)
        if match:
            id = link_url       
            add_to_set(id, to_visit_doulist, visited_doulist)

        #match doulist index
        match = re.search(index_pattern, link_url)
        if match:
            id = link_url
            add_to_set(id, to_visit_doulist_idxs, visited_doulist_idxs)

        #match people list
        match = re.search(peoplelist_pattern, link_url)
        if match:
            id = link_url
            add_to_set(id, to_visit_peoplelist, visited_peoplelist)


def get_soup_content(url):
    print 'visiting ' + url
    soup = None
    cookie = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(11))
    headers = {'Cookie': 'bid=' + '"' + str(cookie) + '"'}    
    try:
        html = requests.get(url, headers=headers, timeout=10)
        if html.status_code != 200:
            print 'get %s failed: %d ' % (url, html.status_code)
        else:
            soup = BeautifulSoup(html.text)
            parse_webpage_to_list(soup)
    except Exception as e:
        print e
        soup = None
    return soup


def parse_peoplelist_page(url):
    soup = get_soup_content(url)
    if not soup:
        return
    
    try:
        paginator = soup.find(attrs={"class":"paginator"})
        next_page = paginator.span.a.get('href')
        
        match = re.search(peoplelist_pattern, next_page)
        if match:
            pid = next_page
            add_to_set(pid, to_visit_peoplelist, visited_peoplelist)

    except:
        pass
    
    update_visit_data(url, to_visit_peoplelist, visited_peoplelist)


def save_user_ratings(file_name, user_id, rating_list):
    file_lock.acquire()
    with open(file_name, "a+") as user_ratings:
        for (mid, rating, date_rated) in rating_list:
            user_ratings.write('{},{},{},{}\n'.format(user_id, mid, rating, date_rated))
    file_lock.release()

            
def parse_item_rating_info(item):
    try:
        rating = 0
        mid = 0
        date_rated = datetime.datetime(1900, 1, 1)
        info = item.find(attrs={"class":"info"})
        url = info.ul.li.a.get('href')

        match = re.search(movie_pattern, url)
        if match:
            mid = match.group(1)
        date_span = info.find(attrs={"class":"date"})
        rate_span = date_span.parent.span    
        date_rated = datetime.datetime.strptime(date_span.contents[0],'%Y-%m-%d')    
        match = re.search(r'rating(\d)-t', str(rate_span))
        if match:
            rating = match.group(1)
        return mid, rating, date_rated
    except Exception as e:
        return None


def get_user_movie_history(uid):
    print "getting rating history of user %s ..."%str(uid)
    start_url = 'http://movie.douban.com/people/'+str(uid)+'/collect'
    user_movie_list = set()
    user_visited_movie = set()
    
    next_url = parse_user_movie_history(start_url, user_movie_list, user_visited_movie)
    while(next_url):
        next_url = parse_user_movie_history(next_url, user_movie_list, user_visited_movie)
        
    save_user_ratings("user_ratings.txt", uid, user_movie_list)
    update_visit_data(id, to_visit_people, visited_people)

    print "getting rating history of user %s done"%str(uid)
    return user_movie_list


def parse_user_movie_history(url, user_movie_list, user_visited_movie):
    soup = get_soup_content(url)
    if not soup:
        return url

    next_url = None
    paginator = soup.find(attrs={"class":"paginator"})
    try:
        next_page = paginator.find(attrs={"class":"next"}).a
        if next_page:
            next_url = next_page.get('href')
    except Exception as e:
        print e
  
    mlist = soup.find(attrs={"class":"grid-view"})
    if mlist and mlist.children:
        for item in mlist.children:
            try:
                (mid, rating, date_rated) = parse_item_rating_info(item)
                if mid not in user_visited_movie:
                    user_visited_movie.add(mid)
                    user_movie_list.add((mid, rating, date_rated))

            except Exception as e:
                pass
        
    parse_webpage_to_list(soup)
        
    return next_url


def get_doulist_index_id(links):
    dlre = re.compile(r'http://movie.douban.com/subject/(\d+)/doulists')
    for link in links:
        url = link.get('href')
        match = re.search(dlre, url)
        if match:
            doulist_id = match.group(0)
            if doulist_id not in visited_doulist_idxs and doulist_id not in to_visit_doulist_idxs:
                to_visit_doulist_idxs.add(doulist_id)
                return doulist_id
    return None


def get_title(soup):
    title = ''
    try:
        element = soup.find('h1')
        title = element.find('span').contents[0].encode('utf8')
    except:
        print "Unexpected error:", sys.exc_info()[0]
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
        rating = float(soup.find(attrs={"class": "ll rating_num"}).contents[0])
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
            date_show = datetime.date(
                int(match.group(1)), int(match.group(2)), int(match.group(3)))
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
        movie_url = url + 'comments'
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
        movie_url = url + 'collections'
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
        movie_url = url + 'wishes'
        num_want = soup.find('a', href=movie_url).contents[0]
        renum = re.compile(u'(\d+)人想看')
        match = re.search(renum, num_want)
        if match:
            num_want = int(match.group(1))
    except:
        num_want = None
    return num_want


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
    get_doulist_index_id(l)
        
    update_visit_data(url, to_visit_movie, visited_movie) 

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
            if doulist_id not in visited_doulist and doulist_id not in to_visit_doulist:
                to_visit_doulist.add(doulist_id)

    update_visit_data(url, to_visit_doulist_idxs, visited_doulist_idxs)


def get_movie_ids_from_doulist(links):
    try:
        dlre = re.compile('http://movie.douban.com/subject/(\d+)/')
        for link in links:
            url = link.get('href')
            match = re.search(dlre, url)
            if match:
                movie_id = match.group(0)
                ret = movie_id
                if movie_id not in visited_movie and movie_id not in to_visit_movie:
                    to_visit_movie.add(movie_id)
    except Exception as e:
        pass


def get_doulist_ids_from_doulist(links):
    try:
        dlre = re.compile('http://www.douban.com/doulist/(\d+)/')
        for link in links:
            url = link.get('href')
            match = re.search(dlre, url)
            if match:
                url = match.group(0)
                ret = url
                if url not in visited_doulist and url not in to_visit_doulist:
                    to_visit_doulist.add(url)
    except Exception as e:
        pass


def parse_doulist_page(url):
    soup = get_soup_content(url)
    if not soup:
        print 'get doulist failed at ' + url
        return None

    movie_links = soup.find_all("a")
    ret = get_movie_ids_from_doulist(movie_links)
    try:
        paginator = soup.find(attrs={"class": "paginator"})
        if paginator:
            doulist_links = paginator.find_all("a")
            get_doulist_ids_from_doulist(doulist_links)
    except:
        print 'parse doulist page failed: %s' % url
    
    update_visit_data(url, to_visit_doulist, visited_doulist)
    

def list_writer(file_name, lst):
    f = open(file_name, 'wb+')
    for line in lst:
        f.write(line + '\n')
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
    load_list('to_visit_doulist.txt', to_visit_doulist)
    # load_list('failed_doulist.txt', failed_doulist)

    load_list('visited_doulist_idxs.txt', visited_doulist_idxs)
    load_list('to_visit_doulist_idxs.txt', to_visit_doulist_idxs)
    # load_list('failed_doulist_idxs.txt', failed_doulist_idxs)

    load_list('visited_movie.txt', visited_movie)
    load_list('to_visit_movie.txt', to_visit_movie)
    # load_list('failed_movies.txt', failed_movies)

    load_list('visited_people.txt', visited_people)
    load_list('to_visit_people.txt', to_visit_people)

    load_list('to_visit_peoplelist.txt', to_visit_peoplelist)
    load_list('visited_peoplelist.txt', visited_peoplelist)
    print "Progress loaded."

def save_progress():
    list_writer('visited_doulist.txt', visited_doulist)
    list_writer('to_visit_doulist.txt', to_visit_doulist)
    # list_writer('failed_doulist.txt', failed_doulist)

    list_writer('visited_doulist_idxs.txt', visited_doulist_idxs)
    list_writer('to_visit_doulist_idxs.txt', to_visit_doulist_idxs)
    # list_writer('failed_doulist_idxs.txt', failed_doulist_idxs)

    list_writer('visited_movie.txt', visited_movie)
    list_writer('to_visit_movie.txt', to_visit_movie)
    # list_writer('failed_movies.txt', failed_movies)

    list_writer('visited_people.txt', visited_people)
    list_writer('to_visit_people.txt', to_visit_people)

    list_writer('to_visit_peoplelist.txt', to_visit_peoplelist)
    list_writer('visited_peoplelist.txt', visited_peoplelist)
    
    print "Progress saved."



def user_rating_history_worker(pid):
    get_user_movie_history(pid)


def process_user_rating_history():
    print "start to get get rating data..."
    while(True):
        if len(to_visit_people) == 0:
            print 'no work to do, sleep 10 seconds'
            time.sleep(10)
        threads = []
        for i in range(3):
            if len(to_visit_people):
                list_lock.acquire()
                pid = to_visit_people.pop()
                visited_people.add(pid)
                list_lock.release()
                t = threading.Thread(target=user_rating_history_worker, args=(pid,))
                threads.append(t)
                t.start()
        
        i = 0
        for thread in threads:
            thread.join()
            i += 1
            print "people thread join %d"%i

def user_rating_thread():
    t = threading.Thread(target=process_user_rating_history)
    t.start()


def write_movie_record(record, db_filename):
        with open(db_filename, 'a+') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=record.keys())
            writer.writerow(record)

def movie_detail_info_worker(url, db_filename):
    
    info = get_movie_detail_info(url)
    if info:
        file_lock.acquire()
        print 'write movie to file'
#         writer.writerow(info)
        write_movie_record(info, db_filename)
        file_lock.release()
        print 'got %d movies: %s' % (len(visited_movie), info['title'])
    else:
        print "failed to get movie: ", url

def process_movie_detail_info(db_filename):
    print "start to get movie info...."
    while(True):
        if len(to_visit_movie) == 0:
            print "no work to do, sleep 10 seconds."
            time.sleep(10)
        threads = []
        for i in range(3):
            if len(to_visit_movie):
                list_lock.acquire()
                mid = to_visit_movie.pop()
                visited_movie.add(mid)
                list_lock.release()
                t = threading.Thread(target=movie_detail_info_worker, args=(mid, db_filename))
                threads.append(t)
                t.start()
        
        i = 0
        for thread in threads:
            thread.join()
            i += 1
            print "movie info thread join %d"%i

def movie_info_thread(db_filename):
    t = threading.Thread(target=process_movie_detail_info, args=(db_filename, ))
    t.start()

def get_movie_info_worker():

    exit_flag = False
    db_filename = 'movie_db.csv'
    
    def signal_handler(signal, frame):
        print('Ctrl+C pressed, stopping the worker....')
        exit_flag = True
        csvfile.close()
        save_progress()
        sys.exit(0)
        
    load_saved_lists()
    if len(to_visit_movie) == 0:
        parse_doulist_page('http://movie.douban.com/')

    info = get_movie_detail_info('http://movie.douban.com/subject/3592854/')
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    import os.path
    
    if not os.path.isfile(db_filename):
        csvfile = open(db_filename, 'w+')
        writer = csv.DictWriter(csvfile, fieldnames=info.keys())
        writer.writeheader()
        csvfile.close()

    signal.signal(signal.SIGINT, signal_handler)

    user_rating_thread()
    movie_info_thread(db_filename)
    while((len(to_visit_movie) or
           len(to_visit_doulist_idxs) or
           len(to_visit_doulist) or
           len(to_visit_peoplelist) or
           len(to_visit_people)) 
           and not exit_flag):

        for url in to_visit_peoplelist.copy():  
            parse_peoplelist_page(url)
            print 'got %d peoplelist page' % len(visited_peoplelist)
            if to_visit_people > 50:
                break
        # while(len(to_visit_movie)):
        # 	process_movie_detail_info(db_filename)
        # while(len(to_visit_people)) 
        # 	process_user_rating_history()
#         for pid in to_visit_people.copy():
#             get_user_movie_history(pid)
#             print 'got %d people history' % len(visited_people)
#             if to_visit_movie > 50:
#                 break

        
#         for url in to_visit_movie.copy():
#             info = get_movie_detail_info(url)
#             if info:
#                 writer.writerow(info)
#                 print 'got %d movies: %s' % (len(visited_movie), info['title'])
#             else:
#                 print "failed to get movie: ", url
# #             if to_visit_people > 50:
#                 break

        for url in to_visit_doulist_idxs.copy():
            get_doulist_ids_from_doulist_idx(url)
            print 'got %d doulist index' % len(visited_doulist_idxs)
            if len(to_visit_doulist) > 50:
                break
            
        for url in to_visit_doulist.copy():
            parse_doulist_page(url)
            print 'got %d doulist page' % len(visited_doulist)
            if len(to_visit_movie) > 50:
                break

    csvfile.close()
    save_progress()

if __name__ == '__main__':
    get_movie_info_worker()
