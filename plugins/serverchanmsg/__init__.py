from typing import Any, List, Dict, Tuple
from urllib.parse import urlencode

from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.utils.http import RequestUtils

import threading

lock = threading.Lock()


class ServerChanMsg(_PluginBase):
    # 插件名称
    plugin_name = "Server酱消息通知"
    # 插件描述
    plugin_desc = "支持使用Server酱发送消息通知。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/Aqr-K/MoviePilot-Plugins/main/icons/ServerChan.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "Aqr-K"
    # 作者主页
    author_url = "https://github.com/Aqr-K"
    # 插件配置项ID前缀
    plugin_config_prefix = "serverchanmsg_"
    # 加载顺序
    plugin_order = 31
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _onlyonce = False

    _enabled = False
    _serverchan_key = None
    _msgtypes = []

    _scheduler = None
    _event = threading.Event()

    def init_plugin(self, config: dict = None):
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._msgtypes = config.get("msgtypes") or []
            self._serverchan_key = config.get("serverchan_key")

        if self._onlyonce:
            flag = self.send_msg(title="Server酱消息通知测试", text="Server酱消息通知测试成功！")
            if flag:
                self.systemmessage.put("Server酱消息通知测试成功！")
            self._onlyonce = False

        self.__update_config()

    def __update_config(self):
        """
        更新配置
        :return:
        """
        config = {
            "enabled": self._enabled,
            "msgtypes": self._msgtypes,
            "serverchan_key": self._serverchan_key,
            "onlyonce": self._onlyonce
        }
        self.update_config(config)

    def get_state(self) -> bool:
        return self._enabled and (True if self._serverchan_key else False)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        # 编历 NotificationType 枚举，生成消息类型选项
        MsgTypeOptions = []
        for item in NotificationType:
            MsgTypeOptions.append({
                "title": item.value,
                "value": item.name
            })
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                            'hint': '开启后插件将处于激活状态',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '测试消息',
                                            'hint': '一次性任务，允运行后自动关闭',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            }

                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'serverchan_key',
                                            'label': '密钥',
                                            'placeholder': 'token: xxxxxxxxxxxxxx',
                                            'hint': 'ServerChan密钥',
                                            'persistent-hint': True,
                                            'clearable': True,
                                        }
                                    }
                                ]
                            },
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': True,
                                            'chips': True,
                                            'model': 'msgtypes',
                                            'label': '消息类型',
                                            'items': MsgTypeOptions,
                                            'clearable': True,
                                            'hint': '自定义需要接受并发送的消息类型',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                ]
            }
        ], {
            "enabled": False,
            "onlyonce": False,
            'msgtypes': [],
            'serverchan_key': '',
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType.NoticeMessage)
    def send(self, event: Event):
        """
        消息发送事件
        """
        if not self.get_state():
            return

        if not event.event_data:
            return

        msg_body = event.event_data
        # 渠道
        channel = msg_body.get("channel")
        if channel:
            return
        # 类型
        msg_type: NotificationType = msg_body.get("type")
        # 标题
        title = msg_body.get("title")
        # 文本
        text = msg_body.get("text")

        if not title and not text:
            logger.warn("标题和内容不能同时为空")
            return

        if (msg_type and self._msgtypes
                and msg_type.name not in self._msgtypes):
            logger.info(f"消息类型 {msg_type.value} 未开启消息发送")
            return
        self.send_msg(title=title, text=text)

    def send_msg(self, title, text):
        """
        发送消息
        :param title:
        :param text:
        :return:
        """
        with lock:
            try:
                if not self._serverchan_key:
                    raise Exception("未添加ServerChan密钥")

                serverchan_url = "https://sctapi.ftqq.com/%s.send?%s" % (self._serverchan_key,
                                                                         urlencode(
                                                                             {"title": title,
                                                                              "desp": text}
                                                                         ))

                res = RequestUtils().get_res(serverchan_url)
                if res:
                    ret_json = res.json()
                    errno = ret_json.get('code')
                    error = ret_json.get('message')
                    if errno == 0:
                        logger.info("ServerChan消息发送成功")
                    else:
                        raise Exception(f"ServerChan消息发送失败：{error}")
                elif res is not None:
                    raise Exception(f"ServerChan消息发送失败，错误码：{res.status_code}，错误原因：{res.reason}")
                else:
                    raise Exception(f"ServerChan消息发送失败：未获取到返回信息")
                return True
            except Exception as msg_e:
                logger.error(f"ServerChan消息发送失败：{str(msg_e)}")
                return False

    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._event.set()
                    self._scheduler.shutdown(wait=False)
                    self._event.clear()
                self._scheduler = None
        except Exception as e:
            logger.error(str(e))
