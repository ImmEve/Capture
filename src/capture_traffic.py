import configparser
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
        self.url_csv_path = conf.get('parameter', 'url_csv_path')
        self.tshark_interface = conf.get('parameter', 'tshark_interface')
        self.tshark_path = conf.get('parameter', 'tshark_path')
        self.mitmdump_path = conf.get('parameter', 'mitmdump_path')
        self.time_duration = int(conf.get('parameter', 'time_duration'))
        self.check_resolution = ['720p', '720p60', '1080p', '1080p60']
        self.webdriver = Webdriver()

    # 获取视频信息
    def get_video_info(self, video_url):
        # 打开视频
        if self.webdriver.loop_get_url(video_url) == 0:
            return 0, 0
        time.sleep(10)
        # 获取视频时长
        video_duration = self.webdriver.get_video_duration(video_url)
        if video_duration == 0:
            return 0, 0
        # 获取视频时长（秒）
        duration_of_the_video = self.webdriver.get_video_duration_second(video_duration)
        # 获取视频分辨率信息
        video_resolution = self.webdriver.get_video_resolution(video_url)
        if video_resolution == 0:
            return 0, 0
        return duration_of_the_video, video_resolution

    # 检查视频信息
    def check_video_info(self, video_url, duration_of_the_video, video_resolution):
        # 检查视频时长
        if duration_of_the_video < self.time_duration:
            print(f'{video_url}: duration too short\n')
            with open(self.webdriver.errorlog, 'a') as f:
                f.write(f'{video_url}: duration too short\n')
            return 0
        # 检查分辨率
        if (set(self.check_resolution) & set(video_resolution)) == set():
            print(f'{video_url}: resolution not include\n')
            with open(self.webdriver.errorlog, 'a') as f:
                f.write(f'{video_url}: resolution not include\n')
            return 0
        return 1

    def capture_traffic(self, video_url, turn):
        print('start checking...')
        p = ProxySetting()
        # 更改端口
        p.enable = True
        p.server = '127.0.0.1:7890'
        # p.enable = False
        p.registry_write()

        duration_of_the_video, video_resolution = self.get_video_info(video_url)
        self.webdriver.driver.close()
        time.sleep(3)
        if duration_of_the_video == 0 or video_resolution == 0:
            return 0
        if self.check_video_info(video_url, duration_of_the_video, video_resolution) == 0:
            return 0

        # 更改端口
        p.enable = True
        p.server = '127.0.0.1:8080'
        p.registry_write()

        for t in range(turn):
            # 新建文件
            t_time = time.strftime('%Y_%m_%d_%H_%M')
            video_name = video_url.split('=')[-1]
            pcap_filename = f'{video_name} TLS {self.check_resolution[0]} {str(duration_of_the_video)}s {t_time}.pacp'
            responsebody_filename = f'{video_name} TLS {self.check_resolution[0]} {str(duration_of_the_video)}s {t_time}.csv'
            pcap_filepath = self.pcap_path + pcap_filename
            responsebody_filepath = self.responsebody_path + responsebody_filename

            # 开始记录网络流量
            print('start checking...')
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

    def batch_capture(self, turn):
        csv_file = open(self.url_csv_path, mode='r', encoding='utf-8')
        csv_data = csv_file.read()
        video_urls = csv_data.split('\n')

        for i in range(13, len(video_urls)):
            self.capture_traffic(video_urls[i], turn)


if __name__ == '__main__':
    capture = Capture()
    capture.capture_traffic('https://www.youtube.com/watch?v=rT3EwuunXJA', 10)
    # capture.batch_capture(1)
