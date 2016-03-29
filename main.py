import urllib2
import urllib
import re
import subprocess
import shlex
import datetime
import sys
import os
import ssl
import string
from time import sleep
from random import randint
from tvdb import Tvdb

class rssDownloader:
    
    def getOnlineContent(self, URL):
        self.history("Retriving: " + URL)
            
        connSettings = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        connSettings.load_verify_locations(cafile="cert.pem")
        connSettings.load_default_certs()
        if connSettings.cert_store_stats()['x509_ca'] == 0:
            self.history("Error reading in CA bundle! Please check your CA bundle or CA bundle environmental path.")
            return False
                
        header = { "user-agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.103 Safari/537.36"}
        
        req = urllib2.Request(URL, headers=header)
        
        try:
            handler = urllib2.urlopen(req, timeout=10)
        except:
            self.history("Trying connection with SSL...")
            try:
                handler = urllib2.urlopen(req, timeout=10, context=connSettings)
            except:
                self.history("Error contacting server. Please try again later and/or check your internet connection.")
                return False
        try:
            result = handler.read()
        except:
            self.history("Error in reading data from server.")
            return False
        if len(result) > 0:
            return result
        else:
            return False
    
    def getCalendarInfo(self, filterDate):
        data = self.getOnlineContent("https://episodecalendar.com/en/rss_feed/heathen711@me.com")
        data = data.replace('\n', '')
        items = re.findall("<item>([\s\w\W]*?)</item>", data)
        if items:
            entries = []
            for item in items:
                entry = {}
                parts = re.findall("<(?P<name>.*?)>([\s\w\W]*?)</(?P=name)", item)
                for part in parts:
                    entry[part[0]] = part[1]
                entry['binaryDate'] = datetime.datetime.strptime(entry['pubDate'], "%a, %d %b %Y %H:%M:%S %Z")
                if entry['binaryDate'] >= filterDate:
                    if 'episodes' in entry.keys():
                        tempEpisodes = []
                        episodes = re.findall("<episode>([\s\w\W]*?)</episode>", entry['episodes'])
                        for episode in episodes:
                            tempEpisodes.append({})
                            parts = re.findall("<(?P<name>.*?)>([\s\w\W]*?)</(?P=name)", episode)
                            for part in parts:
                                tempEpisodes[-1][part[0]] = part[1]
                        for episode in tempEpisodes:
                            entries.append(episode)
        return entries 
    
    def calculateFullEpisodeCount(self, show):
        tvdbHandler = Tvdb(apikey = '4E7A4FBBC8CF4D74')
        test = show['title']
        good = False
        while True:
            seasonInfo = []
            try:
                tvdbHandler[test]
                good = True
            except:
                good = False
            if good:
                bottomSeason = tvdbHandler[test].keys()[0]
                topSeason = tvdbHandler[test].keys()[-1]
                if bottomSeason != 0:
                    for filler in range(0, bottomSeason):
                        seasonInfo.append(0)
                for entry in range(bottomSeason, topSeason+1):
                    seasonInfo.append(tvdbHandler[test][entry].keys()[-1])
                
                fullEpisodeNumber = 0
                for season in range(1, show['season']):
                    fullEpisodeNumber += seasonInfo[season] - 1
                fullEpisodeNumber += show['episode']
                return fullEpisodeNumber
            else:
                test = test.split(' ')
                if len(test) > 1:
                    test = ' '.join(test[0:-1])
                else:
                    self.history("Error finding tv show: " + show['title'])
                    return -1
    
    
    def updateLinkTableShows(self, shows, database):
        for show in shows:
            showID = show['show'] + ' - ' + show['format']
            self.history(showID)
            alreadyAdded = False
            for entry in self.linkTable:
                if entry['id'] == showID:
                    alreadyAdded = True
                    break
            if not alreadyAdded:
                foundMatch = False
                for info in database:
                    if show['show'].lower() in info['shows']:
                        foundMatch = True
                        entry = {}
                        entry['title'] = show['show']
                        entry['SeEp'] = show['format']
                        entry['season'] = int(show['season_number'])
                        entry['episode'] = int(show['episode_number'])
                        entry['fullEpisodeNumber'] = self.calculateFullEpisodeCount(entry)
                        entry['id'] = show['show'] + ' - ' + show['format']
                        entry['url'] = info['link'].replace("%%QUERY%%", urllib.quote_plus(show['show']))
                        entry['url'] = entry['url'].replace("%%SEASON%%", urllib.quote_plus(str(entry['season']).zfill(2)))
                        entry['url'] = entry['url'].replace("%%EPISODE%%", urllib.quote_plus(str(entry['episode']).zfill(2)))
                        entry['url'] = entry['url'].replace("%%FULLCOUNT%%", urllib.quote_plus(str(entry['fullEpisodeNumber'])))
                        self.linkTable.append(entry)
                if not foundMatch:
                    self.history("Did not find a matching show in database for: " + showID)
    
    def history(self, message):
        log = open("rss.log", 'a')
        log.write(str(datetime.datetime.now()) + " - " + message + "\n")
        log.close()
        if not self.service:
            print message
    
    def downloadTorrent(self, torrentURL):
        tempFile = "/share/Transmission/autoDownload/" + str(randint(0,5000)) + ".torrent"
        urlHandler = urllib2.urlopen(torrentURL)
        fileHandler = open(tempFile, 'wb')
        while True:
            buffer = urlHandler.read(8192)
            if not buffer:
                break
            fileHandler.write(buffer)
        fileHandler.close()
        return tempFile
    
    def addTorrent(self, feed):
        self.history("Processing: " + feed['title'])
        if not feed['torrentLink'].endswith(".torrent"):
            self.history("Downloading torrent file...")
            torrentURL = self.downloadTorrent(feed['torrentLink'])
            
        count = 0
        while True:
            self.history("Sending torrent file...")
            command = "transmission-remote " + self.accountInfo['host'] + ":" + self.accountInfo['port'] + " -n " + self.accountInfo['user'] + ":" + self.accountInfo['password'] + " -a " + feed['torrentLink']
            command = shlex.split(command)
            run = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = run.communicate()
            if "success" in result[0]:
                self.history("Torrent added!")
                return True
            elif "Error" in result[1]:
                self.history("Torrent failed to add.")
                return False
            else:
                self.history("Unknown response: ")
                self.history(str(result))
                return False
            count += 1
            if count == 2:
                return False
        
    def printFeed(self, feed):
        for key in feed.keys():
            self.history(key + " : " + feed[key])
    
    def titleFilter(self, title):
        ## Add space buffers for regex searching
        title = ' ' + title + ' '
    
        ## User regex to remove the season and episode info from the file title.
        episodeRegExs = [ "([\ \.\_\-]s(\d{1,3})e(\d{1,3})[\ \.\_\-])",
                        "([\ \.\_\-]s(\d{1,3})[\ \.\_\-]e(\d{1,3})[\ \.\_\-])",
                        "([\ \.\_\-]s(\d{1,3})e(\d{1,3})v\d[\ \.\_\-])",
                        "([\ \.\_\-](\d{3})[\ \.\_\-])",
                        "([\ \.\_\-](\d{3})v\d[\ \.\_\-])",
                        "([\ \.\_\-](\d{1,3})x(\d{1,3})[\ \.\_\-])",
                        "([\ \.\_\-]s(\d{1,3})[\.\ \_]-[\.\ \_](\d{1,3})[\ \.\_\-])",
                        "([\ \.\_\-]-[\.\ \_](\d{1,3})[\ \.\_\-])",
                        "([\ \.\_\-]-[\.\ \_](\d{1,3})v\d[\ \.\_\-])",
                        "([\ \.\_\-]ep[\.\ \_](\d{1,3})[\ \.\_\-])",
                        "([\ \.\_\-]ep[\.\ \_](\d{1,3})v\d[\ \.\_\-])",
                        "([\ \.\_\-]e(\d{1,3})[\ \.\_\-])",
                        "([\ \.\_\-]ova[\ \.\_\-](\d{1,3})[\ \.\_\-])",
                        "([\ \.\_\-]ova[\ \.\_\-](\d{1,3})v\d[\ \.\_\-])",
                        "([\ \.\_\-]season[\ \.\_\-](\d{1,3})[\ \.\_\-]{1,3}episode[\ \.\_\-](\d{1,3}))",
                        "([\ \.\_\-]episode[\ \.\_\-](\d{1,3})[\ \.\_\-])",
                        "([\ \.\_\-]episode[\ \.\_\-](\d{1,3})v\d[\ \.\_\-])",
                        "([\ \.\_\-]episode[\ \.\_\-](\d{1,3})[\ \.\_\-])",
                        "([\ \.\_\-]episode[\ \.\_\-](\d{1,3})v\d[\ \.\_\-])"
                    ]
        for expression in range(0, len(episodeRegExs)):
            result = re.search(episodeRegExs[expression], title)
            if result:
                title = title.replace(result.group(0), ' SeEp ')
                break
    
        if "ova" in title.lower():
            title = title.lower().replace('ova', '').replace(' seep ', ' SeEp ')
    
        # Filter out alternative space marks
        altSpace = [ '.', '_']
        for alt in altSpace:
            title = title.replace(alt, ' ')
    
        title = ' '.join(title.split())
        
        ## Remove uploader name from beginning
        if title[0] == '(':
            title = title[title.find(')')+1:]
            
        if title[0] == '[':
            title  = title[title.find(']')+1:]
            
        title = title.replace('(', "").replace(')', "")
    
        # Use common descprtion terms to find end of tvShow title
        commonTerms = [
                "HDTV",
                "720p",
                "720",
                "1080p",
                "x264",
                "TS",
                "XviD",
                "DVDRip",
                "BrRip",
                "BluRay",
                "H264",
                "AAC",
                "HQ",
                "subs",
                "REPACK",
                "HDRip",
                "1280x720",
                "dvd",
                "episode",
                "ep",
                "dvdscr" ]
        stop = len(title)
        for term in commonTerms:
            if ' ' + term.lower() + ' ' in ' ' + title + ' ':
                place = title.find(term.lower())
                if place < stop:
                    stop = place
        title = title[:stop]
    
        if 'SeEp' in title:
            title = title[:title.find('SeEp')]
                
        ## Handle odd leet speak, by capturing full words and replaceing as needed
        result = re.findall("([\s]\d*[\s])", title)
        if result:
            place = title.find(result[0])
            tempTitle = title.replace(result[0], '')
        else:
            tempTitle = title
        
        tempTitle = tempTitle.replace('0', 'o')
        tempTitle = tempTitle.replace('3', 'e')
        tempTitle = tempTitle.replace('4', 'a')
        tempTitle = tempTitle.replace('5', 's')
        
        if result:
            tempTitle = tempTitle[:place] + result[0] + tempTitle[place:]
        
        title = tempTitle
        
        ## Remove excess puncuation
        punctuation = string.punctuation.replace('(','').replace(')','')
        for char in range(0,len(punctuation)):
            if punctuation[char] in title:
                title = title.replace(punctuation[char], "")
        
        if title[0] == ' ':
            title = title[1:]
        if title[-1] == ' ':
            title = title[:-1]
                
        return title
    
    def getFeed(self, URL):
        result = self.getOnlineContent(URL)
        if not result:
            return []
        result = result.replace('\n', '')
        
        entries = re.findall("<item>([\s\w\W]*?)</item>", result)
        
        feeds = []
        for entry in entries:
            torrentLink = False
            temp = {}
            elements = re.findall("<(?P<tagName>[\s\w\W]*?)>([\s\w\W]*?)</(?P=tagName)>", entry)
            if "<enclosure url=" in entry:
                torrentLink = re.search("<enclosure url=\"(.*?)\" length=\"\d*?\" type=\".*?\" />", entry)
                torrentLink = torrentLink.group(1)
                temp['torrentLink'] = torrentLink
            
            for element in elements:
                temp[element[0]] = element[1]
                
            if 'pubDate' in temp.keys():
                ## Mon, 11 Jan 2016 20:35:45 +0000 
                time = re.search(".*?,\ (\d*?)\ (.*?)\ (\d{4})\ (\d*?):(\d*?):(\d*?)\ \+\d*?", temp['pubDate'])
                months = [ "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" ]
                month = months.index(time.group(2))
                if month >= 0:
                    month += 1
                    temp['binaryDate'] = datetime.datetime(int(time.group(3)), month, int(time.group(1)), int(time.group(4)), int(time.group(5)), int(time.group(6)))
                
            if 'title' in temp.keys():
                temp['origTitle'] = temp['title'].replace("<![CDATA[", '').replace("]]>", '')
                temp['title'] = self.titleFilter(temp['origTitle'])
                
            for key in temp.keys():
                if type(temp[key]) == str:
                    if temp[key].startswith('http'):
                        temp[key] = temp[key].replace("&#38;", '&')
                    if 'download' in temp[key].lower() and not torrentLink:
                        temp['torrentLink'] = temp[key]
                    
            SeEp = self.getSeasonEpisodeInfo(temp['origTitle'])
            if SeEp:
                temp['season'] = SeEp[0]
                temp['episode'] = SeEp[1]
                temp['fullEpisodeNumber'] = self.calculateFullEpisodeCount(temp)
            else:
                temp['season'] = -1
                temp['episode'] = -1
                temp['fullEpisodeNumber'] = -1
                
            
                
            if 'description' in temp.keys():
                temp['description'] = temp['description'].replace("<![CDATA[", '').replace("]]>", '')
                temp['description'] = temp['description'].replace("<br />", ' ')
                htmlTags = re.findall("(<.*?>)", temp['description'])
                for tag in htmlTags:
                    temp['description'] = temp['description'].replace(tag, '')
                temp['description'] = temp['description'].strip()
                if temp['description'].endswith('...'):
                    if '<' in temp['description']:
                        temp['description'] = temp['description'][:temp['description'].rfind('<')]
                temp['description'] = temp['description'].strip()
                temp['description'] = ' '.join(temp['description'].split(' '))
            
            feeds.append(temp)
        
        return feeds
            
    def getAllFeeds(self):
        for index in xrange(len(self.linkTable)):
            self.linkTable[index]['feeds'] = self.getFeed(self.linkTable[index]['url'])
                
    def checkForDownloads(self):
        self.history("Checking for downloads...")
        for entry in range(len(self.linkTable)-1, -1, -1):
            for feed in self.linkTable[entry]['feeds']:
                #print feed['title'] + ' ' + str(feed['season']) + ' ' + str(feed['episode'])
                #print self.linkTable[entry]['title'] + ' ' + str(self.linkTable[entry]['season']) + ' ' + str(self.linkTable[entry]['episode'])
                if (self.linkTable[entry]['season'] == feed['season'] and self.linkTable[entry]['episode'] == feed['episode']) or self.linkTable[entry]['fullEpisodeNumber'] == feed['fullEpisodeNumber']:
                    self.history("Found a match!")
                    self.history(feed['origTitle'] + ' -> ' + self.linkTable[entry]['SeEp'])
                    if 'torrentLink' in feed.keys():
                        added = self.addTorrent(feed)
                        if added:
                            self.linkTable.pop(entry)
                            break
                    else:
                        self.history("Error: " + feed['origTitle'] + " should be downloaded but does not contain a download link!")
                        self.history("Address: " + feed['link'])
        self.history("Done.")
    
    def getSeasonEpisodeInfo(self, name):
        episodeRegExs = [ "([\ \.\_\-]s(\d{1,3})e(\d{1,3})[\ \.\_\-])",
                            "([\ \.\_\-]s(\d{1,3})[\ \.\_\-]e(\d{1,3})[\ \.\_\-])",
                            "([\ \.\_\-]s(\d{1,3})e(\d{1,3})v\d[\ \.\_\-])",
                            "([\ \.\_\-](\d{3})[\ \.\_\-])",
                            "([\ \.\_\-](\d{3})v\d[\ \.\_\-])",
                            "([\ \.\_\-](\d{1,3})x(\d{1,3})[\ \.\_\-])",
                            "([\ \.\_\-]s(\d{1,3})[\.\ \_]-[\.\ \_](\d{1,3})[\ \.\_\-])",
                            "([\ \.\_\-]-[\.\ \_](\d{1,3})[\ \.\_\-])",
                            "([\ \.\_\-]-[\.\ \_](\d{1,3})v\d[\ \.\_\-])",
                            "([\ \.\_\-]ep[\.\ \_](\d{1,3})[\ \.\_\-])",
                            "([\ \.\_\-]ep[\.\ \_](\d{1,3})v\d[\ \.\_\-])",
                            "([\ \.\_\-]e(\d{1,3})[\ \.\_\-])",
                            "([\ \.\_\-]ova[\ \.\_\-](\d{1,3})[\ \.\_\-])",
                            "([\ \.\_\-]ova[\ \.\_\-](\d{1,3})v\d[\ \.\_\-])",
                            "([\ \.\_\-]season[\ \.\_\-](\d{1,3})[\ \.\_\-]{1,3}episode[\ \.\_\-](\d{1,3}))",
                            "([\ \.\_\-]episode[\ \.\_\-](\d{1,3})[\ \.\_\-])",
                            "([\ \.\_\-]episode[\ \.\_\-](\d{1,3})v\d[\ \.\_\-])",
                            "([\ \.\_\-]episode[\ \.\_\-](\d{1,3})[\ \.\_\-])",
                            "([\ \.\_\-]episode[\ \.\_\-](\d{1,3})v\d[\ \.\_\-])"
                        ]
        showNumbers = []
        for expression in range(0, len(episodeRegExs)):
            result = re.search(episodeRegExs[expression], ' ' + name.lower() + ' ')
            if result:
                for item in result.groups()[1:]:
                    if item.isdigit():
                        showNumbers.append(int(item))
                    else:
                        self.history("Error: regex groupings '()' should only be digits.")
                        error = True
                break
        if len(showNumbers) == 0:
            result = re.search("((\d\d)(\d\d))" , name.lower() )
            if result:
                for item in result.groups()[1:]:
                    if item.isdigit():
                        showNumbers.append(int(item))
                    else:
                        self.history("Error: regex groupings '()' should only be digits.")
                        error = True
        if len(showNumbers) == 0:
            return False
        elif len(showNumbers) == 1:
            if showNumbers[0] > 100:
                return [ showNumbers[0]/100, showNumbers[0]%100 ]
            else:
                return [ 1, showNumbers[0] ]
        elif len(showNumbers) == 2:
            return showNumbers
        else:
            return False
                        
    def readDatabase(self, databaseFile):
        rssLinks = []
        
        database = open(databaseFile, "r")
        if database:
            sites = database.read().split('\n\n')
            for site in sites:
                lines = site.split('\n')
                info = {}
                info['link'] = lines[0]
                info['shows'] = []
                for line in lines[1:]:
                    info['shows'].append(line.lower())
                rssLinks.append(info)
            database.close()
        return rssLinks
        
    def updateLinkTable(self, start):
        if self.databaseInfo['timeStamp'] != os.stat(self.databaseInfo['file']).st_mtime:
            self.history("Database has changed, updating shows...")
            rssLinks = self.readDatabase(self.databaseInfo['file'])
            shows = self.getCalendarInfo(start)
            self.updateLinkTableShows(shows, rssLinks)
            self.databaseInfo['timeStamp'] = os.stat(self.databaseInfo['file']).st_mtime
            self.history("Done.")
        self.getAllFeeds()
        
    def stop():
        self.stop = True
                        
    def __init__(self, service = False, fullLink = False):
        self.service = service
        start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self.history(str(start))
        
        if not self.service and not fullLink:
            back = raw_input("How many days would you like to go back? ")
            if back.isdigit():
                back = datetime.timedelta(days=int(back))
                start = start - back
                self.history(str(start))
        else:
            self.history("Running...")
        
        self.accountInfo = {
            "host": "127.0.0.1",
            "port": "9000",
            "user": "God",
            "password": "jay71191"
            }
        
        if fullLink:
            table = self.getFeed(fullLink)
            for feed in table:
                self.addTorrent(feed)
            return 0
            
        
        self.databaseInfo = {
                'file': "sites.txt",
                'timeStamp': False
                }
        
        self.history("Initial load...")
        self.linkTable = []
        self.updateLinkTable(start)
        self.checkForDownloads()
        self.history("Initial load complete.")
        last = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
        shift = datetime.timedelta(hours=3)
        self.history("Sleeping till next update check...")
        while True:
            now = datetime.datetime.now()
            if now.hour == 0 and now.minute == 0:
                self.history("Midnight update!")
                self.databaseInfo['timeStamp'] = False
                self.updateLinkTable(now.replace(hour=0, minute=0, second=0, microsecond=0))
                self.checkForDownloads()
                last = now.replace(minute=0, second=0, microsecond=0)
                sleep(65)
            elif now.minute == 0:
                self.history("Checking if three hours has past...")
                if now - shift >= last:
                    self.history("Updateing feeds...")
                    self.updateLinkTable(now.replace(hour=0, minute=0, second=0, microsecond=0))
                    self.checkForDownloads()
                    last = now.replace(minute=0, second=0, microsecond=0)
                    self.history("Sleeping...")
            elif self.stop:
                break

if __name__ == "__main__":
    service = False
    if len(sys.argv) > 1:
        if sys.argv[1] == '-s':
            rssDownloader(service = True)
        if sys.argv[1] == '-f':
            rssDownloader(fullLink = sys.argv[2].replace('"', ''))
    else:
        rssDownloader()