import os.path
import subprocess
import time
from lxml import etree
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


class Capture():
    def __init__(self, tshark_interface, tshark_path, chrome_driver_path, chrome_user_data_path, pcap_path,
                 url_csv_path=''):
        self.tshark_interface = tshark_interface
        self.tshark_path = tshark_path
        self.chrome_driver_path = chrome_driver_path
        self.chrome_user_data_path = chrome_user_data_path
        self.pcap_path = pcap_path
        self.url_csv_path = url_csv_path
        self.time_duration = 6 * 60

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

    # 确定视频实际播放时长
    def get_video_duration_second(self, video_duration):
        video_duration_s = -1
        if len(video_duration) > 0 and video_duration != -1:
            time_data = str(video_duration[0]).split(':')
            if len(time_data) == 2:
                video_duration_s = int(time_data[0]) * 60 + int(time_data[1])
            else:
                video_duration_s = int(time_data[0]) * 3600 + int(time_data[1]) * 60 + int(time_data[2])
        duration_of_the_video = video_duration_s
        return duration_of_the_video

    # 获取视频分辨率信息
    def get_video_resolution(self):
        video_resolution = []
        try:
            # 点击设置
            self.driver.find_element(By.XPATH, '//*[@class="ytp-button ytp-settings-button"]').click()
            # 点击画质
            self.driver.find_element(By.XPATH,
                                     '//*[@class="ytp-popup ytp-settings-menu"]//*[@class="ytp-menu-label-secondary"]').click()
            time.sleep(1)
            # 获取分辨率信息
            html = self.driver.page_source.encode("utf-8", "ignore")
            parseHtml = etree.HTML(html)
            video_resolution = parseHtml.xpath(
                '//*[@class="ytp-popup ytp-settings-menu"]//*[@class="ytp-menuitem-label"]/div/span/text()')
            # 复原
            self.driver.find_element(By.XPATH, '//*[@class="ytp-button ytp-settings-button"]').click()
        except:
            print('get resolution error')

        return video_resolution

    # 单个播放视频URL，并记录pcap
    def capture_traffic(self, video_url, turn):
        print('start capturing...')
        # 创建目录
        os.makedirs(self.pcap_path, exist_ok=True)

        video_duration = -1
        loop_count = 10

        # 打开视频
        if self.loop_get_url(loop_count, video_url) == 0:
            print('get URL error')
            return

        time.sleep(10)

        # 获取视频的播放时长
        for i1 in range(0, loop_count):
            if video_duration == -1 or len(video_duration) == 0:
                video_duration = self.get_video_duration()
                time.sleep(10)
            else:
                print(video_duration[0])
                break

        # 确定视频实际播放时长
        duration_of_the_video = self.get_video_duration_second(video_duration)
        if duration_of_the_video > self.time_duration:
            duration_of_the_video = self.time_duration
        else:
            return

        # 检查视频是否包含指定分辨率
        check_resolution = ['480', '720', '1080']
        video_resolution = self.get_video_resolution()
        if not all(resolution in video_resolution for resolution in check_resolution):
            return

        for t in range(turn):
            # 新建文件名
            t_time = time.strftime("%Y_%m_%d_%H_%M")
            video_name = video_url.split('=')[-1]
            pcap_filename = f'{video_name} auto {str(duration_of_the_video)} {t_time}.pacp'
            pcap_filepath = self.pcap_path + pcap_filename

            self.driver.close()
            time.sleep(10)

            # 开始记录网络流量
            tsharkOut = open(pcap_filepath, "wb")
            tsharkCall = [self.tshark_path, "-F", "pcap", "-i", self.tshark_interface, "-w", pcap_filepath]
            tsharkProc = subprocess.Popen(tsharkCall, stdout=tsharkOut, executable=self.tshark_path)

            time.sleep(10)
            self.driver = self.chrome_driver_init()
            self.loop_get_url(loop_count, video_url)
            # 等待视频播放
            time.sleep(duration_of_the_video)
            # 结束流量采集
            time.sleep(10)
            tsharkProc.kill()
            time.sleep(10)

    def batch_capture(self, turn):
        csv_file = open(self.url_csv_path, mode='r', encoding='utf-8')
        csv_data = csv_file.read()
        video_urls = csv_data.split('\n')

        for i in range(0, len(video_urls)):
            self.capture_traffic(video_urls[i], turn)


if __name__ == '__main__':
    tshark_interface = 'localnet'
    tshark_path = 'E:/Wireshark/tshark.exe'
    chrome_user_data_path = 'C:/Users/test/AppData/Local/Google/Chrome/User Data'
    chrome_driver_path = '../src/chromedriver.exe'
    pcap_path = '../data/traffic/quic/pcap/'
    url_csv_path = '../data/url/url_list.csv'
    os.makedirs(pcap_path, exist_ok=True)
    capture = Capture(tshark_interface, tshark_path, chrome_driver_path, chrome_user_data_path, pcap_path, url_csv_path)

    # capture.capture_traffic('https://www.youtube.com/watch?v=GiZZ_DRE2To_', 10)

    capture.batch_capture(1)
