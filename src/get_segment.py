import configparser
import csv
import json
import os
import re
import subprocess
import time
from itertools import accumulate
import requests
from bs4 import BeautifulSoup


class Reference():
    def __init__(self, Reference_Type, Reference_Size, Subsegment_Duration, Starts_with_SAP, SAP_Type):
        self.Reference_Type = Reference_Type
        self.Reference_Size = Reference_Size
        self.Subsegment_Duration = Subsegment_Duration
        self.Starts_with_SAP = Starts_with_SAP
        self.SAP_Type = SAP_Type


class Track():
    def __init__(self, Track_Time, Track_Number, Track_Position):
        self.Track_Time = Track_Time
        self.Track_Number = Track_Number
        self.Track_Position = Track_Position


class Box():
    def __init__(self, filetype, start, end, videopath):
        self.filetype = filetype
        self.start = start
        self.end = end
        if self.filetype == 'mp4':
            self.get_metedata_mp4(videopath)
        elif self.filetype == 'webm':
            self.get_metedata_webm(videopath)
        else:
            raise ValueError('Filetype Wrong')

    def get_metedata_mp4(self, videopath):
        with open(videopath, 'rb') as f:
            header_data = f.read(10000)
        sidx = header_data[self.start:self.end + 1]

        self.Box_Siz = int.from_bytes(sidx[:4], byteorder='big')
        sidx = sidx[4:]
        self.Box_Type = int.from_bytes(sidx[:4], byteorder='big')
        sidx = sidx[4:]
        self.Version = int.from_bytes(sidx[:1], byteorder='big')
        sidx = sidx[1:]
        self.Flags = int.from_bytes(sidx[:3], byteorder='big')
        sidx = sidx[3:]
        self.Reference_ID = int.from_bytes(sidx[:4], byteorder='big')
        sidx = sidx[4:]
        self.Timescale = int.from_bytes(sidx[:4], byteorder='big')
        sidx = sidx[4:]
        if self.Version == 0:
            self.Earliest_Presentation_Time = int.from_bytes(sidx[:4], byteorder='big')
            sidx = sidx[4:]
            self.First_Offset = int.from_bytes(sidx[:4], byteorder='big')
            sidx = sidx[4:]
        elif self.Version == 1:
            self.Earliest_Presentation_Time = int.from_bytes(sidx[:8], byteorder='big')
            sidx = sidx[8:]
            self.First_Offset = int.from_bytes(sidx[:8], byteorder='big')
            sidx = sidx[8:]
        else:
            raise Exception('Version Inexistence')
        self.Reserved = int.from_bytes(sidx[:2], byteorder='big')
        sidx = sidx[2:]
        self.Reference_Count = int.from_bytes(sidx[:2], byteorder='big')
        sidx = sidx[2:]

        self.reference = []
        self.reference_list = []
        self.duration_list = []
        while len(sidx) != 0:
            Reference_Type = int.from_bytes(sidx[:1], byteorder='big')
            sidx = sidx[1:]
            Reference_Size = int.from_bytes(sidx[:3], byteorder='big')
            sidx = sidx[3:]
            Subsegment_Duration = int.from_bytes(sidx[:4], byteorder='big')
            sidx = sidx[4:]
            Starts_with_SAP = int.from_bytes(sidx[:1], byteorder='big')
            sidx = sidx[1:]
            SAP_Type = int.from_bytes(sidx[:3], byteorder='big')
            sidx = sidx[3:]

            ref = Reference(Reference_Type, Reference_Size, Subsegment_Duration, Starts_with_SAP, SAP_Type)
            self.reference.append(ref)
            self.reference_list.append(Reference_Size)
            self.duration_list.append(Subsegment_Duration)

    def get_metedata_webm(self, videopath):
        with open(videopath, 'rb') as f:
            header_data = f.read(10000)
        cues = header_data[self.start:self.end + 1]

        self.Cues_Header = int.from_bytes(cues[:6], byteorder='big')
        cues = cues[6:]

        self.track = []
        self.track_list = []
        self.timeline = []
        while len(cues) != 0:
            Track_Time_Flag = int.from_bytes(cues[3:4], byteorder='big')
            cues = cues[4:]
            Track_Time_Length = Track_Time_Flag - 0x80
            Track_Time = int.from_bytes(cues[:Track_Time_Length], byteorder='big')
            cues = cues[Track_Time_Length:]
            Track_Number_Flag = int.from_bytes(cues[3:4], byteorder='big')
            cues = cues[4:]
            Track_Number_Length = Track_Number_Flag - 0x80
            Track_Number = int.from_bytes(cues[:Track_Number_Length], byteorder='big')
            cues = cues[Track_Number_Length:]
            Track_Position_Flag = int.from_bytes(cues[1:2], byteorder='big')
            cues = cues[2:]
            Track_Position_Length = Track_Position_Flag - 0x80
            Track_Position = int.from_bytes(cues[:Track_Position_Length], byteorder='big')
            cues = cues[Track_Position_Length:]

            tra = Track(Track_Time, Track_Number, Track_Position)
            self.track.append(tra)
            if len(self.track) > 1:
                self.track_list.append(self.track[-1].Track_Position - self.track[-2].Track_Position)
            self.timeline.append(Track_Time)


class Video():
    def __init__(self, url):
        conf = configparser.ConfigParser()
        conf.read('config.conf', encoding='UTF-8')
        self.datapath = conf.get('get_segment', 'datapath')
        os.makedirs(self.datapath, exist_ok=True)
        os.makedirs(f'{self.datapath}websource', exist_ok=True)
        os.makedirs(f'{self.datapath}videoheader', exist_ok=True)
        self.fingerpath = conf.get('get_segment', 'fingerpath')
        self.url = url
        self.video_name = self.url.split('=')[1]
        self.video_mp4_itag = [136, 398]
        self.audio_mp4_itag = []
        self.video_webm_itag = [247]
        self.audio_webm_itag = [251]

    def get_websource(self):
        response = requests.get(self.url)
        if response.status_code == 200:
            with open(f'{self.datapath}websource/{self.video_name}.html', 'w', encoding='utf-8') as f:
                f.write(response.text)

    def analyse_websource(self):
        with open(f'{self.datapath}websource/{self.video_name}.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        soup = BeautifulSoup(html_content, 'html.parser')
        # 找到所有的 <script> 标签
        script_tags = soup.find_all('script')
        # 定义正则表达式来匹配 JavaScript 变量
        pattern = re.compile(r'var\s+ytInitialPlayerResponse\s*=\s*({.*?});', re.DOTALL)

        # 在每个 <script> 标签中搜索匹配的内容
        for script_tag in script_tags:
            # 获取 <script> 标签的所有内容，并将其合并为一个字符串
            script_content = ''.join(map(str, script_tag.contents))
            # 使用正则表达式匹配 JavaScript 变量
            match = pattern.search(script_content)
            if match:
                # 提取匹配的 JavaScript 变量内容
                javascript_code = match.group(1)
        data = json.loads(javascript_code)
        service_tracking_params = data.get('streamingData', {}).get('adaptiveFormats', [])

        self.itag_list = []
        self.itag_filetype = {}
        self.itag_mimetype = {}
        self.itag_vcodec = {}
        self.itag_indexrange = {}
        self.itag_contentlength = {}
        self.itag_quality = {}
        for param in service_tracking_params:
            itag = param.get('itag')
            if itag in self.itag_list:
                continue
            if itag in (self.video_mp4_itag + self.video_webm_itag + self.audio_mp4_itag + self.audio_webm_itag):
                self.itag_list.append(itag)
                self.itag_filetype[itag] = param['mimeType'].split('/')[1].split(';')[0]
                self.itag_mimetype[itag] = param['mimeType'].split('/')[0]
                self.itag_vcodec[itag] = param['mimeType'].split('\"')[1].split('.')[0]
                indexRange = param.get('indexRange')
                indexRange['start'] = int(indexRange['start'])
                indexRange['end'] = int(indexRange['end'])
                self.itag_indexrange[itag] = indexRange
                self.itag_contentlength[itag] = int(param.get('contentLength'))
                if self.itag_mimetype[itag] == 'video':
                    self.itag_quality[itag] = param.get('qualityLabel')
                elif self.itag_mimetype[itag] == 'audio':
                    self.itag_quality[itag] = param.get('audioQuality')

    def download_video(self):
        self.analyse_websource()
        os.makedirs(f'{self.datapath}videoheader/{self.video_name}', exist_ok=True)
        for itag in self.itag_list:
            videopath = f'{self.datapath}videoheader/{self.video_name}/{self.video_name}_{self.itag_mimetype[itag]}_{itag}.{self.itag_filetype[itag]}'
            while 10:
                if os.path.exists(videopath):
                    break
                command = f'yt-dlp -f {itag} {self.url} -o {videopath}'.split(' ')
                process = subprocess.Popen(command)
                time.sleep(10)
                process.kill()

    def analyse_video(self):
        self.analyse_websource()
        self.itag_box = {}
        for itag in self.itag_list:
            start, end = self.itag_indexrange[itag]['start'], self.itag_indexrange[itag]['end']
            videopath = f'{self.datapath}/videoheader/{self.video_name}/{self.video_name}_{self.itag_mimetype[itag]}_{itag}.{self.itag_filetype[itag]}'
            try:
                box = Box(self.itag_filetype[itag], start, end, videopath)
            except:
                box = None
            self.itag_box[itag] = box

            if box is not None:
                with open(self.fingerpath, 'a') as f:
                    url = 'https://www.youtube.com//watch?v=' + self.video_name
                    f.write(
                        f'{url},{str(itag)},{self.itag_mimetype[itag]}/{self.itag_filetype[itag]},{self.itag_quality[itag]},{self.itag_vcodec[itag]},{str(self.itag_contentlength[itag])},')
                    if box.filetype == 'mp4':
                        seg_list = box.reference_list
                        dura_list = [1000 * x // box.Timescale for x in box.duration_list]
                        time_list = [0] + list(accumulate(dura_list))
                    elif box.filetype == 'webm':
                        seg_list = box.track_list
                        time_list = box.timeline
                    f.write(str(len(seg_list)) + ',')
                    seg_str = ''
                    for seg in seg_list:
                        seg_str = seg_str + '/' + str(seg)
                    f.write(seg_str + ',')
                    time_str = ''
                    for tim in time_list:
                        time_str = time_str + '/' + str(tim)
                    f.write(time_str + '\n')


def batch_segment():
    conf = configparser.ConfigParser()
    conf.read('config.conf', encoding='UTF-8')
    url_list_path = conf.get('get_segment', 'url_list_path')

    with open(url_list_path, 'r') as f:
        reader = csv.reader(f)
        txt = list(reader)
    url_list = [i[0] for i in txt]

    for i in range(0, len(url_list)):
        try:
            video = Video(url_list[i])
            video.get_websource()
            video.download_video()
            video.analyse_video()
        except:
            print(f'{url_list[i]}: get segment error')
            with open('../data/fingerprint/error_log.csv', 'a') as f:
                f.write(f'{url_list[i]}: get segment error\n')


if __name__ == '__main__':
    batch_segment()
