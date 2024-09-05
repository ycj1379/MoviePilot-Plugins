import inspect
import os
from abc import ABC, abstractmethod
from typing import Any, Tuple, List, Dict, Optional

from app.core.event import EventManager
from app.db.plugindata_oper import PluginDataOper
from app.db.systemconfig_oper import SystemConfigOper
from app.helper.message import MessageHelper
from app.log import logger
from app.plugins import _PluginBase, PluginChian
from app.schemas.types import NotificationType
from version import APP_VERSION


class CloudDisk(ABC):
    """
    基类
    """
    # 组件key
    comp_key: str = ""
    # 组件名称
    comp_name: str = ""
    # 组件顺序
    comp_order: int = 0
    # 组件最低版本
    comp_min_version: str = "v1.9.7"
    # 组件最高版本
    comp_max_version: Optional[str] = None
    # 组件跳过版本
    comp_skip_version: List[str] = []
    # 允许启动

    # 配置相关
    # 组件缺省配置
    config_default: Dict[str, Any] = {
        # "notify_enabled": False,
        # "notify_type": "Plugin",
        # "corn": 0,
        # "params": "",
    }

    helper = None
    params_key = None
    authorization = False

    def __init__(self, plugin: _PluginBase):
        """
        :param plugin: 插件对象
        """
        # 插件数据
        self.plugindata = PluginDataOper()
        # 处理链
        self.chain = PluginChian()
        # 系统配置
        self.systemconfig = SystemConfigOper()
        # 系统消息
        self.systemmessage = MessageHelper()
        # 事件管理器
        self.eventmanager = EventManager()

        # 系统版本
        self.app_version = APP_VERSION
        version = self.app_version.split('.')
        # 系统主版本
        self.major_version = int(
            version[0][1:] if not self.app_version[0].isdigit() else self.app_version.split('.')[0])
        # 系统次版本
        self.minor_version = int(version[1])
        # 系统修订版本
        self.revision_version = int(version[2])
        # 特殊版本后缀
        self.revision_version_count = self.app_version.split('-')[1] if '-' in self.app_version else 0

        if not plugin:
            raise Exception("组件实例化错误")
        self.__plugin = plugin

    def get_config(self) -> dict:
        """
        获取组件配置
        """
        get_comp_config = getattr(self.__plugin, "get_comp_config")
        if not get_comp_config:
            raise Exception("插件方法不存在[get_comp_config]")
        comp_config = get_comp_config(comp_key=self.comp_key)
        return comp_config

    def update_config(self, config: dict) -> bool:
        """"
        更新组件配置
        """
        update_comp_config = getattr(self.__plugin, "update_comp_config")
        if not update_comp_config:
            raise Exception("插件方法不存在[update_comp_config]")
        return update_comp_config(comp_key=self.comp_key, comp_config=config)

    def get_config_item(self, config_key: str, use_default: bool = True) -> Any:
        """
        获取组件配置项
        :param config_key: 配置键
        :param use_default: 是否使用缺省值
        :return: 配置值
        """
        if not config_key:
            return None
        config = self.get_config() or {}
        config_default = self.config_default or {}
        config_value = config.get(config_key)
        if config_value is None and use_default:
            config_value = config_default.get(config_key)
        return config_value

    @staticmethod
    def check_stack_contain_method(package_name: str, function_name: str) -> bool:
        """
        判断调用栈是否包含指定的方法
        """
        if not package_name or not function_name:
            return False
        package_path = package_name.replace('.', os.sep)
        for stack in inspect.stack():
            if not stack or not stack.filename:
                continue
            if stack.function != function_name:
                continue
            if stack.filename.endswith(f"{package_path}.py") or stack.filename.endswith(f"{package_path}{os.sep}__init__.py"):
                return True
        return False

    def check_stack_contain_save_config_request(self) -> bool:
        """
        判断调用栈是否包含“插件配置保存”接口
        """
        return self.check_stack_contain_method(package_name='app.api.endpoints.plugin', function_name='set_plugin_config')

    def save_default_config(self):
        """
        （缺省时）保存默认配置到组件配置中
        """
        config_default = self.config_default or {}
        if not config_default:
            return
        config = self.get_config() or {}
        config_copy = config.copy()
        for key, value in config_default.items():
            if not key or key in config_copy.keys():
                continue
            config_copy[key] = value
        if config_copy != config:
            self.update_config(config=config_copy)

    """ 方法模板 """

    @abstractmethod
    def init_comp(self):
        """
        初始化组件
        """
        pass

    @abstractmethod
    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        获取组件的配置表单
        :return: 配置表单, 建议的配置
        """
        pass

    @abstractmethod
    def system_config_key(self):
        """
        数据库key
        """
        pass

    @abstractmethod
    def check_params(self):
        """
        认证活性检测
        """
        pass

    @abstractmethod
    def extra_info(self):
        """
        额外信息获取
        """
        pass

    """ 前端UI预设 """

    @staticmethod
    def __build_notify_enabled_switch_element() -> List[dict]:
        """
        构造定时检测汇报开关元素
        """
        return [{
            'component': 'VSwitch',
            'props': {
                'model': f'notify_enabled',
                'label': f'启用消息通知',
                'hint': '允许汇报操作结果',
                'persistent-hint': True,
            }
        }]

    @staticmethod
    def __build_notify_type_select_element() -> dict:
        """
        构造定时检测汇报类型下拉选择元素
        """
        return {
            'component': 'VSelect',
            'props': {
                'model': 'notify_type',
                'label': '消息汇报类型',
                'hint': '自定义发送的消息类型',
                'persistent-hint': True,
                'active': True,
                'items': [{
                    'title': notify.value,
                    'value': notify.name,
                } for notify in NotificationType if notify],
            }
        }

    @property
    def __build_corn_select_items(self) -> List[dict]:
        """
        构造时间选择选项
        """
        return [
            {'title': '不启用定时检测', 'value': 0},
            {'title': '每 1 小时', 'value': 3600},
            {'title': '每 2 小时', 'value': 7200},
            {'title': '每 3 小时', 'value': 10800},
            {'title': '每 4 小时', 'value': 14400},
            {'title': '每 5 小时', 'value': 18000},
            {'title': '每 6 小时', 'value': 21600},
            {'title': '每 12 小时', 'value': 43200},
            {'title': '每 24 小时', 'value': 86400},
            {'title': '每 2 天', 'value': 172800},
            {'title': '每 3 天', 'value': 259200},
            {'title': '每 4 天', 'value': 345600},
            {'title': '每 5 天', 'value': 432000},
            {'title': '每 6 天', 'value': 518400},
            {'title': '每 7 天', 'value': 604800},
            {'title': '每 15 天', 'value': 1296000},
        ]

    def __build_corn_select_element(self) -> dict:
        """
        构造时间选择器元素
        """
        return {
            'component': 'VCombobox',
            'props': {
                'model': 'corn',
                'label': f'定时检测',
                'hint': '定时检测认证可用性',
                'persistent-hint': True,
                'active': True,
                'placeholder': '不启用定时检测',
                'items': self.__build_corn_select_items,
            }
        }

    @staticmethod
    def __build_cookie_textarea_element(placeholder='') -> dict:
        """
        构造 Params 文本框元素
        """
        return {
            'component': 'VTextarea',
            'props': {
                'model': 'params',
                'label': '当前cookie值（支持自定义）',
                'placeholder': placeholder,
                'hint': '当前使用的认证缓存。清空时保存，将删除已存在的参数值。可手动替换，使用英文分号;分割，当前只支持普通文本格式，不支持json格式',
                'persistent-hint': True,
                'active': True,
                'clearable': True,
                'auto-grow': True,
            }
        }

    def build_notify_type_select_col_element(self, md=4) -> dict:
        """
        构造定时检测汇报类型下拉选择Col元素
        """
        return {
            'component': 'VCol',
            'props': {
                'cols': 12,
                'md': md,
            },
            'content': [self.__build_notify_type_select_element()]
        }

    def build_corn_select_col_element(self, md=4) -> dict:
        """
        构造定时任务下拉选择Col元素
        """
        return {
            'component': 'VCol',
            'props': {
                'cols': 12,
                'md': md,
            },
            'content': [self.__build_corn_select_element()]
        }

    def build_notify_enabled_switch_col_element(self, md=4) -> dict:
        """
        构造定时检测汇报开关col元素
        """
        return {
            'component': 'VCol',
            'props': {
                'cols': 12,
                'md': md,
            },
            'content': self.__build_notify_enabled_switch_element()
        }

    def build_cookie_textarea_col_element(self, md=12, placeholder=None) -> dict:
        """
        构造Cookie文本框Col元素
        """
        return {
            'component': 'VCol',
            'props': {
                'cols': 12,
                'md': md,
            },
            'content': [self.__build_cookie_textarea_element(placeholder=placeholder)]
        }

    def build_base_settings_select_and_switch_row_element(self, md=4) -> dict:
        """
        构建通用基础设置
        """
        return {
            'component': 'VRow',
            'props': {
                'align': 'center'
            },
            'content': [
                self.build_notify_enabled_switch_col_element(md=md),
                self.build_notify_type_select_col_element(md=md),
                self.build_corn_select_col_element(md=md),
            ]
        }

    def build_base_settings_textarea_row_element_with_cookie(self, md=12, placeholder=None) -> dict:
        """
        构建通用基础cookie设置
        """
        return {
            'component': 'VRow',
            'props': {
                'align': 'center'
            },
            'content': [
                self.build_cookie_textarea_col_element(md=md, placeholder=placeholder)
            ]
        }

    @staticmethod
    def build_not_supported_div_row_element() -> dict:
        """
        构建版本不支持提示
        """
        return {
            'component': 'div',
            'props': {
                'class': 'text-center',
                'style': 'white-space: pre-line;',
            },
            'text': f'当前版本暂不支持该网盘！',
        }

    # 详情显示

    @staticmethod
    def __build_total_vcard_elements(cloud_name, data) -> dict:
        """
        构造显示元素
        """
        return {
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
                                    'text': cloud_name + '/ 额外信息 / 更新时间'
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
                                            'text': data if data else '暂无记录'
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                }
            ]
        }

    def build_total_col_element(self, cloud_name, data, md=4) -> dict:
        """
        构造总计行元素
        """
        return {
            'component': 'VCol',
            'props': {
                'cols': 12,
                'md': md,
            },
            'content': [self.__build_total_vcard_elements(cloud_name, data)]
        }

    """ 初始化显示 """

    def query_params(self, comp_name, system_config_key):
        """
        查询params - 用于初始化显示
        """
        try:
            return self.systemconfig.get(system_config_key)
        except Exception as e:
            logger.error(f"【{comp_name}】认证参数查询失败 - {str(e)}")
            return None

    """ 格式转换方法 """

    @staticmethod
    def valid_auth_params_str(auth_params) -> Optional[str]:
        """
        当前认证参数 - 格式转换 - str
        """
        if not auth_params:
            return ""
        elif isinstance(auth_params, dict):
            auth_params_str = ";".join([f"{key}={value}" for key, value in auth_params.items()])
            return auth_params_str
        elif isinstance(auth_params, str):
            return auth_params
        else:
            raise Exception("传入的认证参数格式错误，无法转换")

    def get_params_value(self, comp_name, system_config_key, key):
        """
        获取认证参数值
        """
        params = self.query_params(comp_name=comp_name, system_config_key=system_config_key)
        if not params:
            return "未绑定"
        value = params.get(key) or "无法获取"
        return value
