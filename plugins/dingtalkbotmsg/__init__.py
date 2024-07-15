from typing import Any, List, Dict, Tuple

from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType
from app.utils.http import RequestUtils

import threading

lock = threading.Lock()


class DingTalkBotMsg(_PluginBase):
    # 插件名称
    plugin_name = "钉钉机器人消息通知"
    # 插件描述
    plugin_desc = "支持使用钉钉群聊机器人发送消息通知。"
    # 插件图标
    plugin_icon = "https://raw.githubusercontent.com/Aqr-K/MoviePilot-Plugins/main/icons/dongjiqiang.png"
    # 插件版本
    plugin_version = "1.3"
    # 插件作者
    plugin_author = "Aqr-k"
    # 作者主页
    author_url = "https://github.com/Aqr-k"
    # 插件配置项ID前缀
    plugin_config_prefix = "dingtalkbotmsg_"
    # 加载顺序
    plugin_order = 28
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _enabled = False
    _send_image_enabled = False
    _webhook_url = None
    _msgtypes = []

    _scheduler = None
    _event = threading.Event()

    def init_plugin(self, config: dict = None):
        """
        初始化插件
        """
        if config:
            self._enabled = config.get("enabled")
            self._send_image_enabled = config.get("send_image_enabled")
            self._webhook_url = config.get("webhook_url")
            self._msgtypes = config.get("msgtypes") or []

        self.__update_config()

    def __update_config(self):
        """
        更新插件配置
        """
        config = {
            "enabled": self._enabled,
            "send_image_enabled": self._send_image_enabled,
            "webhook_url": self._webhook_url,
            "msgtypes": self._msgtypes
        }
        self.update_config(config)

    def get_state(self) -> bool:
        return self._enabled and (True if self._webhook_url else False)

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
                        'props': {
                            'align': 'center',
                        },
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 3
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
                                    'md': 3,
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'send_image_enabled',
                                            'label': '发送图片',
                                            'hint': '是否发送图片消息',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'props': {
                            'align': 'center',
                        },
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'webhook_url',
                                            'label': '机器人WebHook地址',
                                            'placeholder': 'https://oapi.dingtalk.com/robot/send?access_token=xxxxxxxxx',
                                            'clearable': True,
                                            'hint': '机器人WebHook地址，用于连接发送消息通知',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'props': {
                            'align': 'center',
                        },
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
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
                                            'hint': '选择需要发送的消息类型',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'props': {
                            'align': 'center',
                        },
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'style': 'white-space: pre-line;',
                                            'content': '请提前到"钉钉"群聊中，创建机器人，并获取 Webhook 地址。'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ], {
            "enabled": False,
            "send_image_enabled": False,
            'webhook_url': '',
            'msgtypes': []
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
        # 图像
        image = msg_body.get("image")

        if not title and not text:
            logger.warn("标题和内容不能同时为空")
            return

        if (msg_type and self._msgtypes
                and msg_type.name not in self._msgtypes):
            logger.info(f"消息类型 {msg_type.value} 未开启消息发送")
            return
        with lock:
            self.send_to_dingtalk_bot(title, text, image)

    def send_to_dingtalk_bot(self, title: str, text: str, image: str = None):
        """
        发送消息到钉钉机器人
        """
        try:
            if image and self._send_image_enabled:
                payload = {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": title,
                        "text": "#### **" + title + "** \n" + text.replace('\n', ' \n ###### ') + "\n ![image](" + image + ")"
                    }
                }

            else:
                payload = {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": title,
                        "text": "#### **" + title + "** \n" + text.replace('\n', ' \n ###### ')
                    }
                }

            res = RequestUtils(content_type="application/json").post_res(self._webhook_url, json=payload)
            if res and res.status_code == 200:
                ret_json = res.json()
                errcode = ret_json.get('errcode')
                errmsg = ret_json.get('errmsg')
                if errcode == 0:
                    logger.info("钉钉机器人消息发送成功")
                else:
                    logger.warning(f"钉钉机器人消息发送失败，错误码：{errcode}，错误原因：{errmsg}")
            elif res is not None:
                logger.warning(f"钉钉机器人消息发送失败，错误码：{res.status_code}，错误原因：{res.reason}")
            else:
                logger.warning("钉钉机器人消息发送失败，未获取到返回信息")
        except Exception as msg_e:
            logger.error(f"钉钉机器人消息发送失败，{str(msg_e)}")

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
            logger.info(str(e))
