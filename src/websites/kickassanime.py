import time

import cfscrape
from bs4 import BeautifulSoup as bs

from src.config import TimeoutConfig
from src.scrape_utils.selectors import KickassAnimeSelectors, LOAD_STATUS_SELECTOR
from src.scrape_utils.servers import StreamServers
from src.stream_servers.openupload import OpenUploadScraper
from src.stream_servers.mp4upload import Mp4UploadScraper
from src.stream_servers.yourupload import YourUploadScraper
from src.utils import printing
from src.utils.timeout import call_till_true
from src.utils import sort_nicely, printd


class Scraper:
    def __init__(self, webdriver, url, server):
        self.driver = webdriver
        self.anime_url = url
        self.server = server
        self.cfscraper = cfscrape.create_scraper()

        # TODO: Find a better way to bypass CF
        # bypassing cloudflare 
        self.driver.get(self.anime_url)
        time.sleep(5)
        self.driver.get(self.anime_url)

        self.episodes_dict = {}
        self.episodes_dict = self.fetch_episode_list()
        self.server_scraper = self._get_server_scraper()

    def _get_server_scraper(self):
        scrapers = {
            StreamServers.OPENUPLOAD: OpenUploadScraper(self.driver, KickassAnimeSelectors),
            StreamServers.MP4UPLOAD: Mp4UploadScraper(self.driver, KickassAnimeSelectors),
            StreamServers.YOURUPLOAD: YourUploadScraper(self.driver, KickassAnimeSelectors)
        }
        return scrapers[self.server]
    
    def fetch_episode_list(self):
        # -> { 'Episode 1': 'https://www.kickassanime.ru/anime/gintama/episode-1', ... }
        if self.episodes_dict:
            return self.episodes_dict

        printd("fetching episode list")
        printing.fetching_list(self.anime_url)
        driver = self.driver
        
        # ep_list_container = driver.find_element_by_css_selector(KickassAnimeSelectors.EPISODE_LIST)

        # def fetch_ep_list(container):
        #     return container.find_elements_by_css_selector(KickassAnimeSelectors.EPISODE)

        # # Sometimes the episode list takes a while to load and we fetch_ep_list gets 0 episodes
        # # call_till_true will keep trying for n seconds till we get >0 episodes
        # ep_list, calls, success = call_till_true(fetch_ep_list, TimeoutConfig.FETCHING_EPISODE_LIST, ep_list_container)
        # printd(ep_list)
        # if not success:
        #     # TODO: Change error raised
        #     raise ValueError("Failed to fetch episode list")

        # printd("calls", calls)
        # print(ep_list_container.text)
        # print(len(ep_list))

        source = self.cfscraper.get(self.anime_url).content
        soup = bs(source, "lxml")
        ep_list = soup.select(KickassAnimeSelectors.EPISODE_LIST)[0].select(KickassAnimeSelectors.EPISODE)

        ep_dict = {}

        for ep in ep_list:
            if ep.text and ep.text not in ep_dict:
                ep_name = ep.text
                ep_page = ep["href"]
                ep_dict[ep_name] = ep_page

        printd(ep_dict)
        return ep_dict

    def fetch_metadata(self):
        # TODO: Fetch complete metadata
        driver = self.driver
        title = ""
        description = ""
        thumbnail = ""
        
        if driver.current_url != self.anime_url:
            driver.get(self.anime_url)
        
        img_tags = driver.find_elements_by_css_selector("img")

        for img in img_tags: 
            if img.get_attribute("itemprop") == "thumbnailUrl":
                thumbnail = img.get_attribute("src")
                # print(thumbnail)
                break
        return { "title": title, "description": description, "thumbnail": thumbnail }

    def fetch_episode(self, episode_name):
        # -> { stream_page: http://.../watch/episode-01, stream_url: http://.../file.mp4 } 

        if episode_name in self.episodes_dict:
            stream_page = self.episodes_dict[episode_name]
            
            printd("Fetching", episode_name)
            printing.fetching_episode(episode_name, stream_page)
            # stream_url = self.server_scraper.fetch_stream_url(stream_page)
            try:
                stream_url = self.server_scraper.fetch_stream_url(stream_page)
                printd("stream_url", stream_url)
            except:
                stream_url = ""
            result = { "stream_page": stream_page, "stream_url": stream_url  }

            printd(result)
            printing.fetched_episode(episode_name, stream_url, True if stream_url else False)

            return result
        
        raise ValueError("%s does not exist" % episode_name)

    def fetch_episode_number(self, episode_number):
        for episode_name in self.episodes_dict:
            if episode_number == int(episode_name.replace("Episode ", "")):
                return self.fetch_episode(episode_name)
        raise ValueError("Episode %d does not exist" % episode_number)

    def fetch_all_episodes(self, episodes_dict):
        # -> { 'Episode 1': { 'stream_page': http://.../watch/episode-01, 'stream_url': http://.../file.mp4 }  }
        episode_names = list(self.episodes_dict.keys())
        sort_nicely(episode_names)
        
        for ep_name in episode_names:
            try:
                episodes_dict[ep_name] = self.fetch_episode(ep_name)
            except ValueError:
                episodes_dict[ep_name] = ""
