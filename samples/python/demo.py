# -*- coding: utf-8 -*-
import datetime
import json
import logging
import random
import re
import time

import requests
from bs4 import *
from pixivpy3 import *

import wechat
from wechat import WeChatManager, MessageType

wechat_manager = WeChatManager(libs_path='../../libs')

# 默认的warning级别，只输出warning以上的
# 使用basicConfig()来指定日志级别和相关信息

logging_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)-9s - %(filename)-8s : %(lineno)s line - %(message)s", "%Y-%m-%d %H:%M:%S")
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler("D:\\DEV\\wechat_pc_api\\info.log", encoding="UTF-8", mode="a")
handler.setFormatter(logging_formatter)
logger.handlers.append(handler)

__PIXIV_TOKEN = {
    "access": "9FlrO5LV6N5Ngvcon9M8aNBpLYB7gOtZ0E33tjkA2ig",
    "refresh": "96nQwKu2FeDxqpbGuyYGM_9FDhuBTMdowgrJl6Z2n2A"
}
__TIAN_KEY = "8440a83c08e31246c82659cc76507748"
__IPTK_API_KEY = "12854ea84b7b7fb27c8db41001052466"
__IPTK_API_SECRET = "ttmgc5oxmv70"
__REQUESTS_KWARGS = {
    'proxies': {
        'http': 'http://127.0.0.1:7890',
        'https': 'http://127.0.0.1:7890',
    }
}
__MASTER_WECHAT_ID = "wxid_bkst1jkc7ebc22"

# login pixiv
api = AppPixivAPI(**__REQUESTS_KWARGS)
api.auth(refresh_token=__PIXIV_TOKEN["refresh"])

# 全局变量
pixiv_api_error_count = 0
session = requests.Session()


class SetuRepository(object):

    def __init__(self) -> None:
        self.pixiv_imginfo_bydate = {}
        self.pixiv_img_nowindex = 0
        self.pixiv_offset = 0
        self.pixiv_uplimit = -1
        super().__init__()

    def get_setu_by_index(self, pixiv_img_nowindex) -> dict:
        if self.pixiv_imginfo_bydate.get(datetime.date.today()) is None:
            self.pixiv_offset = 0
            self.pixiv_uplimit = -1
            self.pixiv_imginfo_bydate[datetime.date.today()] = api.illust_ranking('day_r18')["illusts"]

        if pixiv_img_nowindex == self.pixiv_uplimit:
            pixiv_img_nowindex = 0

        if pixiv_img_nowindex >= len(self.pixiv_imginfo_bydate[datetime.date.today()]):
            self.pixiv_offset += 30
            if self.pixiv_offset >= 300:
                self.pixiv_offset = 0
                self.pixiv_img_nowindex = 0
                self.pixiv_uplimit = len(self.pixiv_imginfo_bydate[datetime.date.today()])
                raise Exception("若曦找不到更多图片啦")

            self.pixiv_imginfo_bydate[datetime.date.today()] += \
                api.illust_ranking('day_r18',
                                   offset=self.pixiv_offset)["illusts"]
            return self.get_setu_by_index(pixiv_img_nowindex)

        return self.pixiv_imginfo_bydate[datetime.date.today()][pixiv_img_nowindex]

    def get_next_setu(self) -> dict:
        result = self.get_setu_by_index(pixiv_img_nowindex=self.pixiv_img_nowindex)
        self.pixiv_img_nowindex += 1
        return result

    def get_all_setu(self) -> dict:
        return self.pixiv_imginfo_bydate

    def download_setu(self, setu, index) -> str:
        fname = "setu-" + datetime.date.today().__str__() + "-" + index.__str__()
        api.download(setu.image_urls.medium, path="../../setu/",
                     fname="setu-" + datetime.date.today().__str__() + "-" + index.__str__())
        return fname

    def download_next_setu(self) -> str:
        fname = "setu-" + datetime.date.today().__str__() + "-" + (self.pixiv_img_nowindex + 1).__str__()
        api.download(self.get_next_setu().image_urls.medium, path="../../setu/",
                     fname="setu-" + datetime.date.today().__str__() + "-" + self.pixiv_img_nowindex.__str__())
        return fname

    def get_setu_by_keyword(self, keyword):
        return api.search_illust(keyword)["illusts"][0]

    def download_setu_by_keyword(self, keyword):
        uuid_uuid = random.randint(0, 999999999999999999999)
        fname = "setu-" + datetime.date.today().__str__() + "-" + uuid_uuid.__str__()
        api.download(self.get_setu_by_keyword(keyword).image_urls.medium, path="../../setu/",
                     fname="setu-" + datetime.date.today().__str__() + "-" + uuid_uuid.__str__())
        return fname


setuRepository = SetuRepository()


# 这里测试函数回调
@wechat.CONNECT_CALLBACK(in_class=False)
def on_connect(client_id):
    logging.info('[on_connect] client_id: {0}'.format(client_id))


@wechat.RECV_CALLBACK(in_class=False)
def on_recv(client_id, message_type, message_data: dict):
    try:
        raw_msg = ""
        if type(message_data) == dict and message_data.get("raw_msg") is not None:
            raw_msg = message_data.pop("raw_msg")
        logging.info('[on_recv] client_id: {0}, message_type: {1}, message:{2}'.format(client_id,
                                                                                       message_type,
                                                                                       json.dumps(message_data,
                                                                                                  ensure_ascii=False)))
        if message_type == MessageType.MT_RECV_TEXT_MSG:
            msg = message_data.get("msg")
            room_wxid = message_data.get("room_wxid")
            from_wxid = message_data.get("from_wxid")

            if room_wxid == "" and from_wxid != "wxid_9395uubonvp622":
                __message_in_user(client_id, from_wxid, msg)
            elif "wxid_9395uubonvp622" in message_data["at_user_list"] or msg.find("@若曦") != -1:
                msg = __remove_at_from_msg(msg)
                __message_in_room(client_id, msg, room_wxid)

        if message_type == MessageType.MT_RECV_FRIEND_MSG:
            soup = BeautifulSoup(raw_msg, "html.parser")
            __report_to_master(client_id,
                               f"主人主人，有个叫 {soup.msg['fromnickname']} 的人加我啦！他的好友请求是 {soup.msg['content']} 快去通过一下吧~")
    except Exception as e:
        logging.exception(e)
        __report_to_master(client_id, f"主人主人，我出错啦！\n异常信息：" + e.__str__())


@wechat.CLOSE_CALLBACK(in_class=False)
def on_close(client_id):
    logging.info('[on_close] client_id: {0}'.format(client_id))


def __message_in_user(client_id, from_wxid, msg):
    if __is_setu(msg):
        match = re.search("\\*[0-9]+", msg)
        if match is not None:
            for _ in range(int(match.group()[1:])):
                time.sleep(0.1)
                __send_setu(client_id, from_wxid)
        else:
            __send_setu(client_id, from_wxid)
    elif __is_soutu(msg):
        keyword = msg.replace("搜图：", "")
        __send_soutu(client_id, from_wxid, keyword)

    else:
        response = __send_message_itpk(msg.strip())
        time.sleep(len(response) * 0.2)
        wechat_manager.send_text(client_id, from_wxid, response)


def __message_in_room(client_id, msg, room_wxid):
    if __is_setu(msg):
        match = re.search("\\*[0-9]+", msg)
        if match is not None:
            for _ in range(int(match.group()[1:])):
                time.sleep(0.1)
                __send_setu(client_id, room_wxid)
        else:
            __send_setu(client_id, room_wxid)
    elif __is_soutu(msg):
        keyword = msg.replace("搜图：", "")
        __send_soutu(client_id, room_wxid, keyword)
    else:
        response = __send_message_itpk(msg)
        time.sleep(len(response) * 0.2)
        wechat_manager.send_text(client_id, room_wxid, response)


def __send_soutu(client_id, from_wxid, keyword):
    global pixiv_api_error_count
    try:
        logging.info(f"开始搜索...keyword={keyword}")
        setu_filename = setuRepository.download_setu_by_keyword(keyword)
        wechat_manager.send_image(client_id, from_wxid, "D:\\DEV\\wechat_pc_api\\setu\\" + setu_filename)
    except PixivError as e1:
        wechat_manager.send_text(client_id, from_wxid, "若曦找不到图了[大哭]~可以给若曦个机会，稍后再试试吗[可怜]")
        __handle_pixiv_error_and_relogin()
        raise e1
    except Exception as e2:
        wechat_manager.send_text(client_id, from_wxid, "若曦已经尽力了，实在找不到这张图[大哭]，拜托换个关键词试试吧~")
        __handle_pixiv_error_and_relogin()
        raise e2


def __send_setu(client_id, from_wxid):
    try:
        setu_filename = setuRepository.download_next_setu()
        wechat_manager.send_image(client_id, from_wxid, "D:\\DEV\\wechat_pc_api\\setu\\" + setu_filename)
    except PixivError as e1:
        wechat_manager.send_text(client_id, from_wxid, "若曦找不到涩图了[大哭]~可以给若曦个机会，稍后再试试吗[可怜]")
        __handle_pixiv_error_and_relogin()
        raise e1
    except Exception as e2:
        wechat_manager.send_text(client_id, from_wxid, "若曦已经尽力了，实在找不到这张图[大哭]，拜托换个关键词试试吧~")
        __handle_pixiv_error_and_relogin()
        raise e2


def __handle_pixiv_error_and_relogin():
    global pixiv_api_error_count
    pixiv_api_error_count += 1
    if pixiv_api_error_count == 3:
        pixiv_api_error_count = 0
        __login_pixiv()


def __login_pixiv():
    api = AppPixivAPI(**__REQUESTS_KWARGS)
    api.auth(refresh_token=__PIXIV_TOKEN["refresh"])


def __is_setu(msg):
    return msg.find("色图") != -1 or msg.find("涩图") != -1 or msg.find("看看批") != -1


def __is_soutu(msg):
    return msg.find("搜图：") != -1


def __send_message_tian(message):
    resp = session.get("http://api.tianapi.com/txapi/robot/index" + "?key=" + __TIAN_KEY + "&question=" + message)
    content = resp.json()["newslist"][0]["reply"]
    return content


def __send_message_itpk(message):
    resp = session.get("http://i.itpk.cn/api.php" + "?api_key="
                       + __IPTK_API_KEY + "&api_secret=" + __IPTK_API_SECRET + "&question=" + message)
    content = resp.text
    return content


def __report_to_master(client_id, msg):
    wechat_manager.send_text(client_id=client_id, to_wxid=__MASTER_WECHAT_ID, text=msg)


def __remove_at_from_msg(msg):
    msg_list = msg.split("@若曦")
    msg = ""
    for m in msg_list:
        msg = msg + m.strip()
    return msg


if __name__ == "__main__":
    # 添加回调实例对象
    wechat_manager.manager_wechat(smart=True)
    # 阻塞主线程
    while input() not in ["q", "quit", "exit"]:
        pass
