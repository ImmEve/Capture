import configparser
import os.path
import subprocess
import time
from lxml import etree
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from winproxy import ProxySetting


class Capture():
    def __init__(self):
        conf = configparser.ConfigParser()
        conf.read('config.conf', encoding='UTF-8')
        self.tshark_interface = conf.get('parameter', 'tshark_interface')
        self.tshark_path = conf.get('parameter', 'tshark_path')
        self.chrome_driver_path = conf.get('parameter', 'chrome_driver_path')
        self.chrome_user_data_path = conf.get('parameter', 'chrome_user_data_path')
        self.pcap_path = conf.get('parameter', 'pcap_path')
        os.makedirs(self.pcap_path, exist_ok=True)
        self.responsebody_path = conf.get('parameter', 'responsebody_path')
        os.makedirs(self.responsebody_path, exist_ok=True)
        self.url_csv_path = conf.get('parameter', 'url_csv_path')
        self.mitmdump_path = conf.get('parameter', 'mitmdump_path')
        self.time_duration = int(conf.get('parameter', 'time_duration'))
        self.errorlog = conf.get('parameter', 'errorlog')

    def __del__(self):
        self.driver.close()

    # 初始化chrom driver
    def chrome_driver_init(self):
        options = webdriver.ChromeOptions()
        service = Service(self.chrome_driver_path)
        options.add_argument('--user-data-dir=' + self.chrome_user_data_path)
        options.add_argument('--disable-cache')
        options.add_argument('--disk-cache-size=0')
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_window_size(1000, 30000)
        wait = WebDriverWait(driver, 100)
        return driver

    # 持续访问URL直到成功
    def loop_get_url(self, loop_count, video_url):
        self.driver = self.chrome_driver_init()
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
                html = self.driver.page_source.encode('utf-8', 'ignore')
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
            html = self.driver.page_source.encode('utf-8', 'ignore')
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
        # 更改端口
        p = ProxySetting()
        p.enable = True
        p.server = '127.0.0.1:7890'
        p.registry_write()

        video_duration = -1
        loop_count = 10
        # 打开视频
        if self.loop_get_url(loop_count, video_url) == 0:
            with open(self.errorlog, 'a') as f:
                f.write(f'{video_url}: Playback Error\n')
            return
        time.sleep(10)

        # 获取视频的播放时长
        for i1 in range(0, loop_count):
            if video_duration == -1 or len(video_duration) == 0:
                video_duration = self.get_video_duration()
                time.sleep(10)
            else:
                print(f'video_duration: {video_duration[0]}')
                break

        # 确定视频实际播放时长
        duration_of_the_video = self.get_video_duration_second(video_duration)
        if duration_of_the_video > self.time_duration:
            duration_of_the_video = self.time_duration
        else:
            with open(self.errorlog, 'a') as f:
                f.write(f'{video_url}: Duration Error\n')
            self.driver.close()
            time.sleep(10)
            return

        # 检查视频是否包含指定分辨率
        check_resolution = ['720p']
        video_resolution = self.get_video_resolution()
        print(f'video_resolution: {video_resolution}')
        if not all(resolution in video_resolution for resolution in check_resolution):
            with open(self.errorlog, 'a') as f:
                f.write(f'{video_url}: Resolution Error\n')
            self.driver.close()
            time.sleep(10)
            return

        # 关闭视频
        self.driver.close()
        time.sleep(10)
        # 更改端口
        p.enable = True
        p.server = '127.0.0.1:8080'
        p.registry_write()

        for t in range(turn):
            # 新建文件
            t_time = time.strftime('%Y_%m_%d_%H_%M')
            video_name = video_url.split('=')[-1]
            pcap_filename = f'{video_name} TLS {check_resolution[0]} {str(duration_of_the_video)}s {t_time}.pacp'
            responsebody_filename = f'{video_name} TLS {check_resolution[0]} {str(duration_of_the_video)}s {t_time}.csv'
            pcap_filepath = self.pcap_path + pcap_filename
            responsebody_filepath = self.responsebody_path + responsebody_filename

            # 开始记录网络流量
            tsharkOut = open(pcap_filepath, 'wb')
            tsharkCall = [self.tshark_path, '-F', 'pcap', '-i', self.tshark_interface, '-w', pcap_filepath]
            tsharkProc = subprocess.Popen(tsharkCall, stdout=tsharkOut, executable=self.tshark_path)
            mitmCall = [self.mitmdump_path, '-s', 'capture_responsebody.py', '--mode', 'upstream:http://127.0.0.1:7890']
            mitmProc = subprocess.Popen(mitmCall, executable=self.mitmdump_path)
            time.sleep(10)

            # 播放视频
            self.loop_get_url(loop_count, video_url)
            time.sleep(duration_of_the_video + 10)
            # 结束流量采集
            tsharkProc.kill()
            mitmProc.kill()
            os.rename(self.responsebody_path + 'log.csv', responsebody_filepath)
            # 关闭视频
            self.driver.close()
            time.sleep(10)

    def batch_capture(self, turn):
        csv_file = open(self.url_csv_path, mode='r', encoding='utf-8')
        csv_data = csv_file.read()
        video_urls = csv_data.split('\n')

        for i in range(0, len(video_urls)):
            self.capture_traffic(video_urls[i], turn)


if __name__ == '__main__':
    capture = Capture()
    # capture.capture_traffic('https://www.youtube.com/watch?v=GiZZ_DRE2To', 10)
    capture.batch_capture(1)
