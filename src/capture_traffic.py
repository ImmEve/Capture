import configparser
import csv
import os.path
import subprocess
import time
from winproxy import ProxySetting
from webdriver import Webdriver


class Capture():
    def __init__(self):
        conf = configparser.ConfigParser()
        conf.read('config.conf', encoding='UTF-8')
        self.pcap_path = conf.get('parameter', 'pcap_path')
        os.makedirs(self.pcap_path, exist_ok=True)
        self.responsebody_path = conf.get('parameter', 'responsebody_path')
        os.makedirs(self.responsebody_path, exist_ok=True)
        self.url_list_path = conf.get('parameter', 'url_list_path')
        self.url_class_path = conf.get('parameter', 'url_class_path')
        self.tshark_interface = conf.get('parameter', 'tshark_interface')
        self.tshark_path = conf.get('parameter', 'tshark_path')
        self.mitmdump_path = conf.get('parameter', 'mitmdump_path')
        self.time_duration = int(conf.get('parameter', 'time_duration'))
        self.check_resolution = ['720p', '720p60', '720p ', '1080p', '1080p60', '1080p ']
        self.webdriver = Webdriver()

    # 检查视频信息
    def check_video_info(self, video_url):
        # 打开视频
        if self.webdriver.loop_get_url(video_url) == 0:
            self.webdriver.driver.close()
            return 0
        time.sleep(10)
        # 获取视频时长
        video_duration = self.webdriver.get_video_duration(video_url)
        if video_duration == 0:
            self.webdriver.driver.close()
            return 0
        # 获取视频时长（秒）
        duration_of_the_video = self.webdriver.get_video_duration_second(video_duration)
        # 获取视频分辨率信息
        video_resolution = self.webdriver.get_video_resolution(video_url)
        if video_resolution == 0:
            self.webdriver.driver.close()
            return 0
        # 检查视频时长
        if duration_of_the_video < self.time_duration:
            print(f'{video_url}: duration too short\n')
            with open(self.webdriver.errorlog, 'a') as f:
                f.write(f'{video_url}: duration too short\n')
            self.webdriver.driver.close()
            return 0
        # 检查分辨率
        if (set(self.check_resolution) & set(video_resolution)) == set():
            print(f'{video_url}: resolution not include\n')
            with open(self.webdriver.errorlog, 'a') as f:
                f.write(f'{video_url}: resolution not include\n')
            self.webdriver.driver.close()
            return 0
        self.webdriver.driver.close()
        return 1

    # 采集视频流量并记录解密响应
    def capture_traffic(self, video_url, turn):
        print('start checking...')
        p = ProxySetting()
        # 更改端口
        p.enable = True
        p.server = '127.0.0.1:7890'
        # p.enable = False
        p.registry_write()

        if self.check_video_info(video_url) == 0:
            return 0

        # 更改端口
        p.enable = True
        p.server = '127.0.0.1:8080'
        p.registry_write()

        for t in range(turn):
            # 新建文件
            t_time = time.strftime('%Y_%m_%d_%H_%M')
            video_name = video_url.split('=')[-1]
            pcap_filename = f'{video_name} TLS {self.check_resolution[0]} {str(self.time_duration)}s {t_time}.pacp'
            responsebody_filename = f'{video_name} TLS {self.check_resolution[0]} {str(self.time_duration)}s {t_time}.csv'
            pcap_filepath = self.pcap_path + pcap_filename
            responsebody_filepath = self.responsebody_path + responsebody_filename

            # 开始记录网络流量
            print('start capturing...')
            tsharkOut = open(pcap_filepath, 'wb')
            tsharkCall = [self.tshark_path, '-F', 'pcap', '-i', self.tshark_interface, '-w', pcap_filepath]
            tsharkProc = subprocess.Popen(tsharkCall, stdout=tsharkOut, executable=self.tshark_path)
            mitmCall = [self.mitmdump_path, '-s', 'capture_responsebody.py', '--mode', 'upstream:http://127.0.0.1:7890']
            # mitmCall = [self.mitmdump_path, '-s', 'capture_responsebody.py']
            mitmProc = subprocess.Popen(mitmCall, executable=self.mitmdump_path)
            time.sleep(10)

            # 播放视频
            self.webdriver.loop_get_url(video_url)
            time.sleep(self.time_duration + 10)
            # 结束流量采集
            tsharkProc.kill()
            mitmProc.kill()
            try:
                os.rename(self.responsebody_path + 'log.csv', responsebody_filepath)
            except:
                print(f'{video_url}: log error\n')
                with open(self.webdriver.errorlog, 'a') as f:
                    f.write(f'{video_url}: log error\n')
            # 关闭视频
            self.webdriver.driver.close()
            time.sleep(10)

    # 批量采集
    def batch_capture(self, turn):
        csv_file = open(self.url_list_path, 'r', encoding='utf-8')
        csv_data = csv_file.read()
        video_urls = csv_data.split('\n')

        for i in range(0, len(video_urls)):
            self.capture_traffic(video_urls[i], turn)

    # 抓取url
    def clawer_url(self):
        with open(self.url_class_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            class_list = list(reader)
        urllist = []
        for class_url in range(len(class_list)):
            # 打开视频
            if self.webdriver.loop_get_url(class_list[class_url][1]) == 0:
                self.webdriver.driver.close()
                return 0
            time.sleep(10)
            urls = self.webdriver.get_urllist()
            self.webdriver.driver.close()
            urllist = urllist + urls
        urllist = list(set(urllist))
        t_time = time.strftime('%Y_%m_%d_%H_%M')
        with open(f'{self.url_class_path.split("_")[0]}_{t_time}.csv', 'w') as f:
            f.write('\n')
            for url in urllist:
                f.write(url[:44] + '\n')


if __name__ == '__main__':
    capture = Capture()
    capture.clawer_url()
    # capture.capture_traffic('https://www.youtube.com/watch?v=rT3EwuunXJA', 10)
    # capture.batch_capture(1)
