import csv
import time
from lxml import etree
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait


class Clawer_url():
    def __init__(self, chrome_driver_path, chrome_user_data_path):
        self.chrome_driver_path = chrome_driver_path
        self.chrome_user_data_path = chrome_user_data_path

        self.driver = self.chrome_driver_init()

    def __del__(self):
        self.driver.close()

    # 初始化chrom driver
    def chrome_driver_init(self):
        options = webdriver.ChromeOptions()
        service = Service(self.chrome_driver_path)
        options.add_argument("--user-data-dir=" + self.chrome_user_data_path)
        options.add_argument('--disable-cache')
        options.add_argument('--disk-cache-size=0')
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_window_size(1000, 30000)
        wait = WebDriverWait(driver, 100)
        return driver

    # 持续访问URL直到成功
    def loop_get_url(self, loop_count, video_url):
        for i in range(0, loop_count):
            try:
                time.sleep(3)
                self.driver.get(video_url)
                return 1
            except:
                continue
        return 0

    # 获取视频时长
    def get_video_duration(self):
        duration_xpath = '//span[starts-with(@class,"ytp-time-duration")]/text()'
        try:
            if duration_xpath != '':
                html = self.driver.page_source.encode("utf-8", "ignore")
                parseHtml = etree.HTML(html)
                video_duration = parseHtml.xpath(duration_xpath)
        except:
            video_duration = -1
            print('get video duration error')
        return video_duration

    # 从主页面获取待爬取的视频URL
    def get_url(self, main_url):
        loop_count = 10
        self.loop_get_url(loop_count, main_url)
        time.sleep(5)
        for i in range(0, 100):
            self.driver.execute_script('window.scrollBy(0,1000)')
            time.sleep(1)

        # 从索引页批量获取视频URL
        video_urls = []
        html = self.driver.page_source.encode("utf-8", "ignore")
        parseHtml = etree.HTML(html)
        index_page_xpath = '//a[@id="thumbnail"]/@href'
        raw_video_urls = parseHtml.xpath(index_page_xpath)
        # 跳过短视频
        for url in raw_video_urls:
            if str(url).__contains__('watch'):
                video_urls.append("https://www.youtube.com/" + str(url))
        else:
            video_urls = parseHtml.xpath(index_page_xpath)

        return video_urls


if __name__ == '__main__':
    chrome_user_data_path = 'C:/Users/test/AppData/Local/Google/Chrome/User Data'
    chrome_driver_path = '../src/chromedriver.exe'
    clawer_url = Clawer_url(chrome_user_data_path, chrome_driver_path)

    with open('../data/url/url_class.csv', 'r') as f:
        reader = csv.reader(f)
        class_list = list(reader)
    urllist = []
    for i in range(len(class_list)):
        urls = clawer_url.get_url(class_list[i][1])
        urllist = urllist + urls

    urllist = list(set(urllist))
    with open('../data/url/url_list.csv', 'w') as f:
        f.write('\n')
        for url in urllist:
            f.write(url[:44] + '\n')
