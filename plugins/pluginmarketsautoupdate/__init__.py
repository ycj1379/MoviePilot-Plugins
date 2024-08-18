import traceback
from collections import Counter
from datetime import datetime
from threading import Lock
from typing import Any, List, Dict, Tuple, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import set_key
from lxml import html

from app.core.config import settings
from app.core.plugin import PluginManager
from app.log import logger
from app.plugins import _PluginBase
from app.scheduler import Scheduler
from app.schemas import NotificationType
from app.utils.http import RequestUtils

lock = Lock()


class PluginMarketsAutoUpdate(_PluginBase):
    # 插件名称
    plugin_name = "插件库更新推送"
    # 插件描述
    plugin_desc = "支持从官方Wiki中获取记录的最新全量插件库、结合添加黑名单，自动化添加插件库。"
    # 插件图标
    plugin_icon = "upload.png"
    # 插件版本
    plugin_version = "1.6"
    # 插件作者
    plugin_author = "Aqr-K"
    # 作者主页
    author_url = "https://github.com/Aqr-K"
    # 插件配置项ID前缀
    plugin_config_prefix = "pluginmarketsautoupdate_"
    # 加载顺序
    plugin_order = 29
    # 可使用的用户级别
    auth_level = 1

    env_path = settings.CONFIG_PATH / "app.env"

    pluginmanager = PluginManager()

    _enabled = False
    _onlyonce = False
    _corn = 86400
    _enabled_update_notify = False
    _enabled_write_notify = False
    _notify_type = "Plugin"

    _enabled_write_new_markets = False
    _enabled_blacklist = False
    _blacklist = []

    _enabled_auto_get = False
    _enabled_proxy = True
    _timeout = 5
    _wiki_url = "https://wiki.movie-pilot.org/zh/plugin"
    _wiki_url_xpath = '//pre[@class="prismjs line-numbers" and @v-pre="true"]/code/text()'

    _event = None
    _scheduler: Optional[BackgroundScheduler] = None

    def init_plugin(self, config: dict = None):
        """
        初始化插件
        """
        logger.info(f"插件 {self.plugin_name} 初始化")
        if not config:
            return False
        else:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._corn = config.get("corn")
            self._enabled_update_notify = config.get("enabled_update_notify")
            self._enabled_write_notify = config.get("enabled_write_notify")
            self._notify_type = config.get("notify_type")

            self._enabled_write_new_markets = config.get("enabled_write_new_markets")
            self._enabled_blacklist = config.get("enabled_blacklist")
            self._blacklist = config.get("blacklist")

            self._enabled_auto_get = config.get("enabled_auto_get")
            self._enabled_proxy = config.get("enabled_proxy")
            self._timeout = config.get("timeout")
            self._wiki_url = config.get("wiki_url")
            self._wiki_url_xpath = config.get("wiki_url_xpath")

            # 初始化配置
            self.__update_config()

        if self._onlyonce:
            self.task(manual=True)

    def get_state(self):
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
        """
        注册插件公共服务
        """
        try:
            services = []
            if self._enabled and self._corn:
                if isinstance(self._corn, dict):
                    # 提取默认值的value
                    self._corn = self._corn.get("value")

                if self.is_integer(value=self._corn):
                    # 使用内置间隔时间，3600、7200秒等等
                    trigger = "interval"
                    kwargs = {"seconds": int(self._corn)}
                    logger.debug(f"使用间隔时间运行定时任务 - 【{self._corn}】")
                else:
                    raise ValueError("corn不是整数，暂不支持其他格式")
                services = [
                    {
                        "id": "PluginMarketUpdate",
                        "name": "定时扫描Wiki插件库记录",
                        "trigger": trigger,
                        "func": self.task,
                        "kwargs": kwargs
                    }
                ]
            if not services:
                logger.info(f"{self.plugin_name} 插件未启用定时任务")
            return services
        except Exception as e:
            logger.error(f" {self.plugin_name} 插件注册定时认务失败 - {e}")
            return []

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        if self._enabled_auto_get:
            # 允许打开前端时，立刻运行一次，获取Wiki数据获取黑名单表单需要的数据
            self.task(manual=True)

        default_config = {
            "enabled": False,
            "onlyonce": False,
            "corn": 86400,
            "enabled_update_notify": False,
            "enabled_write_notify": False,
            "notify_type": "Plugin",

            "enabled_write_new_markets": False,
            "enabled_blacklist": False,
            "blacklist": [],

            "enabled_auto_get": False,
            "enabled_proxy": True,
            "timeout": 5,
            "wiki_url": "https://wiki.movie-pilot.org/zh/plugin",
            "wiki_url_xpath": '//pre[@class="prismjs line-numbers" and @v-pre="true"]/code/text()',
        }

        # 消息类型
        MsgTypeOptions = []
        for item in NotificationType:
            MsgTypeOptions.append({
                "title": item.value,
                "value": item.name
            })

        corn_options = [
            {'title': '每 1 天', 'value': 86400},
            {'title': '每 2 天', 'value': 172800},
            {'title': '每 3 天', 'value': 259200},
            {'title': '每 4 天', 'value': 345600},
            {'title': '每 5 天', 'value': 432000},
            {'title': '每 6 天', 'value': 518400},
            {'title': '每 7 天', 'value': 604800},
            {'title': '每 15 天', 'value': 1296000},
            {'title': '每 30 天', 'value': 2592000},
            {'title': '每 60 天', 'value': 5184000},
            {'title': '每 90 天', 'value': 7776000},
            {'title': '每 180 天', 'value': 15552000},
            {'title': '每 365 天', 'value': 31536000},
        ]

        markets_list = []

        if self.get_data("data_list"):
            for data in self.get_data("data_list").values():
                markets_list.append({
                    'title': data.get("url"),
                    'value': data.get("url"),
                })
        else:
            for plugin_market in self.__valid_markets_list(plugin_markets=settings.PLUGIN_MARKET, mode="当前ENV配置"):
                markets_list.append({
                    'title': plugin_market,
                    'value': plugin_market,
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
                                            'label': '启用定时运行',
                                            'hint': '开启后插件处于激活状态，并启用定时任务',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 5,
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'onlyonce',
                                            'label': '立刻运行一次',
                                            'hint': '一次性任务；运行后自动关闭',
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
                                        # 选择加手动输入
                                        # 'component': 'VCombobox',
                                        # 只可选择
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'corn',
                                            'label': '定时任务间隔时间',
                                            'hint': '选择定时扫描时间',
                                            'persistent-hint': True,
                                            # 'placeholder': '支持5位cron表达式',
                                            'active': True,
                                            # 'clearable': True,
                                            'items': corn_options,
                                            "item-value": "value",
                                            "item-title": "title",
                                        }
                                    }
                                ]
                            },
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
                                    'md': 4,
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled_update_notify',
                                            'label': '发送更新通知',
                                            'hint': '允许发送新库记录通知',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 5,
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled_write_notify',
                                            'label': '发送写入通知',
                                            'hint': '允许发送新库写入状态通知',
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
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'notify_type',
                                            'label': '自定义消息通知类型',
                                            'items': MsgTypeOptions,
                                            'hint': '选择推送使用的消息类型',
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
                            'align': 'center',
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
                                            'type': 'warning',
                                            'variant': 'tonal',
                                            'style': 'white-space: pre-line;',
                                            'text': '注意：直接返回 "查看数据" 并不会触发刷新，在保存或关闭后，重新打开插件设置，才能查看刷新后的数据统计！！！\n'
                                                    '本插件的写入功能只适用于没有在环境变量中写死 "PLUGIN_MARKET" 的搭建方式，请去除环境变量里的值后再运行！'
                                        }
                                    },
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
                                    'value': 'basic_settings',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '基础设置'
                            },
                            {
                                'component': 'VTab',
                                'props': {
                                    'value': 'advanced_settings',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '高级设置'
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
                                    'value': 'basic_settings',
                                    'style': {
                                        'padding-top': '20px',
                                        'padding-bottom': '20px'
                                    },
                                },
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
                                                            'model': 'enabled_write_new_markets',
                                                            'label': '自动写入新增库',
                                                            'hint': '开启后，新插件库将自动写入env',
                                                            'persistent-hint': True,
                                                        }
                                                    },
                                                ],
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 5,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSwitch',
                                                        'props': {
                                                            'model': 'enabled_blacklist',
                                                            'label': '启用写入黑名单',
                                                            'hint': '黑名单内的插件库不会被写入env',
                                                            'persistent-hint': True,
                                                        }
                                                    },
                                                ],
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 3,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VAlert',
                                                        'props': {
                                                            'type': 'warning',
                                                            'variant': 'tonal',
                                                            'style': 'white-space: pre-line;',
                                                            'text': '问题反馈：'
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'a',
                                                                'props': {
                                                                    'href': 'https://github.com/Aqr-K/MoviePilot-Plugins/issues/new',
                                                                    'target': '_blank'
                                                                },
                                                                'content': [
                                                                    {
                                                                        'component': 'u',
                                                                        'text': 'ISSUES'
                                                                    }
                                                                ]
                                                            }
                                                        ]
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
                                                    'md': 12,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VCombobox',
                                                        'props': {
                                                            'model': 'blacklist',
                                                            'label': 'Wiki插件库地址-黑名单',
                                                            'items': markets_list,
                                                            'clearable': True,
                                                            'multiple': True,
                                                            'placeholder': '支持下拉选择，支持手动输入，输入的地址将不会被写入到app.env中',
                                                            'hint': '选中的插件库将被添加到黑名单中，不会自动添加；已写入env的黑名单插件库，也会在下次运行写入时移除；只移除插件库，插件本身不会被卸载',
                                                            'persistent-hint': True,
                                                            'no-data-text': '没有从 wiki 与 ENV 配置中获取到数据，无法生成快捷选项，可预先手动输入需要加入黑名单的 插件库地址。',
                                                            'active': True,
                                                            'hide-no-data': False,
                                                        }
                                                    }
                                                ]
                                            },
                                        ]
                                    },
                                ]
                            },
                            {
                                'component': 'VWindowItem',
                                'props': {
                                    'value': 'advanced_settings',
                                    'style': {
                                        'padding-top': '20px',
                                        'padding-bottom': '20px'
                                    },
                                },
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
                                                            'model': 'enabled_auto_get',
                                                            'label': '允许前端自动获取Wiki数据',
                                                            'hint': '允许前端打开时，立刻获取Wiki数据',
                                                            'persistent-hint': True,
                                                        }
                                                    },
                                                ],
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 5,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSwitch',
                                                        'props': {
                                                            'model': 'enabled_proxy',
                                                            'label': '启用代理访问',
                                                            'hint': '需要配置 PROXY_HOST',
                                                            'persistent-hint': True,
                                                        }
                                                    },
                                                ],
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 3,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'timeout',
                                                            'label': 'Wiki访问超时时间',
                                                            'hint': '访问超时时间，最低1秒',
                                                            'suffix': '秒',
                                                            'persistent-hint': True,
                                                            'type': 'number',
                                                            'active': True,
                                                        }
                                                    },
                                                ],
                                            },
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
                                                    'md': 12,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'wiki_url',
                                                            'label': 'Wiki插件库记录地址',
                                                            'placeholder': 'https://wiki.movie-pilot.org/zh/plugin',
                                                            'hint': '可自定义地址，留空则使用默认地址',
                                                            'persistent-hint': True,
                                                            'active': True,
                                                            'clearable': True,
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
                                                    'md': 12,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'wiki_url_xpath',
                                                            'label': '记录页面Xpath定位路径',
                                                            'placeholder': '//pre[@class="prismjs line-numbers" and @v-pre="true"]/code/text()',
                                                            'hint': '提取Wiki插件库记录地址的Xpath路径，留空则使用默认Xpath路径',
                                                            'persistent-hint': True,
                                                            'active': True,
                                                            'clearable': True,
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
                                                    'md': 12,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VAlert',
                                                        'props': {
                                                            'type': 'info',
                                                            'variant': 'tonal',
                                                            'style': 'white-space: pre-line;',
                                                            'text': '高级设置注意事项：\n'
                                                                    '1、当官网出现，域名与路径被替换、Xpath变动时，可自行修改高级设置的 "Wiki插件库记录地址"、"记录页面Xpath定位路径"，以保证功能的正常运行。\n\n'
                                                                    '2、启用 "允许前端自动获取Wiki数据" 在打开 "配置页面"(不是"查看数据") 时，后台会激活运行一次，用于获取数据，但相对应，也会增加打开时的显示等待时间。\n\n'
                                                                    '3、启用 "启用代理访问" 需要配置 "PROXY_HOST"；没有配置 "PROXY_HOST" 时，启用该项会默认使用系统网络环境，不会导致运行失败。\n\n'
                                                                    '4、"Wiki访问超时时间" 只支持整数，单位为秒，小数点后的数字会被后台忽略，如：3.5 会被转换为 3 秒；且在输入的参数存在问题的时候，会用默认值 5 秒。\n\n'
                                                                    '5、"Wiki插件库记录地址"、"记录页面Xpath定位路径" 此两项参数，直接关系到是否能成功获取到Wiki官网记录的库地址，不懂得如何获取的用户，请不要随意修改这两项参数！'
                                                        }
                                                    }
                                                ]
                                            }
                                        ],
                                    },
                                ]
                            },
                        ]
                    },
                ]
            },
        ], default_config

    def get_page(self) -> List[dict]:
        """
        拼装插件详情页面，需要返回页面配置，同时附带数据
        """
        data_list = self.get_data("data_list") or {}

        if not data_list:
            return [
                {
                    'component': 'div',
                    'text': '暂无数据',
                    'props': {
                        'class': 'text-center',
                    }
                }
            ]
        else:
            data_list = data_list.values()
            # 按time倒序排序
            data_list = sorted(data_list, key=lambda x: x.get("time") or 0, reverse=True)

        # 表格标题
        headers = [
            {'title': '插件库来源', 'key': 'source', 'sortable': True},
            {'title': '黑名单状态', 'key': 'blacklist', 'sortable': True},
            {'title': '插件库作者', 'key': 'user', 'sortable': True},
            {'title': '插件库名字', 'key': 'repo', 'sortable': True},
            {'title': '插件库分支', 'key': 'branch', 'sortable': True},
            {'title': '插件库地址', 'key': 'url', 'sortable': True},
        ]

        items = [
            {
                'source': data.get("source"),
                'blacklist': data.get("blacklist"),
                'user': data.get("user"),
                'repo': data.get("repo"),
                'branch': data.get("branch"),
                'url': data.get("url"),
            } for data in data_list
        ]

        return [
            {
                'component': 'VRow',
                'props': {
                    'style': {
                        'overflow': 'hidden',
                    }
                },
                'content':
                    self.__get_total_elements() +
                    [
                        {
                            'component': 'VRow',
                            'props': {
                                'class': 'd-none d-sm-block',
                            },
                            'content': [
                                {
                                    'component': 'VCol',
                                    'props': {
                                        'cols': 12,
                                    },
                                    'content': [
                                        {
                                            'component': 'VDataTableVirtual',
                                            'props': {
                                                'class': 'text-sm',
                                                'headers': headers,
                                                'items': items,
                                                'height': '30rem',
                                                'density': 'compact',
                                                'fixed-header': True,
                                                'hide-no-data': True,
                                                'hover': True
                                            },
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
            }
        ]

    def __get_total_elements(self) -> List[dict]:
        """
        组装汇总元素
        """
        # 统计数据
        statistic_info = self.__get_statistic_info()

        total_markets_count = statistic_info.get("total_markets_count") or 0
        wiki_markets_count = statistic_info.get("wiki_markets_count") or 0
        other_markets_count = statistic_info.get("other_markets_count") or 0

        blacklisted_markets_count = statistic_info.get("blacklisted_markets_count") or 0
        in_blacklist_markets_count = statistic_info.get("in_blacklist_markets_count") or 0

        env_markets_count = statistic_info.get("env_markets_count") or 0
        in_env_wiki_markets_count = statistic_info.get("in_env_wiki_markets_count") or 0
        in_env_other_markets_count = statistic_info.get("in_env_other_markets_count") or 0

        time = statistic_info.get("time") or "暂无记录"

        if total_markets_count == 0:
            all_markets_count = "暂无记录"
        else:
            all_markets_count = f"{total_markets_count} / {wiki_markets_count} / {other_markets_count}"

        if total_markets_count == 0 and env_markets_count == 0:
            write_markets_count = "暂无记录"
        else:
            write_markets_count = f"{env_markets_count} / {in_env_wiki_markets_count} / {in_env_other_markets_count}"

        if total_markets_count == 0 and blacklisted_markets_count == 0:
            blacklist_markets_count = "暂无记录"
        else:
            blacklist_markets_count = f"{blacklisted_markets_count} / {in_blacklist_markets_count}"

        return [
            # 库数量
            {
                'component': 'VCol',
                'props': {
                    'cols': 12,
                    'md': 3,
                    'sm': 6
                },
                'content': [
                    {
                        'component': 'VCard',
                        'props': {
                            'variant': 'tonal',
                        },
                        'content': [
                            {
                                'component': 'VCardText',
                                'props': {
                                    'class': 'd-flex align-center',
                                },
                                'content': [

                                    {
                                        'component': 'div',
                                        'content': [
                                            {
                                                'component': 'span',
                                                'props': {
                                                    'class': 'text-caption'
                                                },
                                                'text': '全部插件库 / 官方 / 非官方'
                                            },
                                            {
                                                'component': 'div',
                                                'props': {
                                                    'class': 'd-flex align-center flex-wrap'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'props': {
                                                            'class': 'text-h6'
                                                        },
                                                        'text': all_markets_count
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                ]
            },
            # 写入库数量
            {
                'component': 'VCol',
                'props': {
                    'cols': 12,
                    'md': 3,
                    'sm': 6
                },
                'content': [
                    {
                        'component': 'VCard',
                        'props': {
                            'variant': 'tonal',
                        },
                        'content': [
                            {
                                'component': 'VCardText',
                                'props': {
                                    'class': 'd-flex align-center',
                                },
                                'content': [
                                    {
                                        'component': 'div',
                                        'content': [
                                            {
                                                'component': 'span',
                                                'props': {
                                                    'class': 'text-caption'
                                                },
                                                'text': '本地已配置库 / 官方 / 非官方'
                                            },
                                            {
                                                'component': 'div',
                                                'props': {
                                                    'class': 'd-flex align-center flex-wrap'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'props': {
                                                            'class': 'text-h6'
                                                        },
                                                        'text': write_markets_count
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                ]
            },
            # 黑名单
            {
                'component': 'VCol',
                'props': {
                    'cols': 12,
                    'md': 3,
                    'sm': 6
                },
                'content': [
                    {
                        'component': 'VCard',
                        'props': {
                            'variant': 'tonal',
                        },
                        'content': [
                            {
                                'component': 'VCardText',
                                'props': {
                                    'class': 'd-flex align-center',
                                },
                                'content': [
                                    {
                                        'component': 'div',
                                        'content': [
                                            {
                                                'component': 'span',
                                                'props': {
                                                    'class': 'text-caption'
                                                },
                                                'text': '黑名单库 / 被命中'
                                            },
                                            {
                                                'component': 'div',
                                                'props': {
                                                    'class': 'd-flex align-center flex-wrap'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'props': {
                                                            'class': 'text-h6'
                                                        },
                                                        'text': blacklist_markets_count
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ]
                    },
                ]
            },
            # 上次更新时间
            {
                'component': 'VCol',
                'props': {
                    'cols': 12,
                    'md': 3,
                    'sm': 6
                },
                'content': [
                    {
                        'component': 'VCard',
                        'props': {
                            'variant': 'tonal',
                        },
                        'content': [
                            {
                                'component': 'VCardText',
                                'props': {
                                    'class': 'd-flex align-center',
                                },
                                'content': [
                                    {
                                        'component': 'div',
                                        'content': [
                                            {
                                                'component': 'span',
                                                'props': {
                                                    'class': 'text-caption'
                                                },
                                                'text': '上次更新时间'
                                            },
                                            {
                                                'component': 'div',
                                                'props': {
                                                    'class': 'd-flex align-center flex-wrap'
                                                },
                                                'content': [
                                                    {
                                                        'component': 'span',
                                                        'props': {
                                                            'class': 'text-h6'
                                                        },
                                                        'text': time
                                                    },
                                                ]
                                            },
                                        ]
                                    },
                                ]
                            }
                        ]
                    }
                ]
            },
        ]

    def stop_service(self):
        """
        退出插件
        """
        try:
            if self._scheduler:
                self._scheduler.remove_all_jobs()
                if self._scheduler.running:
                    self._scheduler.shutdown()
                self._scheduler = None
        except Exception as e:
            logger.error("退出插件失败：%s" % str(e))

    # init

    def task(self, manual=False):
        """
        启动插件
        """
        with lock:
            try:
                # 获取Wiki插件库更新的新插件库
                wiki_markets_list, new_markets_list = self.get_wiki_markets_list_and_new_markets_list()
                # 获取已写入的插件库与第三方插件库
                other_markets_list = self.get_env_markets_list_and_other_markets_list(
                    wiki_markets_list=wiki_markets_list)
                # 获取需要写入app.env的插件库
                if self._enabled_write_new_markets:
                    self.write_markets_to_env(wiki_markets_list=wiki_markets_list,
                                              other_markets_list=other_markets_list)
            except Exception as e:
                logger.error(f'{"手动" if manual else "定时"}任务运行失败 - {e}')
                if manual:
                    self._enabled = False
            # 运行成功
            else:
                # 现在的时间，格式 2021-01-01 00:00:00
                time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                # 更新 data_list
                self.__update_and_save_statistic_info(wiki_markets_list=wiki_markets_list,
                                                      other_markets_list=other_markets_list,
                                                      time=time)
            finally:
                self._onlyonce = False
                self.__update_config()

    # 获取Wiki插件库更新

    def get_wiki_markets_list_and_new_markets_list(self) -> Tuple[Optional[list], Optional[list]]:
        """
        获取 Wiki库 与 最新插件库 更新的地址
        """
        try:
            # 获取官方全量插件库
            wiki_markets_list = self._get_wiki_code()
            # 判断是否有新插件库
            new_markets_list = self._get_new_markets_list(wiki_markets_list=wiki_markets_list)
            # 格式修正，补全没有以/结尾的地址
            new_markets_list = [url if url.endswith("/") else f"{url}/" for url in new_markets_list]
            wiki_markets_list = [url if url.endswith("/") else f"{url}/" for url in wiki_markets_list]
            return wiki_markets_list, new_markets_list
        except Exception as e:
            raise Exception(e)

    # 获取全量插件库地址

    def _get_wiki_code(self) -> Optional[list]:
        """
        获取 Wiki 页面的代码
        """
        try:
            res = self.__get_wiki_html()
            # 提取全量插件库地址的code值
            wiki_markets_code = self.__get_code(res=res)
            # 格式化全量插件库地址
            wiki_markets_list = self.__valid_markets_list(plugin_markets=wiki_markets_code, mode="Wiki官网")
            return wiki_markets_list
        except Exception as e:
            raise Exception(f"获取Wiki插件库地址失败 - {e}")

    def __get_wiki_html(self):
        """
        访问 wiki 获取插件库地址
        :return:
        """
        try:
            if self._wiki_url:
                url = self._wiki_url
            else:
                url = "https://wiki.movie-pilot.org/zh/plugin"
            res = RequestUtils(proxies=self.__proxies, timeout=self.__timeout).get_res(url=url)
            if res.status_code != 200:
                raise ValueError(f"访问Wiki页面失败 - {res.status_code}")
            return res
        except Exception as e:
            raise Exception(f"获取Wiki页面失败 - {e}")

    def __get_code(self, res):
        """
        从 wiki 中提取全量插件库地址
        """
        try:
            tree = html.fromstring(res.text)
            if self._wiki_url_xpath:
                code = tree.xpath(self._wiki_url_xpath)
            else:
                code = tree.xpath('//pre[@class="prismjs line-numbers" and @v-pre="true"]/code/text()')
            if not code:
                raise ValueError("未找到Xpath路径的值")
            wiki_markets_code = ''.join(code).strip()
            logger.debug(f"成功提取到当前Wiki记录的全量插件库地址合集 - {wiki_markets_code}")
            return wiki_markets_code
        except Exception as e:
            raise Exception(f"无法从网页中提取全量插件库地址 - {e}")

    # 提取新插件库

    def _get_new_markets_list(self, wiki_markets_list) -> Optional[list]:
        """
        与前一次对比，查看是否有新插件库
        """
        try:
            if self.get_data("data_list"):
                urls = [value['url'] for key, value in self.get_data("data_list").items() if 'url' in value]
                backup_wiki_markets_list = self.__valid_markets_list(plugin_markets=urls, mode="上次更新缓存")
            else:
                backup_wiki_markets_list = []
            # 有上次
            if backup_wiki_markets_list:
                # 有变化
                if backup_wiki_markets_list != wiki_markets_list:
                    new_markets_list = [url for url in wiki_markets_list if url not in backup_wiki_markets_list]
                # 没有变化
                else:
                    new_markets_list = []
            # 没有上次，判定为初始化
            else:
                new_markets_list = wiki_markets_list
        except Exception as e:
            logger.error(f"对比失败 - {e}")
            return []
        else:
            if not new_markets_list:
                logger.info("没有新的插件库更新")
            else:
                if Counter(new_markets_list) != Counter(wiki_markets_list):
                    msg = f"有新的插件库更新"
                else:
                    msg = f"首次获取到插件库"
                logger.info(f'{msg} - 共获取到 {len(new_markets_list)} 个插件库地址')
                if self._enabled_update_notify:
                    self.__send_message(title=self.plugin_name, text=f"{msg} - 共获取到 {len(new_markets_list)} 个插件库地址")
            return new_markets_list

    # 提取已写入的插件库与第三方插件库

    def get_env_markets_list_and_other_markets_list(self, wiki_markets_list):
        """
        提取 已写入的插件库 与 第三方插件库
        """
        try:
            # 提取已经写入env的所有插件库
            env_markets_list = self.__valid_markets_list(plugin_markets=settings.PLUGIN_MARKET, mode="当前ENV配置")
            # 提取已经写入的不在官方库的第三方插件库
            other_markets_list = self.__get_other_markets(env_markets_list=env_markets_list,
                                                          wiki_markets_list=wiki_markets_list)
            # 格式修正
            other_markets_list = [url if url.endswith("/") else f"{url}/" for url in other_markets_list]
            return other_markets_list
        except Exception as e:
            logger.error(f"提取配置失败 - {e}")
            return False

    @staticmethod
    def __get_other_markets(env_markets_list, wiki_markets_list):
        """
        提取已经写入的第三方插件库
        """
        try:
            other_markets = []
            if env_markets_list and wiki_markets_list:
                for url in env_markets_list:
                    if not url.endswith("/"):
                        url += "/"
                    if url not in wiki_markets_list:
                        other_markets.append(url)
                return other_markets
            elif not env_markets_list and wiki_markets_list:
                raise ValueError("未获取到已写入的插件库")
            elif not wiki_markets_list and env_markets_list:
                raise ValueError("未获取到全量插件库")
            else:
                raise ValueError("未获取到已写入的插件库和全量插件库")
        except Exception as e:
            raise Exception(f"提取第三方插件库失败 - {e}")

    # 网络设置

    @property
    def __proxies(self):
        """
        代理设置
        """
        return None if settings.GITHUB_PROXY and self._enabled_proxy else settings.PROXY

    @property
    def __timeout(self) -> int:
        """
        超时设置
        """
        try:
            if self._timeout:
                if isinstance(self._timeout, int):
                    timeout = self._timeout
                elif isinstance(self._timeout, float):
                    timeout = int(self._timeout)
                elif isinstance(self._timeout, str):
                    if self.is_integer(self._timeout):
                        timeout = int(self._timeout)
                    else:
                        raise ValueError("超时时间格式不合法")
                else:
                    raise ValueError("超时时间格式不合法")
                if 1 > int(timeout) >= 0:
                    raise ValueError("超时时间设置不合法，最小为1秒")
                elif int(timeout) < 0:
                    raise ValueError("超时时间设置不合法，不能为负数")
                return int(timeout)
            else:
                raise ValueError("未设置超时时间")
        except Exception as e:
            self._timeout = 5
            self.__update_config()
            logger.error(f"超时时间设置失败，还原并使用默认值 {int(self._timeout)} 秒 - {e}")
            return int(self._timeout)

    # 数据格式与提取

    @staticmethod
    def is_integer(value) -> bool:
        """
        检查字符串是否可以转换为整数
        """
        try:
            if isinstance(value, int):
                return True
            elif isinstance(value, str):
                int(value)
                return True
            elif isinstance(value, float):
                int(value)
                return True
            else:
                return False
        except ValueError:
            return False

    @staticmethod
    def __valid_markets_list(plugin_markets, mode: str = "参数中") -> List[str]:
        """
        数据格式化 - 转换为list
        """
        try:
            if plugin_markets:
                if isinstance(plugin_markets, str):
                    plugin_markets_list = [url.strip() for url in plugin_markets.split(",")]
                elif isinstance(plugin_markets, list):
                    plugin_markets_list = plugin_markets
                elif isinstance(plugin_markets, dict):
                    plugin_markets_list = list(plugin_markets.values())
                else:
                    raise ValueError(f'从 {mode} 提取的插件库地址格式不合法')
                return plugin_markets_list if plugin_markets_list else []
            else:
                return []
        except Exception as e:
            raise Exception(f"数据校验与转化失败 - {e}")

    @staticmethod
    def __get_repo_info(repo_url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        获取Github仓库信息
        :param repo_url: Github仓库地址
        :return: user, repo, branch
        """
        # Todo；后续考虑支持非main分支，需要主程序支持
        if not repo_url:
            return None, None, None
        if not repo_url.endswith("/"):
            repo_url += "/"
        if repo_url.count("/") < 6:
            repo_url = f"{repo_url}main/"
        try:
            user, repo, branch = repo_url.split("/")[-4:-1]
        except Exception as e:
            logger.error(f"解析Github仓库地址失败：{str(e)} - {traceback.format_exc()}")
            return None, None, None
        return user, repo, branch

    # 写入app.env

    def write_markets_to_env(self, wiki_markets_list, other_markets_list):
        try:
            # 提取需要写入的插件库
            write_markets_list = self.__get_write_markets(wiki_markets_list=wiki_markets_list,
                                                          other_markets_list=other_markets_list)
            # 写入app.env
            status = self.__update_env(write_markets_list=write_markets_list)
        except Exception as e:
            raise Exception(f"写入app.env失败 - {e}")
        else:
            logger.info(f"成功覆盖式写入 {len(write_markets_list)} 个插件库地址到app.env")
            if self._enabled_write_notify and status:
                self.__send_message(title=self.plugin_name,
                                    text=f"成功覆盖式写入 {len(write_markets_list)} 个插件库地址到app.env")

    def __get_write_markets(self, wiki_markets_list, other_markets_list):
        """
        生成最后需要更新到env中的值的列表
        """
        all_markets_list = list(set(wiki_markets_list) | set(other_markets_list))
        try:
            if self._enabled_blacklist and self._blacklist:
                blacklist = self.__valid_markets_list(self._blacklist, mode="插件写入黑名单")
                write_markets_list = [url for url in all_markets_list if url not in blacklist]
                return write_markets_list
            else:
                return all_markets_list
        except Exception as e:
            logger.error(f"黑名单失败配置运行失败，默认不使用黑名单筛选 - {e}")
            return all_markets_list

    def __update_env(self, write_markets_list):
        """
        更新env
        """
        try:
            # 判断是否与当前的值一致
            if Counter(write_markets_list) == Counter(self.__valid_markets_list(settings.PLUGIN_MARKET, mode="当前ENV配置")):
                logger.info("当前插件库地址与env配置一致，无需更新")
                return False
            # 将新插件键库转换成str
            if isinstance(write_markets_list, list):
                write_markets_str = ",".join(write_markets_list)
                set_key(dotenv_path=self.env_path, key_to_set="PLUGIN_MARKET", value_to_set=write_markets_str)
            else:
                raise ValueError("写入env的值，格式不合法")
        except Exception as e:
            raise Exception(e)
        else:
            self._update_other_plugins(write_markets_str=write_markets_str)
            return True

    # 同步显示

    def _update_other_plugins(self, write_markets_str):
        """
        同步并更新其他插件
        """
        try:
            flag, installed_plugins = self.__check_settings_plugins_installed()
            if flag:
                logger.info("正在准备同步更新显示")
                for plugin_id, plugin_name in (item for plugin in installed_plugins for item in plugin.items()):
                    config = self.get_config(plugin_id=plugin_id) or {}
                    plugin_market = config.get("PLUGIN_MARKET", "")
                    # 只有在内容变更时，才更新配置
                    if write_markets_str != plugin_market:
                        config["PLUGIN_MARKET"] = write_markets_str
                        self.update_config(config=config, plugin_id=plugin_id)
                        self.__reload_plugin(plugin_id=plugin_id)
                        logger.info(f"【{plugin_name}】更新完成")
                    else:
                        logger.info(f"【{plugin_name}】中的值与当前插件库地址一致，无需更新")
        except Exception as e:
            logger.error(f"同步显示更新任务失败 - {e}")

    def __check_settings_plugins_installed(self) -> (bool, list):
        """
        检查需要同步的插件是否已安装
        """
        plugin_names = {
            "ConfigCenter": "配置中心",
        }

        # 获取本地插件列表
        local_plugins = self.pluginmanager.get_local_plugins()

        # 初始化已安装插件列表
        installed_plugins = []

        # 校验所有的插件是否已安装
        for plugin_id, plugin_name in plugin_names.items():
            plugin = next((p for p in local_plugins if p.id == plugin_id and p.installed), None)
            if plugin:
                installed_plugins.append({plugin_id: plugin_name})

        if installed_plugins:
            return True, installed_plugins

        return False, []

    def __reload_plugin(self, plugin_id: str):
        """
        热加载
        """
        logger.info(f"准备热加载插件: {plugin_id}")

        # 加载插件到内存
        try:
            self.pluginmanager.reload_plugin(plugin_id)
            logger.info(f"成功热加载插件: {plugin_id} 到内存")
        except Exception as e:
            logger.error(f"失败热加载插件: {plugin_id} 到内存. 错误信息: {e}")
            return

        # 注册插件服务
        try:
            Scheduler().update_plugin_job(plugin_id)
            logger.info(f"成功热加载插件到插件服务: {plugin_id}")
        except Exception as e:
            logger.error(f"失败热加载插件到插件服务: {plugin_id}. 错误信息: {e}")
            return

        logger.info(f"已完成插件热加载: {plugin_id}")

    # 推送通知

    def __send_message(self, title: str, text: str, mtype=None):
        """
        推送消息通知
        """
        if not mtype:
            mtype = NotificationType.Plugin
        self.post_message(mtype=mtype, title=title, text=text)

    # 统计

    def __update_and_save_statistic_info(self, wiki_markets_list, other_markets_list, time):
        """
        更新并保存统计信息
        """
        statistic_info = self.__get_statistic_info()
        all_markets_list = list(set(wiki_markets_list) | set(other_markets_list))

        other_markets = []
        wiki_markets = []
        # 直接env配置的库进行对比筛查
        env_markets_list = self.__valid_markets_list(settings.PLUGIN_MARKET, mode="当前ENV配置")
        for url in env_markets_list:
            if not url.endswith("/"):
                url += "/"
            if url not in wiki_markets_list:
                other_markets.append(url)
            else:
                wiki_markets.append(url)

        # 总库数量
        total_markets_count = len(all_markets_list)
        # 官方库数量
        wiki_markets_count = len(wiki_markets_list)
        # 非官方库数量
        other_markets_count = len(other_markets_list)

        # 黑名单库数量
        blacklisted_markets_count = len(self.__valid_markets_list(self._blacklist, mode="插件写入黑名单"))
        # 在总库在黑名单中的库数量
        in_blacklist_markets_count = len(
            [url for url in all_markets_list if url in self.__valid_markets_list(self._blacklist)])

        # env写入库数量
        env_markets_count = len(env_markets_list)
        # 已写入的官方库数量
        in_env_wiki_markets_count = len(wiki_markets)
        # 已写入的非官方库数量
        in_env_other_markets_count = len(other_markets)

        # 头部统计信息
        statistic_info.update({
            "total_markets_count": total_markets_count,
            "wiki_markets_count": wiki_markets_count,
            "other_markets_count": other_markets_count,

            "blacklisted_markets_count": blacklisted_markets_count,
            "in_blacklist_markets_count": in_blacklist_markets_count,

            "env_markets_count": env_markets_count,
            "in_env_wiki_markets_count": in_env_wiki_markets_count,
            "in_env_other_markets_count": in_env_other_markets_count,

            "time": time,
        })

        # 重新生成数据列表
        data_list = {}

        for plugin_market in all_markets_list:
            user, repo, branch = self.__get_repo_info(repo_url=plugin_market)
            source = "Wiki官网" if plugin_market in wiki_markets_list else "非官网"
            data_list[plugin_market] = {
                "source": source,
                "blacklist": "是" if plugin_market in self.__valid_markets_list(self._blacklist) else "否",
                "user": user,
                "repo": repo,
                "branch": branch,
                "url": plugin_market,
            }

        self.save_data("statistic", statistic_info)
        self.save_data("data_list", data_list)

    def __get_statistic_info(self) -> Dict[str, int]:
        """
        获取统计数据
        """
        statistic_info = self.get_data("statistic") or {
            "total_markets_count": 0,
            "wiki_markets_count": 0,
            "other_markets_count": 0,

            "blacklisted_markets_count": 0,
            "in_blacklist_markets_count": 0,

            "env_markets_count": 0,
            "in_env_wiki_markets_count": 0,
            "in_env_other_markets_count": 0,

            "time": 0,
        }
        return statistic_info

    # 更新

    def __update_config(self):
        """
        更新配置
        """
        config = {
            "enabled": self._enabled,
            "onlyonce": self._onlyonce,
            "corn": self._corn,
            "enabled_update_notify": self._enabled_update_notify,
            "enabled_write_notify": self._enabled_write_notify,
            "notify_type": self._notify_type,

            "enabled_write_new_markets": self._enabled_write_new_markets,
            "enabled_blacklist": self._enabled_blacklist,
            "blacklist": self._blacklist,

            "enabled_auto_get": self._enabled_auto_get,
            "enabled_proxy": self._enabled_proxy,
            "timeout": self._timeout,
            "wiki_url": self._wiki_url,
            "wiki_url_xpath": self._wiki_url_xpath,
        }
        self.update_config(config)
