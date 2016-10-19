from pupa.scrape import Scraper

from .base import LegistarScraper, LegistarAPIScraper
from collections import deque

import time
import datetime
import pytz

class LegistarEventsScraper(LegistarScraper):
    def eventPages(self, since) :

        page = self.lxmlize(self.EVENTSPAGE)

        if since is None :
            yield from self.eventSearch(page, 'All')
        else :
            for year in range(since, self.now().year + 1) :
                yield from self.eventSearch(page, str(year))

    def eventSearch(self, page, value) :
            payload = self.sessionSecrets(page)

            payload['ctl00_ContentPlaceHolder1_lstYears_ClientState'] = '{"value":"%s"}' % value

            payload['__EVENTTARGET'] = 'ctl00$ContentPlaceHolder1$lstYears'

            return self.pages(self.EVENTSPAGE, payload)

    def events(self, follow_links=True, since=None) :
        # If an event is added to the the legistar system while we
        # are scraping, it will shift the list of events down and
        # we might revisit the same event. So, we keep track of
        # the last few events we've visited in order to
        # make sure we are not revisiting
        scraped_events = deque([], maxlen=10)

        for page in self.eventPages(since) :
            events_table = page.xpath("//table[@class='rgMasterTable']")[0]
            for events, _, _ in self.parseDataTable(events_table) :
                if follow_links and type(events["Meeting Details"]) == dict :
                    detail_url = events["Meeting Details"]['url']
                    if detail_url in scraped_events :
                        continue
                    else :
                        scraped_events.append(detail_url)

                    meeting_details = self.lxmlize(detail_url)

                    agenda = self.agenda(detail_url)

                else :
                    agenda = None
                
                yield events, agenda

    def agenda(self, detail_url) :
        for page in self.pages(detail_url) :
            agenda_table = page.xpath(
                "//table[@id='ctl00_ContentPlaceHolder1_gridMain_ctl00']")[0]
            agenda = self.parseDataTable(agenda_table)
            yield from agenda

    def addDocs(self, e, events, doc_type) :
        try :
            if events[doc_type] != 'Not\xa0available' : 
                e.add_document(note= events[doc_type]['label'],
                               url = events[doc_type]['url'],
                               media_type="application/pdf")
        except ValueError :
            pass

class LegistarAPIEventScraper(LegistarAPIScraper):
    def events(self):
        events_url = self.BASE_URL + '/events/'
        
        response = self.get(events_url)

        for event in response.json():
            
            start = self.toTime(event['EventDate'])
            start_time = time.strptime(event['EventTime'], '%I:%M %p')
            event['start'] = start.replace(hour=start_time.tm_hour,
                                           minute=start_time.tm_min)
            event['status'] = confirmed_or_passed(event['start'])

            yield event

    def agenda(self, event):
        agenda_url = self.BASE_URL + '/events/{}/eventitems'.format(event['EventId'])

        response = self.get(agenda_url)

        for item in response.json():
            if item['EventItemTitle']:
                yield item

    
def confirmed_or_passed(when) :
    if datetime.datetime.utcnow().replace(tzinfo = pytz.utc) > when :
        status = 'confirmed'
    else :
        status = 'passed'
    
    return status

            
