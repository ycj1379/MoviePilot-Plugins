import itertools
import threading
from datetime import datetime, timedelta
from typing import Any, List, Dict, Tuple

import pytz
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.db import SessionFactory
from app.db.models import User
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType, MessageChannel

scheduler_lock = threading.Lock()


class SendCustomMsg(_PluginBase):
    # 插件名称
    plugin_name = "自定义消息汇报"
    # 插件描述
    plugin_desc = "用于手动发送自定义消息，也可用于调试各类消息通知插件。"
    # 插件图标
    plugin_icon = "Synomail_A.png"
    # 插件版本
    plugin_version = "1.2"
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
    _save = False
    _only_send_once = False
    _enabled_scheduled_sends_msg = False
    _scheduled_sends_time = None

    _userid_type = None
    _channel_type = None
    _msg_type = None
    _image = None
    _title = None
    _text = None
    _link = None

    _backup_save = None
    _backup_only_send_once = None
    _backup_enabled_scheduled_sends_msg = None
    _backup_scheduled_sends_time = None

    _backup_channel_type = None
    _backup_msg_type = None
    _backup_userid_type = None
    _backup_title = None
    _backup_text = None
    _backup_image = None
    _backup_link = None

    _scheduler = None
    _event = threading.Event()

    def init_plugin(self, config: dict = None):
        logger.info(f"初始化插件 {self.plugin_name}")

        if config:
            self._only_send_once = config.get("only_send_once", False)
            self._save = config.get("save", True)
            self._enabled_scheduled_sends_msg = config.get("enabled_scheduled_sends_msg", False)
            self._scheduled_sends_time = config.get("scheduled_sends_time", None)
            self._channel_type = config.get("channel_type", [])
            self._msg_type = config.get("msg_type", None)
            self._userid_type = config.get("userid_type", [])
            self._title = config.get("title", None)
            self._text = config.get("text", None)
            self._image = config.get("image", None)
            self._link = config.get("link", None)

        self.run()

    def get_state(self):
        return self._enabled_scheduled_sends_msg

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
        # 消息渠道
        ChannelTypeOptions = []
        for item in MessageChannel:
            ChannelTypeOptions.append({
                "title": item.value,
                "value": item.value
            })
        # 消息类型
        MsgTypeOptions = []
        for item in NotificationType:
            MsgTypeOptions.append({
                "title": item.value,
                "value": item.value
            })

        UserTypeOptions = []

        users = self.__get_users()
        for user in users:
            # 只有激活的用户才能被选中
            if user.get('active'):
                UserTypeOptions.append({
                    "title": f"{'管理员' if user.get('superuser') else '普通用户'} - {user.get('name')}",
                    "value": user.get('name'),
                })
        if UserTypeOptions:
            UserTypeOptions.insert(0, {
                "title": "全部普通用户",
                "value": "all_users",
            })
            UserTypeOptions.insert(0, {
                "title": "全部管理员",
                "value": "all_admins",
            })

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
                                    'md': 6,
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled_scheduled_sends_msg',
                                            'label': '启用定时发送',
                                            'hint': '依赖于定时发送时间，发送后自动关闭',
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
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'scheduled_sends_time',
                                            'label': '定时发送时间',
                                            'hint': '支持直接输入与表单选择两种模式，点击日历图标可进入表单选择',
                                            'persistent-hint': True,
                                            'clearable': True,
                                            'type': 'datetime-local',
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
                                    'md': 6,
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'only_send_once',
                                            'label': '发送本次消息',
                                            'hint': '立即发送消息，单次任务',
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
                                            'model': 'save',
                                            'label': '保留消息',
                                            'hint': '保存当前填写的配置',
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
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'warning',
                                            'variant': 'tonal',
                                            'text': '注意：已经成功启用定时发送任务后，需要重新修改发生配置，但清除定时时间并未设定的情况下，为了保护已经启动的定时任务，修改的配置将不会被更新保存！'
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
                                        'component': 'VAutocomplete',
                                        'props': {
                                            'multiple': True,
                                            'chips': True,
                                            'model': 'channel_type',
                                            'label': '消息渠道',
                                            'placeholder': '支持可选项多选，不支持手动输入',
                                            'items': ChannelTypeOptions,
                                            'clearable': True,
                                            'hint': '选择消息发送的渠道',
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
                                        'component': 'VAutocomplete',
                                        'props': {
                                            'multiple': False,
                                            'model': 'msg_type',
                                            'label': '消息类型',
                                            'placeholder': '只支持可选项单选，不支持手动输入可选项以外参数',
                                            'items': MsgTypeOptions,
                                            "clearable": True,
                                            'hint': '选择消息的类型',
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
                                        'component': 'VCombobox',
                                        'props': {
                                            'multiple': True,
                                            'chips': True,
                                            'model': 'userid_type',
                                            'label': '用户ID',
                                            'placeholder': '支持下拉框多选，支持手动输入多个可选项以外参数，每输入一个参数请回车',
                                            'items': UserTypeOptions,
                                            "clearable": True,
                                            'hint': '自定义用户ID',
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
                                            'hint': '适配各种类字符，支持换行符',
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
                                            'hint': '适配各种类字符，支持换行符',
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
                                    'md': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'image',
                                            'label': '图片地址',
                                            'clearable': True,
                                            'placeholder': '目前只支持输入图片地址或本地路径；本地上传图片功能需要等项目开发组前端支持。',
                                            'hint': '图片URL地址，如果是服务器的本地图片，请自行确定具体路径。',
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
                                    'md': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'link',
                                            'label': '链接地址',
                                            'clearable': True,
                                            'placeholder': 'https://example.com/',
                                            'hint': 'URL链接地址；一般用于需要跳转功能的消息通知。',
                                            'persistent-hint': True,
                                            'active': True,
                                        }
                                    }
                                ]
                            },
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
            'save': False,
            'only_send_once': False,
            'enabled_scheduled_sends_msg': False,
            'scheduled_sends_time': None,
            'channel_type': None,
            'msg_type': None,
            'userid_type': None,
            'title': None,
            'text': None,
            'image': None,
            'link': None,
        }

    def get_page(self) -> List[dict]:
        pass

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

    def __update_config(self):
        """
        更新配置
        """
        config = {
            'only_send_once': self._only_send_once,
            'save': self._save,
            'enabled_scheduled_sends_msg': self._enabled_scheduled_sends_msg,
            'scheduled_sends_time': self._scheduled_sends_time,
            'channel_type': self._channel_type,
            'msg_type': self._msg_type,
            'userid_type': self._userid_type,
            'title': self._title,
            'text': self._text,
            'image': self._image,
            'link': self._link,

            'backup_only_send_once': self._backup_only_send_once,
            'backup_save': self._backup_save,
            'backup_enabled_scheduled_sends_msg': self._backup_enabled_scheduled_sends_msg,
            'backup_scheduled_sends_time': self._backup_scheduled_sends_time,
            'backup_channel_type': self._backup_channel_type,
            'backup_msg_type': self._backup_msg_type,
            'backup_userid_type': self._backup_userid_type,
            'backup_title': self._backup_title,
            'backup_text': self._backup_text,
            'backup_image': self._backup_image,
            'backup_link': self._backup_link,

        }
        self.update_config(config=config)

    def __default_config(self):
        """
        默认配置字典
        """
        self._save = False
        self._only_send_once = False
        self._enabled_scheduled_sends_msg = False
        self._scheduled_sends_time = None
        self._channel_type = None
        self._msg_type = None
        self._userid_type = None
        self._title = None
        self._text = None
        self._image = None
        self._link = None

    def __backup_config(self):
        """
        备份配置字典
        """
        self._backup_save = self._save
        self._backup_only_send_once = self._only_send_once
        self._backup_enabled_scheduled_sends_msg = self._enabled_scheduled_sends_msg
        self._backup_scheduled_sends_time = self._scheduled_sends_time
        self._backup_channel_type = self._channel_type
        self._backup_msg_type = self._msg_type
        self._backup_userid_type = self._userid_type
        self._backup_title = self._title
        self._backup_text = self._text
        self._backup_image = self._image
        self._backup_link = self._link

    def __restore_config(self):
        """
        从备份配置还原配置
        """
        self._save = self._backup_save
        self._only_send_once = self._backup_only_send_once
        self._enabled_scheduled_sends_msg = self._backup_enabled_scheduled_sends_msg
        self._scheduled_sends_time = self._backup_scheduled_sends_time
        self._channel_type = self._backup_channel_type
        self._msg_type = self._backup_msg_type
        self._userid_type = self._backup_userid_type
        self._title = self._backup_title
        self._text = self._backup_text
        self._image = self._backup_image
        self._link = self._backup_link

    # init 初始化

    def run(self):
        """
        运行插件
        """
        # 保存配置
        if not self._enabled_scheduled_sends_msg:
            if self._save:
                if (not self._text
                        and not self._title
                        and not self._image
                        and not self._link
                        and not self._msg_type
                        and not self._channel_type
                        and not self._userid_type
                        and not self._scheduled_sends_time
                        and not self._only_send_once
                        and not self._enabled_scheduled_sends_msg
                        and not self._save):
                    logger.info("插件初始化成功！")
                else:
                    self.__backup_config()
                    logger.info("消息配置保存成功！")
            else:
                if (not self._text
                        and not self._title
                        and not self._image
                        and not self._link
                        and not self._msg_type
                        and not self._channel_type
                        and not self._userid_type
                        and not self._scheduled_sends_time
                        and not self._only_send_once
                        and not self._enabled_scheduled_sends_msg
                        and not self._save):
                    logger.info("插件初始化成功！")
                else:
                    self.__default_config()
                    logger.warning("消息配置已清空！")

        # 发送自定义消息
        if self._only_send_once:
            if self._text or self._title:
                self._send_msg()
                self._only_send_once = False
                self.__update_config()
            else:
                msg = "消息主题和内容都是空的，必须填写其中一项，否则无法发送自定义消息！"
                logger.warning(msg)
                self.systemmessage.put(msg)
                self._only_send_once = False
                self.__update_config()

        else:
            # 定时发送消息
            self._handle_scheduled_task()

    # 定时任务

    def _handle_scheduled_task(self):
        """
        处理定时任务
        """
        # 启动定时任务开关
        if self._enabled_scheduled_sends_msg:
            # 有定时时间
            if self._scheduled_sends_time:
                # 检查定时器合法性
                if self.__convert_time_format():
                    # 配置完整
                    if self._title or self._text:
                        self.__handle_existing_scheduler()
                    else:
                        self.__handle_incomplete_configuration()
                else:
                    self.__handle_invalid_timer()
            else:
                self.__handle_missing_timer()
        else:
            self.__handle_disabled_scheduler()

    def __handle_existing_scheduler(self):
        """
        处理现有定时任务
        """
        if self._scheduler:
            self._scheduler.remove_all_jobs()
            if self._save:
                logger.info("定时任务已更新，重新加载定时任务！")
            else:
                logger.info("定时任务已更新，未启动保存配置，自动保存本次配置，重新启动定时任务！")
        else:
            if self._save:
                logger.info("配置已保存，定时任务已启动！")
            else:
                logger.info("未启动保存配置，自动保存本次配置，定时任务已启动！")
        self.__backup_config()
        self.__update_config()
        self._scheduled_task()

    def __handle_incomplete_configuration(self):
        """
        处理配置不完整的情况
        """
        if self._scheduler:
            self.__restore_config()
            self.__update_config()
            msg = "消息主题和内容都是空的，必须填写其中一项，否则无法发送自定义消息！抛弃本次配置，恢复原配置，继续运行已存在的定时任务！"
        else:
            if self._save:
                msg = "消息主题和内容都是空的，必须填写其中一项，否则无法发送自定义消息！保存已填写配置！"
            else:
                msg = "消息主题和内容都是空的，必须填写其中一项，否则无法发送自定义消息！未启动保存配置，抛弃本次消息配置！"
                self.__default_config()
            self._enabled_scheduled_sends_msg = False
            self.__update_config()
        logger.warning(msg)
        self.systemmessage.put(msg)

    def __handle_invalid_timer(self):
        """
        处理定时器不合法的情况
        """
        if self._scheduler:
            self.__restore_config()
            self.__update_config()
            msg = "定时发送时间解析失败，无法更新定时任务！抛弃本次配置，恢复原配置！继续运行已存在的定时任务！"
        else:
            if self._save:
                msg = "定时发送时间解析失败，无法启用定时任务！保存已填写配置！"
            else:
                msg = "定时发送时间解析失败，无法启用定时任务！未启动保存配置，抛弃本次消息配置！"
                self.__default_config()
            self._enabled_scheduled_sends_msg = False
            self.__update_config()
        logger.warning(msg)
        self.systemmessage.put(msg)

    def __handle_missing_timer(self):
        """
        处理缺少定时时间的情况
        """
        if self._scheduler:
            self.__restore_config()
            self.__update_config()
            msg = "已存在定时任务，当前配置缺少定时时间，抛弃本次消息配置，维持原有消息配置！"
        else:
            if self._save:
                msg = "缺少定时时间，无法启用定时任务！保存已填写配置！"
            else:
                msg = "缺少定时时间，无法启用定时任务！未启动保存配置，抛弃本次消息配置！"
                self.__default_config()
            self._enabled_scheduled_sends_msg = False
            self.__update_config()
        logger.warning(msg)
        self.systemmessage.put(msg)

    def __handle_disabled_scheduler(self):
        """
        处理没有启动定时任务开关的情况
        """
        if self._scheduler:
            self.stop_service()
            logger.warning("取消定时发送任务！")

    def _scheduled_task(self):
        """
        定时任务
        """

        if self._scheduled_sends_time:
            # 转换时间格式
            timedata = self.__convert_time_format()

            if timedata:
                # 启动定时任务
                if not self._scheduler:
                    self._scheduler = BackgroundScheduler(timezone=settings.TZ)
                # 清空已存在的定时任务
                if len(self._scheduler.get_jobs()):
                    logger.info(
                        "已经存在待执行的定时发送任务，清空现有的待执行的定时发送任务，并更新尝试启用新的定时发送任务！")
                    self._scheduler.remove_all_jobs()

                self._scheduler.add_job(
                    func=self._send_msg,
                    kwargs={"scheduler": True},
                    trigger="date",
                    run_date=timedata,
                    name="单次定时发送消息",
                )
                logger.info("已添加定时发送任务，等待执行！")
                if self._scheduler.get_jobs():
                    self._scheduler.print_jobs()
                if not self._scheduler.running:
                    self._scheduler.start()
            else:
                msg = "定时发送时间解析失败，无法启用定时任务！"
                logger.error(msg)
                self.systemmessage.put(f"{msg}")
        else:
            if self._scheduler:
                msg = "定时发送时间为空，继续运行已存在的定时任务！"
            else:
                msg = "定时发送时间为空，无法启用定时任务！"
            logger.warning(msg)
            self.systemmessage.put(f"{msg}")

    def __convert_time_format(self):
        """
        转换时间格式
        """
        try:
            # 解析时间格式，增加微秒
            send_time = datetime.strptime(self._scheduled_sends_time, "%Y-%m-%dT%H:%M").replace(microsecond=1)
            # 判断时间是否在当前时间之前
            if send_time < datetime.now() + timedelta(seconds=3):
                raise ValueError("输入了一个过期的时间")
            logger.info(f"定时任务时间大于当前时间，允许添加定时发送任务！")
            # 转换格式
            timedata = pytz.timezone(settings.TZ).localize(send_time).isoformat(timespec='microseconds')
            # 去除日期和时间之间的分隔符
            timedata = timedata.replace("T", " ")
        except Exception as e:
            logger.error(f"时间格式转换失败 - {e}")
            timedata = None
        return timedata

    # 发送消息

    def _send_msg(self, scheduler=False):
        """
        发送自定义消息
        """
        log_type = "定时任务" if scheduler else "手动任务"
        logger.info(f"{log_type} - 开始发送自定义消息")
        msg = None
        try:
            if self._title or self._text:
                channel_type = self._get_values(data=self._channel_type)
                userid_type = self._get_values(data=self._userid_type, user_mode=True)

                if not channel_type and userid_type:
                    channels = [None]  # 没有渠道
                    users = userid_type
                elif channel_type and not userid_type:
                    channels = channel_type
                    users = [None]  # 没有用户
                elif channel_type and userid_type:
                    channels = channel_type
                    users = userid_type
                else:
                    channels = [None]
                    users = [None]
                for channel, userid in itertools.product(channels, users):
                    self.post_message(channel=channel,
                                      mtype=self._msg_type,
                                      title=self._title,
                                      text=self._text,
                                      image=self._image,
                                      userid=userid,
                                      link=self._link)
                    continue

                msg = f"{log_type} - 自定义消息发送成功！"
                logger.info(msg)
            else:
                msg = f"{log_type} - 主题和内容都是空的，必须填写其中一项，否则无法发送自定义消息！"
                logger.warning(msg)
                return True
        except Exception as e:
            msg = f"{log_type} - 自定义消息发送失败！"
            logger.error(f"{msg} - 错误 - {e}")
            return False

        finally:
            # 如果是定时任务，发送消息不管是否成功都，关闭定时任务
            if self._enabled_scheduled_sends_msg and scheduler is True:
                self._enabled_scheduled_sends_msg = False
                self.__update_config()
                self.stop_service()
                logger.info("定时任务执行完毕，关闭定时任务！")
                if not self._save:
                    self.__default_config()
                    self.__update_config()
                    logger.info("定时任务执行完毕，清空当前的消息配置！")
                else:
                    logger.info("定时任务执行完毕，已启用消息保存功能，保留当前的消息配置！")

            if self._only_send_once and scheduler is False:
                self.systemmessage.put(f"{msg}")

    # 数据处理

    @staticmethod
    def _get_values(data: list, user_mode=False) -> list:
        """
        数据处理
        """
        values = []
        values_set = set()

        if not data:
            return values

        for item in data:
            if isinstance(item, dict) and 'value' in item:
                value = item['value']
            else:
                value = item

            if value not in {"all_users", "all_admins"}:
                if value not in values_set:
                    values.append(value)
                    values_set.add(value)

            # 用户模式专用
            if user_mode:
                # 只在用户模式下处理 "all_users" 和 "all_admins"
                if value == "all_users":
                    # 获取全部普通用户
                    user_names = [user.get('name') for user in SendCustomMsg.__get_users() if not user.get('superuser')]
                    unique_users = [name for name in user_names if name not in values_set]
                    values.extend(unique_users)
                    values_set.update(unique_users)
                elif value == "all_admins":
                    # 获取全部管理员
                    user_names = [user.get('name') for user in SendCustomMsg.__get_users() if user.get('superuser')]
                    unique_users = [name for name in user_names if name not in values_set]
                    values.extend(unique_users)
                    values_set.update(unique_users)
        return values

    @staticmethod
    def __get_users():
        """
        获取用户列表
        """
        with SessionFactory() as db:
            users = db.query(User).all()
            user_list = [
                {
                    'name': user.name,
                    'active': user.is_active,
                    'superuser': user.is_superuser
                }
                for user in users
            ]
            return user_list
