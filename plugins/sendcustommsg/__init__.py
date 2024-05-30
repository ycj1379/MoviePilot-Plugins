from typing import Any, List, Dict, Tuple

from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType, MessageChannel


class SendCustomMsg(_PluginBase):
    # 插件名称
    plugin_name = "自定义消息汇报"
    # 插件描述
    plugin_desc = "支持手动发送自定义消息，也可用于调试各类消息通知插件。"
    # 插件图标
    plugin_icon = "Synomail_A.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "Aqr-K"
    # 作者主页
    author_url = "https://github.com/Aqr-K"
    # 插件配置项ID前缀
    plugin_config_prefix = "sendcustommsg_"
    # 加载顺序
    plugin_order = 5
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _save = True
    _enabled = False

    _userid_type = None
    _channel_type = None
    _msg_type = None
    _image = None

    _title = None
    _text = None

    def init_plugin(self, config: dict = None):
        logger.info(f"初始化插件 {self.plugin_name}")

        if config:
            self._save = config.get("save", True)
            self._enabled = config.get("enabled", False)
            self._channel_type = config.get("channel_type", None)
            self._msg_type = config.get("msg_type", None)
            self._userid_type = config.get("userid_type", None)
            self._title = config.get("title", None)
            self._text = config.get("text", None)
            self._image = config.get("image", None)

        # 发送自定义消息
        if self._enabled:
            self._send_msg()
            self._enabled = False
            self.__update_config()

        # 保存配置
        if self._save:
            self.__update_config()
            logger.warning("消息保留成功！")
            self.systemmessage.put(f"{self.plugin_name}消息保留成功！")

        # 还原成默认配置
        else:
            self.__default_config()
            self.__update_config()

    def _send_msg(self):
        logger.warning("开始发送自定义消息")
        try:
            if self._title or self._text:
                self.post_message(channel=self._channel_type,
                                  mtype=self._msg_type,
                                  title=self._title,
                                  text=self._text,
                                  image=self._image,
                                  userid=self._userid_type)
                msg = "自定义消息发送成功！"
            else:
                msg = "主题和内容都是空的，必须填写其中一项，否则无法发送自定义消息！"
        except Exception as e:
            msg = f"自定义消息发送失败！错误：{e}"

        logger.warning(f"{msg}")
        self.systemmessage.put(f"{msg}")

    def get_state(self):
        pass

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
        # 消息渠道选项
        ChannelTypeOptions = []
        for item in MessageChannel:
            ChannelTypeOptions.append({
                "title": item.value,
                "value": item.value
            })

        # 消息类型选项
        MsgTypeOptions = []
        for item in NotificationType:
            MsgTypeOptions.append({
                "title": item.value,
                "value": item.value
            })

        # Todo：暂时只支持手动输入用户ID，后续尝试增加支持当前用户列表自动获取
        # UserTypeOptions = []
        # for user in users:
        #     UserTypeOptions.append({
        #         "title": f"用户名：{user.name} - 用户状态：{user.is_active}",
        #         "value": user.id
        #     })

        return [
            {
                'component': 'VForm',
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
                                    'md': 3
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '发送本次消息',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 2
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'save',
                                            'label': '保留消息',
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 7
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'warning',
                                            'variant': 'tonal',
                                            'text': '注意：保留消息关闭时，所有配置将在点击保存按钮后清空！！'
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
                                    'md': 4
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': False,
                                            'model': 'channel_type',
                                            'label': '消息渠道',
                                            'items': ChannelTypeOptions,
                                            'clearable': True,
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
                                            'multiple': False,
                                            'model': 'msg_type',
                                            'label': '消息类型',
                                            'items': MsgTypeOptions,
                                            "clearable": True
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
                                        # 'component': 'VSelect',
                                        'component': 'VTextField',
                                        'props': {
                                            'multiple': False,
                                            'model': 'userid_type',
                                            'label': '用户ID',
                                            'placeholder': '该参数将被作为{userid}变量的值。',
                                            # 'items': UserTypeOptions,
                                            "clearable": True
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'title',
                                            'label': '消息主题',
                                            'clearable': True,
                                            'placeholder': '消息主题与文本内容必须填写其中一项，否则无法发送自定义消息！',
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
                                        'component': 'VTextarea',
                                        'props': {
                                            'model': 'text',
                                            'label': '文本内容',
                                            'placeholder': '消息主题与文本内容必须填写其中一项，否则无法发送自定义消息！',
                                            "clearable": True,
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
                                    'md': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'image',
                                            'label': '图片地址',
                                            'clearable': True,
                                            'placeholder': '目前只支持输入url类型的图片地址；上传本地图片需要等待项目开发组支持。',
                                        }
                                    }
                                ]
                            },
                            # {
                            #     'component': 'VCol',
                            #     'props': {
                            #         'cols': 12,
                            #         'md': 2
                            #     },
                            #     'content': [
                            #         {
                            #             'component': 'VSwitch',
                            #             'props': {
                            #                 'model': 'watch_image',
                            #                 'label': '查看图片',
                            #             }
                            #         }
                            #     ]
                            # },
                            # {
                            #     'component': 'VCol',
                            #     'props': {
                            #         'cols': 12,
                            #         'md': 5
                            #     },
                            #     'content': [
                            #         {
                            #             'component': 'VFileInput',
                            #             'props': {
                            #                 'model': 'image',
                            #                 'label': '图片',
                            #                 'show-size': '1024',
                            #                 'small-chips': True,
                            #                 'prepend-icon': "mdi-image",
                            #                 'accept': 'image/png, image/jpeg, image/bmp',
                            #             },
                            #         }
                            #     ]
                            # },
                            # {
                            #     'component': 'VCol',
                            #     'props': {
                            #         'cols': 12,
                            #         'md': 5
                            #     },
                            #     'content': [
                            #         {
                            #             'component': 'VAlert',
                            #             'props': {
                            #                 'type': 'warning',
                            #                 'variant': 'tonal',
                            #                 'text': '注意：图片不会被保存，请重新导入！！'
                            #             }
                            #         }
                            #     ]
                            # }
                        ]
                    },
                    # {
                    #     'component': 'VDialog',
                    #     'props': {
                    #         'model': 'watch_image',
                    #         'max-width': '65rem',
                    #         'overlay-class': 'v-dialog--scrollable v-overlay--scroll-blocked',
                    #         'content-class': 'v-card v-card--density-default v-card--variant-elevated rounded-t'
                    #     },
                    #     'content': [
                    #         {
                    #             'component': 'VCard',
                    #             'props': {
                    #                 'title': "查看图片"
                    #             },
                    #             'content': [
                    #                 {
                    #                     'component': "VDialogCloseBtn",
                    #                     'props': {
                    #                         'model': "watch_image"
                    #                     }
                    #                 },
                    #                 {
                    #                     'component': "VCardText",
                    #                     'props': {},
                    #                     'content': [
                    #                         {
                    #                             'component': 'VRow',
                    #                             'content': [
                    #                                 {
                    #                                     'component': 'VCol',
                    #                                     'props': {
                    #                                         'cols': 12,
                    #                                     },
                    #                                     'content': [
                    #                                         {
                    #                                             'component': 'VImg',
                    #                                             'props': {
                    #                                                 'model': 'image',
                    #                                                 'src': 'image',
                    #                                             },
                    #                                         }
                    #                                     ]
                    #                                 }
                    #                             ]
                    #                         },
                    #                     ]
                    #                 }
                    #             ]
                    #         }
                    #     ]
                    # }
                ]
            }
        ], {
            'title': None,
            'text': None,

            'image': None,
            'channel_type': None,
            'msg_type': None,
            'userid_type': None,

            'save': False,
            'enabled': False,
        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        退出插件
        """
        pass

    def __update_config(self):
        """
        更新配置
        """
        config = {
            'enabled': self._enabled,
            'channel_type': self._channel_type,
            'msg_type': self._msg_type,
            'userid_type': self._userid_type,
            'title': self._title,
            'text': self._text,
            'image': self._image,
            'save': self._save,
        }
        self.update_config(config=config)

    def __default_config(self):
        """
        默认配置字典
        """
        self._save = False
        self._enabled = False
        self._channel_type = None
        self._msg_type = None
        self._userid_type = None
        self._title = None
        self._text = None
        self._image = None
