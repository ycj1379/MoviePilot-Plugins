import threading
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from urllib.parse import urlparse
import random

Lock = threading.Lock()


class MqttClient(_PluginBase):
    # 插件名称
    plugin_name = "MQTT消息交互（测试版）"
    # 插件描述
    plugin_desc = "可接入HomeAssistant，支持使用智能家居设备，汇报状态信息。"
    # 插件图标
    plugin_icon = "Ha_A.png"
    # 插件版本
    plugin_version = "0.1"
    # 插件作者
    plugin_author = "Aqr-K"
    # 作者主页
    author_url = "https://github.com/Aqr-K"
    # 插件配置项ID前缀
    plugin_config_prefix = "mqttclient_"
    # 加载顺序
    plugin_order = 29
    # 可使用的用户级别
    auth_level = 1

    # 回调函数状态
    connect_type = ""
    connect_success = None

    # client
    mqtt_client = None
    now_client_loop_thread_ident = None
    now_client_loop_thread_name = None
    now_client_id: Optional[str] = None

    # 插件配置项
    _enabled: bool = False

    # Broker 服务器

    _broker_anonymous: bool = False  # 匿名模式增加6位随机后缀
    _broker_client_id: Optional[str] = None  # 客户端ID，匿名模式下可不填，填了则为前缀
    _broker_protocol = mqtt.MQTTv311  # 协议版本，对应MQTTv3.1、MQTTv3.1.1、MQTTv5

    _broker_address: Optional[str] = None  # 服务器地址
    _broker_port: Optional[int] = None  # 服务器端口
    _broker_transport: str = "tcp"  # 传输层协议

    _broker_username: Optional[str] = ''  # 用户名
    _broker_password: Optional[str] = ''  # 密码

    # Publisher 发布者

    _publisher_enabled: bool = False  # 发布端开关
    _publisher_onlyonce: bool = False  # 发布测试消息
    _publisher_msgtypes_cn_enabled: bool = False  # 中文消息类型
    _publisher_msgtypes = []  # 接受的消息类型
    _publisher_topic: str = None  # 主题名前缀
    _publisher_qos: int = 2  # 消息质量

    # _publisher_send_image: bool = False  # 发送图片

    # Subscriber 订阅者
    _subscriber_enabled: bool = False
    _subscriber_onlyonce: bool = False

    # log 日志

    _clean_all_log: bool = False  # 立刻清理全部日志
    _onlyonce_clean: bool = False  # 立刻整理一次
    _log_clean_enabled: bool = False  # 日志记录最大数量开关
    _log_max_lines: Optional[int] = 100  # 日志记录最大数量

    log_path: Path = settings.LOG_PATH / "plugins" / "mqttclient.log"

    # 事件调度
    _scheduler: Optional[BackgroundScheduler] = BackgroundScheduler(timezone=settings.TZ)
    _event = threading.Event()

    def init_plugin(self, config: dict = None):
        logger.info("MQTT 插件 初始化")

        if config:
            self._enabled = config.get("enabled", False)
            self._log_clean_enabled = config.get("log_clean_enabled", False)

            self._broker_anonymous = config.get("anonymous", False)
            self._broker_client_id = config.get("client_id", None)
            self._broker_protocol = config.get("protocol", mqtt.MQTTv311)
            self._broker_address = config.get("broker_address", None)
            self._broker_port = config.get("broker_port", None)
            self._broker_transport = config.get("transport", "tcp")
            self._broker_username = config.get("username", None)
            self._broker_password = config.get("password", None)

            self._publisher_enabled = config.get("published_enabled", False)
            self._publisher_topic = config.get("publisher_topic", "MoviePilot")
            self._publisher_qos = config.get("publisher_qos", 0)
            self._publisher_msgtypes = config.get("publisher_msgtypes", [])

            self._subscriber_enabled = config.get("subscriber_enabled", False)
            self._subscriber_onlyonce = config.get("subscriber_onlyonce", False)

            self._clean_all_log = config.get("clean_all_log", False)
            self._onlyonce_clean = config.get("onlyonce_clean", False)
            self._log_max_lines = config.get("log_max_lines", 100)

        self.client_stop()

        self._onlyonce_test()

        if self._enabled:
            if self._broker_anonymous is False and self._broker_client_id is (None or ""):
                self._enabled = False
                self.__update_config()
                self.systemmessage.put(f"参数不全，关闭插件！请启动匿名模式或者填写客户端ID！")
            if self._publisher_enabled is False and self._subscriber_enabled is False:
                self._enabled = False
                self.systemmessage.put(f"参数不全，关闭插件！消息发布与消息订阅，至少需要启用一项！")
            if self._enabled:
                if self.client_start():
                    self.systemmessage.put(f"MQTT 插件启动成功！")
                else:
                    self.systemmessage.put(f"MQTT 插件启动失败，请查看日志，定位错误原因！")
                    self._enabled = False

        self._onlyonce_clean_logs()
        self.__update_config()

    def __update_config(self):
        """
        更新配置
        """
        config = {
            "enabled": self._enabled,
            "log_clean_enabled": self._log_clean_enabled,

            "now_client_loop_thread_name": self.now_client_loop_thread_name,
            "now_client_loop_thread_ident": self.now_client_loop_thread_ident,
            "now_client_id": self.now_client_id,

            "anonymous": self._broker_anonymous,
            "client_id": self._broker_client_id,
            "protocol": self._broker_protocol,
            "broker_address": self._broker_address,
            "broker_port": self._broker_port,
            "transport": self._broker_transport,
            "username": self._broker_username,
            "password": self._broker_password,

            "published_enabled": self._publisher_enabled,
            "publisher_onlyonce": self._publisher_onlyonce,
            "publisher_msgtypes_cn_enabled": self._publisher_msgtypes_cn_enabled,
            "publisher_topic": self._publisher_topic,
            "publisher_qos": self._publisher_qos,
            "publisher_msgtypes": self._publisher_msgtypes,

            "subscriber_enabled": self._subscriber_enabled,
            "subscriber_onlyonce": self._subscriber_onlyonce,

            "clean_all_log": self._clean_all_log,
            "onlyonce_clean": self._onlyonce_clean,
            "log_max_lines": self._log_max_lines,

        }
        self.update_config(config)

    def get_state(self):
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        [{
            "id": "服务ID",
            "name": "服务名称",
            "trigger": "触发器：cron/interval/date/CronTrigger.from_crontab()",
            "func": self.xxx,
            "kwargs": {} # 定时器参数
        }]
        """
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        MsgTypeOptions = []
        for item in NotificationType:
            MsgTypeOptions.append({
                "title": item.value + " - " + item.name,
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
                                    'md': 4,
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
                                    'md': 6,
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'log_clean_enabled',
                                            'label': '启用日志整理',
                                            'hint': '订阅或发送后，根据 日志记录最大数量 进行限制整理',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            },
                        ]
                    },
                    {
                        'component': 'VRow',
                        'props': {
                            'align': 'center'
                        },
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'now_client_loop_thread_name',
                                            'label': '当前客户端保活线程名',
                                            'placeholder': '未获取到客户端保活线程名',
                                            'hint': '显示连接后的客户端的保活线程名',
                                            'persistent-hint': True,
                                            'readonly': True,
                                            'active': True,
                                        },
                                    },
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'now_client_loop_thread_ident',
                                            'label': '当前客户端保活线程唯一ID',
                                            'placeholder': '未获取到客户端保活线程唯一ID',
                                            'hint': '显示连接后的客户端的保活线程唯一ID',
                                            'persistent-hint': True,
                                            'readonly': True,
                                            'active': True,
                                        },
                                    },
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 4,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'now_client_id',
                                            'label': '当前客户端ID',
                                            'placeholder': '未获取到客户端ID',
                                            'hint': '显示连接后的客户端ID',
                                            'persistent-hint': True,
                                            'readonly': True,
                                            'active': True,
                                        },
                                    },
                                ]
                            },
                        ]
                    },
                    {
                        'component': 'VRow',
                        'props': {
                            'align': 'center'
                        },
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'text': '以上三项，仅用于显示客户端启动后，动态获取的每次保存后生成的动态属性，如有需要自行复制。\n'
                                                    '\n'
                                                    '注意：消息发布者与消息订阅者，至少需要启用一项。两项都未启用时，会关闭插件开关，避免性能占用。',
                                            'style': 'white-space: pre-line;',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VTabs',
                        'props': {
                            'model': '_tabs',
                            'height': 72,
                            'fixed-tabs': True,
                            'style': {
                                'margin-top': '8px',
                                'margin-bottom': '10px',
                            }
                        },
                        'content': [
                            {
                                'component': 'VTab',
                                'props': {
                                    'value': 'client_setting',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '服务器参数'
                            },
                            {
                                'component': 'VTab',
                                'props': {
                                    'value': 'publish_setting',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '消息发布者'
                            },
                            {
                                'component': 'VTab',
                                'props': {
                                    'value': 'subscribe_setting',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '消息订阅者'
                            },
                            {
                                'component': 'VTab',
                                'props': {
                                    'value': 'log_setting',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '日志设置'
                            },
                        ]
                    },
                    {
                        'component': 'VWindow',
                        'props': {
                            'model': '_tabs',
                        },
                        'content': [
                            {
                                'component': 'VWindowItem',
                                'props': {
                                    'value': 'client_setting',
                                    'style': {
                                        'padding-top': '20px',
                                        'padding-bottom': '20px'
                                    },
                                },
                                'content': [
                                    {
                                        'component': 'VRow',
                                        'props': {
                                            'align': 'center'
                                        },
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 4,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSwitch',
                                                        'props': {
                                                            'model': 'anonymous',
                                                            'label': '匿名模式',
                                                            'hint': '开启后，将自动生成6位随机客户端ID',
                                                            'persistent-hint': True,
                                                            'active': True,
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 4,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'client_id',
                                                            'label': '客户端ID',
                                                            'placeholder': '非匿名模式下，固定客户端唯一ID',
                                                            'clearable': True,
                                                            'hint': '启用匿名模式时，则视为前缀，后缀仍是随机',
                                                            'persistent-hint': True,
                                                            'active': True,
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': '12',
                                                    'md': 4,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSelect',
                                                        'props': {
                                                            'model': 'protocol',
                                                            'label': 'MQTT 协议版本',
                                                            'placeholder': '未选择，此项必选',
                                                            'items': [
                                                                {'title': 'MQTT v3.1', 'value': mqtt.MQTTv31},
                                                                {'title': 'MQTT v3.1.1', 'value': mqtt.MQTTv311},
                                                                {'title': 'MQTT v5.0', 'value': mqtt.MQTTv5},
                                                            ],
                                                            'hint': '必须项；选择服务器支持的协议版本',
                                                            'persistent-hint': True,
                                                            'active': True,
                                                        }
                                                    }
                                                ]
                                            },
                                        ]
                                    },
                                    {
                                        'component': 'VRow',
                                        'props': {
                                            'align': 'center'
                                        },
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': '12',
                                                    'md': 4
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'broker_address',
                                                            'label': 'MQTT 服务器地址',
                                                            'placeholder': 'mqtt.com or 127.0.0.1',
                                                            'clearable': True,
                                                            'hint': '必须项；服务器的地址，不需要加任何协议头',
                                                            'persistent-hint': True,
                                                            'active': True,
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': '12',
                                                    'md': 4,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'broker_port',
                                                            'label': 'MQTT 服务器端口',
                                                            'placeholder': '常见：1883、8083、8084  ……',
                                                            'clearable': True,
                                                            'hint': '必须项；服务器地址的端口号：1~65535',
                                                            'persistent-hint': True,
                                                            'maxlength': 5,
                                                            'type': 'number',
                                                            'active': True,
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': '12',
                                                    'md': 4,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSelect',
                                                        'props': {
                                                            'model': 'transport',
                                                            'label': '连接方式',
                                                            'placeholder': '未选择，此项必选',
                                                            'items': [
                                                                {'title': 'tcp', 'value': 'tcp'},
                                                                {'title': 'websockets', 'value': 'websockets'},
                                                                {'title': 'unix', 'value': 'unix'},
                                                            ],
                                                            'hint': '必须项；使用unix前，请确认服务器是否支持',
                                                            'persistent-hint': True,
                                                            'active': True,
                                                        }
                                                    }
                                                ]
                                            },
                                        ]
                                    },
                                    {
                                        'component': 'VRow',
                                        'props': {
                                            'align': 'center'
                                        },
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': '12',
                                                    'md': 6,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'username',
                                                            'label': 'MQTT 认证用户',
                                                            'placeholder': 'username or client ID',
                                                            'clearable': True,
                                                            'hint': '选填。服务器认证用户名或客户端ID',
                                                            'persistent-hint': True,
                                                            'active': True,
                                                        }
                                                    },
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': '12',
                                                    'md': 6,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'password',
                                                            'label': 'MQTT 认证密码/密钥',
                                                            'placeholder': 'password or token',
                                                            'clearable': True,
                                                            'hint': '选填。服务器的认证密码/密钥',
                                                            'persistent-hint': True,
                                                            'active': True,
                                                        }
                                                    }
                                                ]
                                            },
                                        ]
                                    },
                                    {
                                        'component': 'VRow',
                                        'props': {
                                            'align': 'center'
                                        },
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 12,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VAlert',
                                                        'props': {
                                                            'type': 'info',
                                                            'variant': 'tonal',
                                                            'text': '暂时只支持："无认证"、"用户名+密码/密钥"、"Client ID+密码/密钥" 三种登陆方式。\n'
                                                                    '暂不支持使用Tls加密连接链路；请谨慎使用，尽量不要与部署在公网上的 MQTT 服务器进行连接。\n'
                                                                    '暂时只支持接入单个 MQTT 服务器，不支持接入服务器节点集群。',
                                                            'style': 'white-space: pre-line;',
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                ]
                            },
                            {
                                'component': 'VWindowItem',
                                'props': {
                                    'value': 'publish_setting',
                                    'style': {
                                        'padding-top': '20px',
                                        'padding-bottom': '20px'
                                    },
                                },
                                'content': [
                                    {
                                        'component': 'VRow',
                                        'props': {
                                            'align': 'center'
                                        },
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 4,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSwitch',
                                                        'props': {
                                                            'model': 'published_enabled',
                                                            'label': '启用消息发布者',
                                                            'hint': '开启后发布端将处于激活状态',
                                                            'persistent-hint': True,
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 4,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSwitch',
                                                        'props': {
                                                            'model': 'onlyonce_publish',
                                                            'label': '发布一次测试消息',
                                                            'hint': '一次性任务，订阅 "主题名(如果有)/Test" 查看',
                                                            'persistent-hint': True,
                                                        }
                                                    }
                                                ]
                                            },
                                        ]
                                    },
                                    {
                                        'component': 'VRow',
                                        'props': {
                                            'align': 'center'
                                        },
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 4,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSwitch',
                                                        'props': {
                                                            'model': 'publisher_msgtypes_cn_enabled',
                                                            'label': '中文消息类型名称',
                                                            'hint': '使用中文消息类型作，不启用则用英文',
                                                            'persistent-hint': True,
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 4
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'publisher_topic',
                                                            'label': '主题名',
                                                            'placeholder': 'MoviePilot',
                                                            'clearable': True,
                                                            'hint': '选填；缺省时，默认使用接受消息类型作为主题名',
                                                            'persistent-hint': True,
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 4
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSelect',
                                                        'props': {
                                                            'model': 'publisher_qos',
                                                            'label': '消息质量（Qos）',
                                                            'items': [
                                                                {'title': 'Qos 0', 'value': 0},
                                                                {'title': 'Qos 1', 'value': 1},
                                                                {'title': 'Qos 2', 'value': 2},
                                                            ],
                                                            'hint': '必须项；消息的质量等级',
                                                            'persistent-hint': True,
                                                        }
                                                    }
                                                ]
                                            },
                                        ]
                                    },
                                    {
                                        'component': 'VRow',
                                        'props': {
                                            'align': 'center'
                                        },
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 12
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VAutocomplete',
                                                        'props': {
                                                            'multiple': True,
                                                            'chips': True,
                                                            'model': 'publisher_msgtypes',
                                                            'label': '消息类型',
                                                            'items': MsgTypeOptions,
                                                            'clearable': True,
                                                            'hint': '自定义需要接受并发布的消息类型',
                                                            'persistent-hint': True,
                                                        }
                                                    }
                                                ]
                                            },
                                        ]
                                    },
                                    {
                                        'component': 'VRow',
                                        'props': {
                                            'align': 'center'
                                        },
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 12,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VAlert',
                                                        'props': {
                                                            'type': 'info',
                                                            'variant': 'tonal',
                                                            'text': '订阅方式：不启动中文模式时，主题名/消息类型，如 "MoviePilot/Plugin" ，主题名留空，则填写消息类型即可。\n'
                                                                    '斜杠 / 为自动生成，如果没有主题名，订阅时则不需要 / 。\n'
                                                                    '注意：每个消息类型都视为单独的订阅，应写成 ”MoviePilot/插件消息" "MoviePilot/手动订阅通知" 多个订阅。\n',
                                                            'style': 'white-space: pre-line;',
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VRow',
                                        'props': {
                                            'align': 'center'
                                        },
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 12,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VAlert',
                                                        'props': {
                                                            'type': 'info',
                                                            'variant': 'tonal',
                                                            'text': '消息质量（Qos）等级说明：\n'
                                                                    'Qos 0 ：消息发布不会等待消息订阅者的确认。消息可能会丢失，但不会进行重传。\n'
                                                                    'Qos 1 ：消息发布如果没有收到确认回调，会一直重传，直到接收到消息订阅者的确认回调。在高频重传时，可能会收到多条内容一样的消息的问题。\n'
                                                                    'Qos 2 ：在 "Qos 1" 的基础上，增加消息发布者会二次确认机制，确保消息订阅者只会收到一次消息，避免接受重复消息。',
                                                            'style': 'white-space: pre-line;',
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                ]
                            },
                            {
                                'component': 'VWindowItem',
                                'props': {
                                    'value': 'subscribe_setting',
                                    'style': {
                                        'padding-top': '20px',
                                        'padding-bottom': '20px'
                                    },
                                },
                                'content': [
                                    {
                                        'component': 'VForm',
                                        'content': [
                                            {
                                                'component': 'div',
                                                'text': '预留项，待更新',
                                                'props': {
                                                    'class': 'text-center',
                                                }
                                            },
                                        ]
                                    },
                                ]
                            },
                            {
                                'component': 'VWindowItem',
                                'props': {
                                    'value': 'log_setting',
                                    'style': {
                                        'padding-top': '20px',
                                        'padding-bottom': '20px'
                                    },
                                },
                                'content': [
                                    {
                                        'component': 'VRow',
                                        'props': {
                                            'align': 'center'
                                        },
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 4,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSwitch',
                                                        'props': {
                                                            'model': 'clean_all_log',
                                                            'label': '立刻清理全部日志',
                                                            'hint': '一次性任务，清空日志文件',
                                                            'persistent-hint': True,
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 4,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSwitch',
                                                        'props': {
                                                            'model': 'onlyonce_clean',
                                                            'label': '立刻整理一次日志',
                                                            'hint': '一次性任务，依赖于日志记录最大数量',
                                                            'persistent-hint': True,
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 4,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'log_max_lines',
                                                            'label': '日志记录最大数量',
                                                            'placeholder': '必须大于等于0',
                                                            'hint': '选填；必须大于等于0，保存的最近的记录的最大数量',
                                                            'persistent-hint': True,
                                                            'type': 'number',
                                                            'clearable': True,
                                                        }
                                                    }
                                                ]
                                            },
                                        ]
                                    },
                                    {
                                        'component': 'VRow',
                                        'props': {
                                            'align': 'center'
                                        },
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VAlert',
                                                        'props': {
                                                            'type': 'info',
                                                            'variant': 'tonal',
                                                            'text': '启用最大记录数量后，每次发送任务结束，不管是否发送成功，'
                                                                    '都将进行整理，该功能处理方式为删除文件内记录！\n'
                                                                    "\n"
                                                                    '清空所有日志记录功能不需要依赖于启用最大记录数量。\n'
                                                                    '\n'
                                                                    '同时启用立刻清空所有日志与立刻整理日志时，'
                                                                    '优先运行立刻整理日志，且自动关闭清空所有日志开关，'
                                                                    '避免误操作！',
                                                            'style': 'white-space: pre-line;',
                                                        }
                                                    }
                                                ]
                                            },
                                        ]
                                    },
                                ]
                            },
                        ]
                    },
                ]
            }
        ], {
            "enabled": False,

            "broker_anonymous": False,
            "broker_client_id": None,
            "broker_protocol": mqtt.MQTTv311,
            "broker_address": None,
            "broker_port": None,
            "broker_transport": "tcp",
            "broker_username": None,
            "broker_password": None,

            "published_enabled": False,
            "publish_onlyonce": False,
            "publisher_msgtypes_cn_enabled": False,
            "publisher_topic": "MoviePilot",
            "publisher_qos": 2,
            "publisher_msgtypes": [],

            "clean_all_log": False,
            "onlyonce_clean": False,
            "log_clean_enabled": False,
            "log_max_lines": 100,
        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        退出插件
        """
        try:
            self.client_stop()
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._event.set()
                    self._scheduler.shutdown(wait=False)
                    self._event.clear()
                self._scheduler = None
        except Exception as e:
            logger.error(str(e))

    # data validation 数据校验

    def _validate_broker_address(self):
        """
        服务器地址
        """
        try:
            if not self._broker_address:
                raise Exception("请填写 MQTT 服务器地址")

            broker_address = self._broker_address

            if '://' not in broker_address:
                # 如果不包含，假定它是一个主机名，并将其解析为网络位置
                _broker_address = '//' + self._broker_address
            else:
                _broker_address = self._broker_address

            parsed = urlparse(_broker_address)

            if parsed.scheme:
                raise Exception(f"输入的服务器地址包含了协议头，请去掉协议头【 {parsed.scheme}:// 】")

            if parsed.path:
                raise Exception(f"输入的服务器地址包含了路径，请去掉路径【 {parsed.path} 】")

            if parsed.params:
                raise Exception(f"输入的服务器地址包含了参数，请去掉参数【 {parsed.path} 】")

            if parsed.query:
                raise Exception(f"输入的服务器地址包含了查询字符串，请去掉查询字符串【 {parsed.path} 】")

            if parsed.fragment:
                raise Exception(f"输入的服务器地址包含了片段，请去掉片段【 {parsed.path} 】")

            if parsed.port:
                raise Exception(f"输入的服务器地址包含了端口，请去掉端口【 :{parsed.port} 】")

            if not parsed.netloc:
                raise Exception("输入的服务器地址，不是IP地址或者域名")

        except Exception as e:
            raise Exception(e)
        return broker_address

    def _validate_broker_port(self):
        """
        服务器端口
        """
        try:
            if int(self._broker_port) <= 0 or int(self._broker_port) > 65535:
                raise Exception("请填写正确的 MQTT 服务器端口，范围 1-65535")
            broker_port = self._broker_port
        except Exception:
            raise Exception("请填写有效的 MQTT 服务器端口")
        return broker_port

    def _validate_client_id(self):
        """
        客户端ID
        """
        try:
            if self._broker_anonymous:
                if self._broker_client_id:
                    if self._broker_client_id[-1] == "_":
                        _ = ""
                    else:
                        _ = "_"
                    client_id = self._broker_client_id + _ + str(random.randint(100000, 999999))
                else:
                    client_id = str(random.randint(100000, 999999))
            else:
                if self._broker_client_id:
                    client_id = self._broker_client_id
                else:
                    raise Exception("请填写 MQTT 客户端唯一ID或打开随机客户端ID")
        except Exception as e:
            raise Exception(e)
        return client_id

    def data_validation(self):
        """
        数据校验
        """
        try:
            # 服务器地址
            broker_address = self._validate_broker_address()
            # 服务器端口
            broker_port = self._validate_broker_port()
            # 客户端ID
            client_id = self._validate_client_id()
            # 返回数据
            return broker_address, broker_port, client_id
        except Exception as e:
            raise Exception(e)

    # broker 服务器

    def client_start(self):
        """
        连接服务器
        """
        try:
            broker_address, broker_port, client_id = self.data_validation()
            self.mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2,
                                           client_id=str(client_id),
                                           protocol=self._broker_protocol,
                                           transport=self._broker_transport)
            if self._broker_username:
                self.mqtt_client.username_pw_set(username=str(self._broker_username), password=str(self._broker_password))
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.connect(host=str(broker_address), port=int(broker_port))

            if self.mqtt_client:
                self.client_loop_start(client_id=client_id)
                if self.connect_success:
                    logger.info(self.connect_type)
                else:
                    self.client_stop()
                    self.mqtt_client = None
                    raise Exception(self.connect_type)
            self.__update_config()
            return True
        except Exception as e:
            logger.error(f"客户端启动失败 - {e}")
            return False
        finally:
            self._clean_log()

    def on_connect(self, _client, _userdata, _connect_flags, _reason_code, _properties):
        """
        连接回调函数 - API v2.0
        """
        if _reason_code == 0:
            self.connect_success = True
            self.connect_type = f"连接成功"
        else:
            self.connect_success = False
            self.connect_type = f"连接失败 - {_reason_code}"
        logger.debug(self.connect_type)

    def client_loop_start(self, client_id):
        """
        启动循环进行服务器保活
        """
        try:
            if self.mqtt_client:
                self.mqtt_client.loop_start()
                for thread in threading.enumerate():
                    if thread.name == f'paho-mqtt-client-{client_id}':
                        self.now_client_loop_thread_ident = thread.ident
                        self.now_client_loop_thread_name = thread.name
                        self.now_client_id = client_id
                        self.__update_config()
                        logger.info(f"成功启动保活线程 - 线程名：【 {thread.name} 】 - 线程ID:【 {thread.ident} 】")
                        break
            else:
                raise Exception("未找到客户端对象，无法启动保活线程")
        except Exception as e:
            raise Exception(f"保活线程启动失败 - {e}")

    def client_stop(self):
        """
        断开服务器
        """
        try:
            if self.mqtt_client:
                self.mqtt_client.disconnect()
            self.client_loop_stop()
            if self.now_client_id and self.now_client_loop_thread_ident and self.now_client_loop_thread_name:
                logger.info(f"已终止 【 {self.now_client_id} 】 客户端的保活线程 - "
                            f"线程名：【 {self.now_client_loop_thread_name} 】 - "
                            f"线程ID：【 {self.now_client_loop_thread_ident} 】")
            self.now_client_id = None
            self.now_client_loop_thread_ident = None
            self.now_client_loop_thread_name = None
            self.__update_config()
        except Exception as e:
            logger.error(f"断开 MQTT 服务器连接失败 - {e}")

    def client_loop_stop(self):
        """
        断开循环
        """
        try:
            if self.now_client_loop_thread_ident and self.now_client_loop_thread_name:
                for thread in threading.enumerate():
                    if (thread.ident == self.now_client_loop_thread_ident and
                            thread.name == self.now_client_loop_thread_name):
                        # 设置线程终止标志
                        thread._thread_terminate = True
                        break
        except Exception as e:
            logger.error(f"后台线程终止失败 - {e}")

    # Publisher 发布者

    @eventmanager.register(EventType.NoticeMessage)
    def send(self, event: Event):
        """
        消息发送事件
        """
        if not self.get_state():
            return
        if not self._publisher_enabled:
            return
        if not event.event_data:
            return
        msg_body = event.event_data
        channel = msg_body.get("channel")
        if channel:
            return
        msg_type: NotificationType = msg_body.get("type")
        title = msg_body.get("title")
        text = msg_body.get("text")
        image = msg_body.get("image")
        userid = msg_body.get("userid")
        if not title and not text:
            logger.warning("标题和内容不能同时为空")
            return
        if (msg_type and self._publisher_msgtypes
                and msg_type.name not in self._publisher_msgtypes):
            logger.info(f"消息类型 {msg_type.value} 未开启消息发送")
            return
        self.start_publisher(msg_type=msg_type, title=title, text=text, image=image, userid=userid)

    def start_publisher(self, msg_type, title, text, image=None, userid=None):
        """
        发布消息
        """
        with Lock:
            try:
                if (not self.now_client_id or
                        not self.mqtt_client or
                        not self.now_client_loop_thread_ident or
                        not self.now_client_loop_thread_name):
                    self.client_stop()
                    self.client_start()
                    self.__update_config()

                topic_value, userid_value, title_value, text_value, image_value = (
                    self._publish_data_check(_msg_type=msg_type, _title=title, _text=text, _image=image,
                                             _userid=userid, _topic_type=str(self._publisher_topic)))
                topic, payload = self._publisher_data_build(_topic_value=topic_value, _userid_value=userid_value,
                                                            _title_value=title_value, _text_value=text_value,
                                                            _image_value=None)
                self._publish_message(topic=topic, payload=payload)
                self.mqtt_client.on_publish = self.on_publish
                logger.info(f"发布消息成功 - {topic}")
            except Exception as e:
                logger.error(f"发布消息失败 - {e}")
                raise Exception(e)
            finally:
                self._clean_log()

    # TODO: 后续增加图片传送，现在暂时不支持
    def _publish_data_check(self, _msg_type, _title, _text, _image=None, _userid=None, _topic_type=None):
        """
        发布通知校验
        """
        if _msg_type:
            if self._publisher_msgtypes_cn_enabled:
                if _topic_type:
                    topic_value = f"{_topic_type}/{_msg_type.value}"
                else:
                    topic_value = f"{_msg_type.value}"
            else:
                if _topic_type:
                    topic_value = f"{_topic_type}/{_msg_type.name}"
                else:
                    topic_value = f"{_msg_type.name}"
        else:
            raise Exception("消息类型不能为空，无法生成主题")
        if _userid:
            userid_value = f"用户 {_userid} 的 "
        else:
            userid_value = ""
        if _title:
            title_value = f"{_title}"
        else:
            title_value = ""
        if _text:
            text_value = f"{_text}"
        else:
            text_value = ""
        # TODO: 图片预留
        # if image and self._send_image:
        #     image_value = f"图片：{image}"
        # else:
        #     image_value = ""
        # Todo: 暂时不支持图片
        image_value = None

        return topic_value, userid_value, title_value, text_value, image_value

    @staticmethod
    def _publisher_data_build(_topic_value, _userid_value, _title_value, _text_value, _image_value=None):
        """
        消息数据
        """
        topic = f"{_topic_value}"
        payload = (f"收到 {_userid_value}{_topic_value} 消息"
                   f"\n "
                   f"{_title_value}"
                   f"\n"
                   f"{_text_value}"
                   # f"\n"
                   # f"{_image_value}"
                   )
        logger.debug(f"发布消息\n{topic}\n{payload}")

        return topic, payload

    def _publish_message(self, topic, payload=None, retain=False, properties=None):
        """
        发布消息
        :param topic: 消息名，string类型
        :param payload: 消息内容，string类型
        """
        try:
            if self.mqtt_client:
                result = self.mqtt_client.publish(topic=topic, payload=payload,
                                                  qos=self._publisher_qos, retain=retain, properties=properties)
            else:
                raise Exception("未连接到 MQTT 服务器")
            return result
        except Exception as e:
            raise Exception(e)

    @staticmethod
    def on_publish(_client, _userdata, mid, _reason_code, _properties=None):
        """
        MQTT 客户端发布消息回调函数

        Args:
        - client: MQTT 客户端对象
        - userdata: 用户数据
        - mid: 消息 ID
        """
        logger.info(f"消息 {mid} 已发布")

    # logs 日志清理

    def _onlyonce_clean_logs(self):
        """
        立刻清理日志
        """
        if self._onlyonce_clean:
            if int(self._log_max_lines) >= 1:
                self._clean_log()
            else:
                self.systemmessage.put("最大记录数量不能小于等于0，清理日志失败！")
            self._onlyonce_clean = False
            self._clean_all_log = False
            self.__update_config()

        elif self._clean_all_log:
            try:
                with open(self.log_path, 'w', encoding='utf-8') as file:
                    file.truncate(0)
            except Exception as e:
                self.systemmessage(f"清空日志失败 - 原因 - {e}")
            self._clean_all_log = False
            self.__update_config()

    def _clean_log(self):
        """
        按需清理日志
        """
        try:
            if not self._log_clean_enabled:
                return
            if self._log_max_lines is None or self._log_max_lines == "" or int(self._log_max_lines) <= 0:
                return
            with open(self.log_path, 'r+', encoding="utf-8") as file:
                lines = file.readlines()
                if len(lines) > int(self._log_max_lines):
                    file.seek(0)
                    file.writelines(lines[-int(self._log_max_lines):])
                    file.truncate()
                    if self._onlyonce_clean:
                        logger.info(f"成功整理了 {len(lines)-int(self._log_max_lines)} 条消息")

        except Exception as e:
            logger.warning(f"日志最大保存限制失败 - 原因 - {e}")

    # test 测试模式

    def _onlyonce_test(self):
        """
        发送测试
        :return:
        """
        with Lock:
            try:
                if self._publisher_onlyonce or self._subscriber_onlyonce:
                    if (not self.now_client_id or
                            not self.mqtt_client or
                            not self.now_client_loop_thread_ident or
                            not self.now_client_loop_thread_name):
                        self.client_stop()
                        self.client_start()

                    if self._publisher_onlyonce:
                        self.start_publisher(msg_type="Test", title="插件测试", text="这是一条测试消息~~~", image=None,
                                             userid="测试用户")
                    # todo: 订阅测试
                    if self._subscriber_onlyonce:
                        pass

                    if not self._enabled:
                        self.client_stop()
            except Exception as e:
                logger.error(f"测试模式运行失败 - {e}")

            finally:
                self._publisher_onlyonce = False
                self._subscriber_onlyonce = False
                self.__update_config()
                self._clean_log()
