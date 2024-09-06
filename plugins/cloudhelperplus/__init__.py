import ast
import copy
import inspect
import json
import os
from datetime import datetime
from functools import partial
from typing import OrderedDict, Dict, Any, List, Tuple, Optional, Type, Union
from collections import OrderedDict as collections_OrderedDict


from app import schemas
from app.core.config import settings
from app.helper.module import ModuleHelper
from app.log import logger
from app.plugins import _PluginBase

from app.plugins.cloudhelperplus.clouddisk import CloudDisk
from app.schemas import NotificationType


class CloudHelperPlus(_PluginBase):
    # 插件名称
    plugin_name = "云盘拓展功能"
    # 插件描述
    plugin_desc = "拓展官方内置支持的云盘的部分功能，功能开放API接口。"
    # 插件图标
    plugin_icon = "Alidrive_A.png"
    # 插件版本
    plugin_version = "2.2"
    # 插件作者
    plugin_author = "Aqr-K"
    # 作者主页
    author_url = "https://github.com/Aqr-K"
    # 插件配置项ID前缀
    plugin_config_prefix = "cloudhelperplus_"
    # 加载顺序
    plugin_order = 11
    # 可使用的用户级别
    auth_level = 2

    # 注册组件
    __module_path = "app.plugins.cloudhelperplus.clouddisk"
    # 注册组件对象
    __comp_objs: OrderedDict[str, CloudDisk] = collections_OrderedDict()

    # 配置相关
    __config_default: Dict[str, Any] = {
        "enable": False,
        "component_size": "off",
        "dashboard_type": [],
    }
    # 用户提交配置
    __config: Dict[str, Any] = {}

    # 版本支持的云盘
    __allow_cloud: dict = {}

    def init_plugin(self, config: dict = None):
        """
        生效配置信息
        :param config: 配置信息字典
        """
        # 加载插件配置
        self.__config = config
        # 修正配置
        config = self.__fix_config(config=config)
        # 重新加载插件配置
        self.__config = config
        # 注册组件
        self.__register_comp()
        # 当通过页面操作保存配置时
        if self.__check_stack_contain_save_config_request():
            logger.info(f"通过前端执行保存")
            self.__apply_params_config(config=self.__config)
            # 重新保存配置
            self.__fix_config(config=config, mode=True)

    def get_state(self) -> bool:
        """
        获取插件运行状态
        """
        return True if self.__get_config_item("enable") else False

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        """
        注册插件远程命令
        [{
            "cmd": "/xx",
            "event": EventType.xx,
            "desc": "名称",
            "category": "分类，需要注册到Wechat时必须有分类",
            "data": {}
        }]
        """
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        """
        注册插件API
        [{
            "path": "/xx",
            "endpoint": self.xxx,
            "methods": ["GET", "POST"],
            "summary": "API名称",
            "description": "API说明"
        }]
        """
        if not self.__comp_objs or not self.__allow_cloud:
            self.__register_comp()
        query = partial(self.api_auth_get, "query_params", )
        update = partial(self.api_auth_post, "update_params", )
        delete = partial(self.api_auth_get, "delete_params", )
        check = partial(self.api_auth_get, "check_params", )
        extra = partial(self.api_auth_get, "extra_info", )

        text = []
        for comp_key in self.__allow_cloud:
            text.append(comp_key)

        if text:
            text = '支持的云盘id:' + ', '.join(text)
        else:
            text = '当前没有支持的云盘'

        apis = [
            {
                "path": "/query",
                "endpoint": query,
                "methods": ["GET"],
                "summary": f"{self.plugin_name} - 查询认证参数",
                "description": f"查询认证参数 - {text}"
            },
            {
                "path": "/update",
                "endpoint": update,
                "methods": ["POST"],
                "summary": f"{self.plugin_name} - 更新认证参数",
                "description": f"更新认证参数，如果params为空则会覆盖清空，等效于删除认证参数 - {text}"
            },
            {
                "path": "/delete",
                "endpoint": delete,
                "methods": ["DELETE"],
                "summary": f"{self.plugin_name} - 删除认证参数",
                "description": f"删除认证参数 - {text}"
            },
            {
                "path": "/check",
                "endpoint": check,
                "methods": ["GET"],
                "summary": f"{self.plugin_name} - 测试认证参数的可用性",
                "description": f"测试认证参数的可用性 - {text}"
            },
            {
                "path": "/extra",
                "endpoint": extra,
                "methods": ["GET"],
                "summary": f"{self.plugin_name} - 获取认证参数的额外信息",
                "description": f"获取认证参数的额外信息 - {text}"
            }
        ]
        return apis

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
        all_services = []
        # 启动定时检测
        if self.__get_config_item("enable"):
            if not self.__comp_objs or not self.__allow_cloud:
                self.__register_comp()

            for comp_key, comp_obj in self.__comp_objs.items():
                if comp_key not in self.__allow_cloud:
                    continue
                comp_name = comp_obj.comp_name
                corn_key = self.__get_key_prefix(comp_key) + "corn"
                corn = self.__get_config_item(config_key=corn_key)
                if isinstance(corn, dict):
                    corn = int(corn.get("value"))
                if corn == 0:
                    logger.info(f"【{comp_name}】未启用定时检测，跳过")
                    continue
                if corn < 0:
                    logger.warning(f"【{comp_name}】定时检测时间设置错误，跳过")
                    continue
                check_params = partial(self.get_comp_obj_to_method, method="check_params", comp_key=comp_key)
                all_services.append({
                    "id": f"CloudHelperPlus_{comp_name.capitalize()}",
                    "name": f"【{comp_name}】认证可用性检查",
                    "trigger": "interval",
                    "func": check_params,
                    "kwargs": {"seconds": corn}
                })

        return all_services

    def get_dashboard(self, key: str, **kwargs) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
        """
        获取仪表盘数据
        """
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        插件配置页面使用Vuetify组件拼装，参考：https://vuetifyjs.com/
        """
        config_default = {}
        # 合并默认配置
        config_default.update(self.__config_default)

        # 合并各个模块的默认配置
        for _, comp_obj in self.__comp_objs.items():
            comp_form_data = self.__get_comp_form_data(comp_obj=comp_obj)
            if comp_form_data:
                config_default.update(comp_form_data)
        # 头部全局元素
        header_elements = [
            {
                'component': 'VRow',
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
                                    'model': 'enable',
                                    'label': '启用插件',
                                    'hint': '激活定时功能，允许检查云盘状态',
                                    'persistent-hint': True,
                                }
                            }
                        ]
                    },
                    # {
                    #     'component': 'VCol',
                    #     'props': {
                    #         'cols': 12,
                    #         'md': 4
                    #     },
                    #     'content': [
                    #         {
                    #             'component': 'VSelect',
                    #             'props': {
                    #                 'model': 'component_size',
                    #                 'label': '仪表台组件',
                    #                 'items': [
                    #                     {"title": "不启用", "value": "off"},
                    #                     {"title": "迷你", "value": "mini"},
                    #                     {"title": "小型", "value": "small"},
                    #                     {"title": "中型", "value": "medium"},
                    #                     {"title": "大型", "value": "large"}
                    #                 ]
                    #             }
                    #         }
                    #     ]
                    # },
                    {
                        'component': 'VCol',
                        'props': {
                            'cols': 12,
                            'md': 4
                        },
                        'content': [
                            {
                                'component': 'VAlert',
                                'props': {
                                    'type': 'warning',
                                    'variant': 'tonal',
                                    'style': 'white-space: pre-line;',
                                    'text': '问题反馈：',
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
                                                'text': 'ISSUES(点击跳转)'
                                            }
                                        ]
                                    }
                                ]
                            },
                        ]
                    }
                ]
            }]
        # 版本动态仪表台元素
        # dashboard_elements = [self.__build_comp_form_dashboard_element()]
        # 组件的元素
        comp_elements = [self.__build_comp_form_element()]
        # 合并全部元素
        elements = [
            {
                'component': 'VForm',
                # 'content': header_elements + dashboard_elements + comp_elements
                'content': header_elements + comp_elements
            }
        ]

        return elements, config_default

    def get_page(self) -> List[dict]:
        return [
            {
                'component': 'VRow',
                'props': {
                    'style': {
                        'overflow': 'hidden',
                    }
                },
                'content':
                    self.__get_total_elements()
            }
        ]

    def stop_service(self):
        """
        停止插件服务
        """
        try:
            logger.info('尝试停止插件服务...')
            self.__gc()
            logger.info('插件服务停止完成')
        except Exception as e:
            logger.error(f"插件服务停止异常: {str(e)}", exc_info=True)

    def __gc(self):
        """
        回收内存
        """
        try:
            logger.info('尝试回收内存...')
            if self.__comp_objs:
                self.__allow_cloud.clear()
                self.__comp_objs.clear()
            logger.info('回收内存成功')
        except Exception as e:
            logger.error(f"回收内存异常 - {str(e)}", exc_info=True)

    """ 变量缓存 """

    def __fix_config(self, config: dict, mode=False) -> Optional[dict]:
        """
        修正配置
        """
        if not config:
            return None
        # 忽略主程序在reset时赋予的内容
        reset_config = {
            "enabled": False,
            "enable": False,
        }
        if config == reset_config:
            return None
        config_copy = copy.deepcopy(config)
        if mode:
            # 修正配置
            if not self.__comp_objs or not self.__allow_cloud:
                self.__register_comp()
            # 修正配置，去除组件的params
            for comp_key, comp_obj in self.__comp_objs.items():
                if comp_key not in self.__allow_cloud:
                    continue
                key = self.__get_key_prefix(comp_key) + "params"
                # 替换成数据库缓存
                _, _, params = self.query_params(comp_obj=comp_obj)
                if params:
                    params = self.__valid_auth_params_str(value=params)
                config_copy[key] = params
        # 保存更新
        if config != config_copy:
            self.update_config(config=config_copy)
        return config_copy

    def __get_config_item(self, config_key: str, use_default: bool = True) -> Any:
        """
        获取插件配置项
        :param config_key: 配置键
        :param use_default: 是否使用缺省值
        :return: 配置值
        """
        if not config_key:
            return None
        config = self.__config or {}
        config_default = self.__config_default or {}
        config_value = config.get(config_key)
        if config_value is None and use_default:
            config_value = config_default.get(config_key)
        return config_value

    def get_comp_config(self, comp_key: str) -> Dict[str, Any]:
        """
        获取组件配置
        """
        comp_config = {}
        if not comp_key:
            return comp_config
        if not self.__config:
            return comp_config
        for key, value in self.__config.items():
            if not key or not key.startswith(self.__get_key_prefix(comp_key)):
                continue
            comp_config_key = key.removeprefix(self.__get_key_prefix(comp_key))
            comp_config[comp_config_key] = value
        return comp_config

    def update_comp_config(self, comp_key: str, comp_config: dict) -> bool:
        """"
        更新组件配置
        """
        if not comp_key:
            return False
        config = self.__config or {}
        if not config and not comp_config:
            return False
        config = dict(filter(lambda item: item and not item[0].startswith(self.__get_key_prefix(comp_key)), config.items()))
        if comp_config:
            for comp_config_key, value in comp_config.items():
                if not comp_config_key:
                    continue
                key = self.__get_key_prefix(comp_key) + comp_config_key
                config[key] = value
        result = self.update_config(config=config)
        self.__config = config
        return result

    """ 前端输入处理 """

    def __apply_params_config(self, config: dict):
        """
        将每个 comp 的 params 写入对应数据库
        """
        try:
            if not self.__comp_objs:
                logger.warning(f"组件实例缓存不存在，重新创建组件实例缓存")
                # 重新注册组件实例
                self.__register_comp()
            for comp_key, comp_obj in self.__comp_objs.items():
                if comp_key not in self.__allow_cloud:
                    continue
                params = config.get(f'{self.__get_key_prefix(comp_key) + "params"}') or {}
                if params:
                    # 格式转换
                    params = self.__valid_auth_params_dict(value=params)
                status, msg, data = self.get_comp_obj_to_method(comp_key=comp_key, method="update_params", params=params)
                logger.info(msg) if status else logger.error(msg)
        except Exception as e:
            logger.error(f"保存认证参数异常 - {str(e)}", exc_info=True)

    """ 组件注册 """

    @staticmethod
    def __filter_comp_type(comp_type: type) -> bool:
        """
        过滤组件类
        """
        if not comp_type:
            return False
        return issubclass(comp_type, CloudDisk) \
            and comp_type.__name__ != CloudDisk.__name__

    def __register_comp(self):
        """
        注册组件
        """
        # 加载所有组件类
        comp_types: List[Type[CloudDisk]] = \
            ModuleHelper.load(
                package_path=self.__module_path,
                filter_func=lambda _, obj: self.__filter_comp_type(comp_type=obj)
            )
        # 去重
        comp_types = list(set(comp_types))
        # 数量
        comp_count = len(comp_types) if comp_types else 0
        logger.info(f"总共加载到{comp_count}个组件")
        if not comp_types:
            return
        # 组件排序，顺序一样时按照key排序
        comp_types = sorted(comp_types, key=lambda c_type: (c_type.comp_order, c_type.comp_key))
        # 依次实例化并注册
        for comp_type in comp_types:
            # comp_name = comp_type.comp_name
            try:
                comp_key = comp_type.comp_key
                comp_obj = self.__comp_objs.pop(comp_key, None)
                if not comp_obj:
                    # 实例化组件
                    comp_obj = comp_type(plugin=self)
                # 初始化组件
                comp_obj.init_comp()
                # 注册组件
                self.__comp_objs[comp_key] = comp_obj
            except Exception as e:
                logger.error(f"注册组件 - 【{comp_type.__name__}】 - 【{comp_type.comp_name}】 - 异常: {str(e)}",
                             exc_info=True)
            else:
                if comp_obj.authorization:
                    self.__allow_cloud[comp_obj.comp_key] = comp_obj.comp_name
                logger.info(f"注册组件 - 【{comp_type.__name__}】 - 【{comp_type.comp_name}】- 成功")

    """ 封装配置ui """

    @staticmethod
    def __wrapper_comp_form_model(comp_key: str, model: str) -> Optional[str]:
        """
        包装组件表单model
        """
        return None if not comp_key or not model else f"{comp_key}_{model}"

    def __get_comp_form_data(self, comp_obj: CloudDisk) -> Optional[Dict[str, Any]]:
        """
        获取组件的表单数据
        """
        if not comp_obj:
            return None
        form = comp_obj.get_form()
        if not form:
            return None
        _, data = form
        if not data:
            return {}
        result = {}
        comp_key = comp_obj.comp_key
        for key, value in data.items():
            if not key or not value:
                continue
            key = self.__wrapper_comp_form_model(comp_key=comp_key, model=key)
            result[key] = value
        return result

    def __build_comp_form_element(self) -> dict:
        """
        构建组件表单元素
        """
        return \
            {
                'component': 'VRow',
                'content': [{
                    'component': 'VCol',
                    'props': {
                        'cols': 12
                    },
                    'content': [
                        self.__build_comp_form_tabs_element(),
                        self.__build_comp_form_window_element(),
                    ]
                }]
            }

    @staticmethod
    def __build_comp_form_tab_value(key: str) -> str:
        """
        构造组件表单tab的value
        :param key: 组件的key
        """
        return f'_tab_{key}'

    def __build_comp_form_dashboard_items(self) -> List[dict]:
        """
        构建组件表单dashboard选项的元素下拉可选表单
        """
        return \
            [
                {"title": obj.comp_name, "value": key}
                for key, obj in self.__comp_objs.items() if key and obj
            ]

    def __build_comp_form_tabs_element(self) -> dict:
        """
        构建组件表单tabs元素
        """
        return \
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
                'content': [{
                    'component': 'VTab',
                    'props': {
                        'style': {
                            'padding-top': '10px',
                            'padding-bottom': '10px',
                            'font-size': '16px'
                        },
                        'value': self.__build_comp_form_tab_value(key=key)
                    },
                    'text': obj.comp_name
                } for key, obj in self.__comp_objs.items() if key and obj]
            }

    def __build_comp_form_window_element(self) -> dict:
        """
        构建组件表单window元素
        """
        return \
            {
                'component': 'VWindow',
                'props': {
                    'model': '_tabs',
                },
                'content': [{
                    'component': 'VWindowItem',
                    'props': {
                        'style': {
                            'margin-top': '20px',
                        },
                        'value': self.__build_comp_form_tab_value(key=key)
                    },
                    'content': self.__get_comp_form_elements(comp_obj=obj)
                } for key, obj in self.__comp_objs.items() if key and obj]
            }

    def __build_comp_form_dashboard_element(self) -> dict:
        """
        构建头部的仪表台可选元素
        """
        return \
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
                                'component': 'VSelect',
                                'props': {
                                    'model': 'dashboard_type',
                                    'label': '允许仪表台显示的云盘类型',
                                    'items': self.__build_comp_form_dashboard_items(),
                                    'hint': '选择推送使用的消息类型',
                                    'persistent-hint': True,
                                    'active': True,
                                    'clearable': True,
                                    'multiple': True,
                                    'chips': True,
                                }
                            }
                        ]
                    }
                ]
            }

    def __get_comp_form_elements(self, comp_obj: CloudDisk) -> Optional[list]:
        """
        获取组件的配置表单元素
        """
        if not comp_obj:
            return None
        form = comp_obj.get_form()
        if not form:
            return None
        elements, _ = form
        comp_key = comp_obj.comp_key
        self.__wrapper_comp_form_elements(comp_key=comp_key, comp_elements=elements)
        return elements

    def __wrapper_comp_form_elements(self, comp_key: str, comp_elements: List[dict]):
        """
        修改组件表单元素
        """
        if not comp_key or not comp_elements:
            return
        for comp_element in comp_elements:
            if not comp_element:
                continue
            # 处理自身
            props = comp_element.get("props")
            if props:
                model = props.get("model")
                if model:
                    props["model"] = self.__wrapper_comp_form_model(comp_key=comp_key, model=model)
            # 递归处理下级
            content = comp_element.get("content")
            if content:
                self.__wrapper_comp_form_elements(comp_key=comp_key, comp_elements=content)

    """ 封装统计UI """

    def __save_page_data(self, comp_obj):
        """
        保存页面数据
        """
        query_params_status, _, query_params_data = self.query_params(comp_obj=comp_obj)
        # 初始化
        status, extra_info = None, None
        # 查询失败
        if not query_params_status:
            status, extra_info = None, False
        # 查询成功
        else:
            # 认证存在
            if query_params_data:
                # 活性检测
                check_params_status, msg, _ = self.check_params(comp_obj=comp_obj)
                # 可以检测有效性
                if check_params_status:
                    status = True if msg.endswith('有效') else False
                # 无法检测有效性
                else:
                    status, extra_info = None, False

                if extra_info is not False:
                    # 额外参数提取
                    extra_info_status, _, extra_info_data = self.extra_info(comp_obj=comp_obj)
                    # 可以提取
                    if extra_info_status:
                        extra_info = extra_info_data
                    else:
                        extra_info = "无法获取"

        try:
            info = self.get_data(f"{comp_obj.comp_key}_status") or {
                f'{comp_obj.comp_key}_status': '暂无记录',
                f'{comp_obj.comp_key}_extra_info': '暂无记录',
                f'{comp_obj.comp_key}_update_time': '暂无记录',
            }
            time = datetime.now().strftime('%m-%d %H:%M:%S')
            info.update({
                f'{comp_obj.comp_key}_status': status,
                f'{comp_obj.comp_key}_extra_info': extra_info if extra_info else '无',
                f'{comp_obj.comp_key}_update_time': time,
            })
            self.save_data(f"{comp_obj.comp_key}_info", info)
            logger.info(f"【{comp_obj.comp_name}】状态记录更新成功")
        except Exception as e:
            logger.error(f"【{comp_obj.comp_name}】状态记录失败 - {e}", exc_info=True)

    def __get_total_elements(self):
        """
        组装汇总元素
        """
        page_info = []
        if not self.__comp_objs or not self.__allow_cloud:
            self.__register_comp()
        if self.__comp_objs:
            for comp_key in self.__comp_objs:
                comp_obj = self.__comp_objs.get(comp_key, None)
                if comp_obj.comp_key not in self.__allow_cloud:
                    continue
                info = self.get_data(f'{comp_obj.comp_key}_info')
                if not info:
                    cloud_type = '暂无记录'
                else:
                    # 提取
                    cloud_status = info.get(f'{comp_obj.comp_key}_status', None)
                    cloud_extra_info = info.get(f'{comp_obj.comp_key}_extra_info', None)
                    cloud_update_time = info.get(f'{comp_obj.comp_key}_update_time', None)

                    if cloud_extra_info is False:
                        cloud_type = f'状态检查失败 / 无 / {cloud_update_time}'
                    else:
                        if cloud_status:
                            cloud_status_type = '有效'
                        elif cloud_status is False:
                            cloud_status_type = '已失效'
                        else:
                            cloud_status_type = '未绑定'

                        cloud_type = f'{cloud_status_type} / {cloud_extra_info} / {cloud_update_time}'

                header = f'{comp_obj.comp_name} 状态 / 额外信息 / 更新时间'

                # 组装
                page_info.append({
                    'component': 'VCol',
                    'props': {
                        'cols': 12,
                        'md': 4,
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
                                                    'text': header
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
                                                            'text': cloud_type
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
                )

        if not page_info:
            page_info = [
                {
                    'component': 'div',
                    'text': '暂无数据',
                    'props': {
                        'class': 'text-center',
                    }
                }
            ]
        return page_info

    """ API调用认证 """

    def api_auth_get(self, method: str, apikey: str, cloud_id: str):
        """
        API 认证 - GET
        """
        if apikey != settings.API_TOKEN:
            return schemas.Response(success=False, message="API密钥错误")
        return self.api_method(cloud_id=cloud_id, method=method)

    def api_auth_post(self, method: str, apikey: str, cloud_id: str, params: Union[list, dict, bool, int, str] = None):
        """
        API 认证 - POST
        """
        if apikey != settings.API_TOKEN:
            return schemas.Response(success=False, message="API密钥错误")
        return self.api_method(cloud_id=cloud_id, method=method, params=params)

    def api_method(self, cloud_id, method, params: Union[list, dict, bool, int, str] = None):
        """
        API调用
        :param cloud_id: 云盘
        :param method: 调用方法
        :param params: 认证参数
        """
        # 非更新，清除无用的认证参数
        if method != 'update_params':
            params = None
        status, message, data = self.get_comp_obj_to_method(comp_key=cloud_id, method=method, params=params)
        if isinstance(status, int):
            status = True if status >= 0 else False
        if data and isinstance(data, str):
            data = [f"{data}"]
        return schemas.Response(success=status, message=message, data=data)

    """ 数据处理 """

    def get_comp_obj_to_method(self, comp_key, method, params: Union[list, dict, bool, int, str] = None):
        """
        指定组件实例化对象与调用
        """
        try:
            # 查找组件实例
            if not self.__comp_objs:
                logger.warning(f"组件实例缓存不存在，重新创建组件实例缓存")
                # 重新注册组件实例
                self.__register_comp()

            comp_obj = self.__comp_objs.get(comp_key, None)
            if not comp_obj:
                return False, f"【{comp_key}】组件实例不存在", None

            if comp_key not in self.__allow_cloud:
                return False, f"当前插件不支持使用【{comp_key}】", None

            target_method = getattr(self, method)
            status, msg, data = target_method(comp_obj=comp_obj,
                                              params=params) if method == 'update_params' else target_method(comp_obj=comp_obj)

        except Exception as e:
            logger.error(f"调用组件方法异常 - {str(e)}", exc_info=True)
            return False, f"调用组件方法异常 - {str(e)}", None

        else:
            # 成功更新调用一次检查
            if method == 'update_params':
                self.__save_page_data(comp_obj=comp_obj)

            # 消息推送
            config = self.__config or {}
            if config:
                notify_enabled = self.__get_key_prefix(comp_key) + "notify_enabled"
                notify_type = self.__get_key_prefix(comp_key) + "notify_type"
                # 提取配置
                notify_enabled = config.get(notify_enabled)
                notify_type = config.get(notify_type)
                # 推送
                if notify_enabled and msg:
                    self.post_message(mtype=getattr(NotificationType, notify_type, NotificationType.Plugin.value),
                                      title=f"{self.plugin_name} - {comp_obj.comp_name if comp_obj.comp_name else comp_key}",
                                      text=msg)
            return status, msg, data

    def query_params(self, comp_obj) -> Tuple[bool, str, Optional[dict]]:
        """
        查询params
        """
        try:
            data = self.systemconfig.get(key=comp_obj.system_config_key)
            return True, f"【{comp_obj.comp_name}】认证参数查询成功", data if data else ''
        except Exception as e:
            logger.error(f"【{comp_obj.comp_name}】认证参数查询失败 - {str(e)}")
            return False, f"【{comp_obj.comp_name}】认证参数查询失败", None

    def update_params(self, comp_obj, params) -> Tuple[bool, str, Optional[dict]]:
        """
        更新params
        """
        if not isinstance(params, Optional[dict]):
            return False, f"【{comp_obj.comp_name}】认证参数更新失败，不是合法值", None
        try:
            self.systemconfig.set(key=comp_obj.system_config_key, value=params)
            return True, f"【{comp_obj.comp_name}】认证参数更新成功", None
        except Exception as e:
            logger.error(f"【{comp_obj.comp_name}】认证参数更新失败 - {str(e)}", exc_info=True)
            return False, f"【{comp_obj.comp_name}】认证参数更新失败", None

    def delete_params(self, comp_obj) -> Tuple[bool, str, Optional[dict]]:
        """
        删除params
        """
        try:
            status = self.systemconfig.delete(key=comp_obj.system_config_key)
            msg = f"【{comp_obj.comp_name}】认证参数删除成功" if status else f"【{comp_obj.comp_name}】认证参数删除失败"
            return True if status else False, msg, None
        except Exception as e:
            logger.error(f"【{comp_obj.comp_name}】认证参数删除失败 - {str(e)}", exc_info=True)
            return False, f"【{comp_obj.comp_name}】认证参数删除失败", None

    @staticmethod
    def __is_pass_function(func) -> bool:
        """
        检测给定的类或实例中的某个方法是否为 pass 语句。
        """
        try:
            # 检查func方法是否存在
            if not callable(func):
                return False
            # 检查func方法是否为pass
            source_code = inspect.getsource(func)
            source_code = source_code.strip()
            tree = ast.parse(source_code)
            function_def = tree.body[0]
            # 忽略非方法的func
            if not isinstance(function_def, ast.FunctionDef):
                return False
            # 忽略文档字符串
            body = [node for node in function_def.body if not isinstance(node, ast.Expr)]
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                return False
            # 非pass
            return True
        except Exception as e:
            logger.warning(f"无法解析方法是否存在，默认方法不存在 - {str(e)}", exc_info=True)
            return False

    def check_params(self, comp_obj) -> Tuple[bool, str, Optional[dict]]:
        """
        检查params是否有效
        """
        try:
            if not self.__is_pass_function(func=comp_obj.check_params):
                return False, f"【{comp_obj.comp_name}】没有检测方法，无法检测", None
            if comp_obj.check_params():
                logger.info(f"【{comp_obj.comp_name}】认证参数检查成功 - 认证有效")
                return True, f"【{comp_obj.comp_name}】认证参数检查成功 - 认证有效", None
            else:
                logger.warning(f"【{comp_obj.comp_name}】认证参数检查成功 - 认证失效")
                return True, f"【{comp_obj.comp_name}】认证参数检查成功 - 认证失效", None
        except Exception as e:
            logger.error(f"【{comp_obj.comp_name}】认证检测方法调用失败 - {str(e)}", exc_info=True)
            return False, f"【{comp_obj.comp_name}】认证检测方法调用失败 - {str(e)}", None

    def extra_info(self, comp_obj) -> Tuple[bool, str, Optional[dict]]:
        """
        额外信息
        """
        try:
            if not self.__is_pass_function(func=comp_obj.extra_info):
                logger.error(f"【{comp_obj.comp_name}】没有额外信息获取方法，无法获取")
                return False, f"【{comp_obj.comp_name}】没有额外信息获取方法，无法获取", None
            extra_info = comp_obj.extra_info()
            return True, f"【{comp_obj.comp_name}】额外信息 - 【{extra_info}】", extra_info
        except Exception as e:
            logger.error(f"获取【{comp_obj.comp_name}】额外信息失败 - {str(e)}", exc_info=True)
            return False, f"获取【{comp_obj.comp_name}】额外信息失败", None

    """ 插件调用栈检测 """

    @classmethod
    def __check_stack_contain_method(cls, package_name: str, function_name: str) -> bool:
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

    @classmethod
    def __check_stack_contain_save_config_request(cls) -> bool:
        """
        判断调用栈是否包含“插件配置保存”接口
        """
        return cls.__check_stack_contain_method('app.api.endpoints.plugin', 'set_plugin_config')

    """ 格式转换方法 """

    @staticmethod
    def __valid_auth_params_str(value) -> Optional[str]:
        """
        当前认证参数 - 格式转换 - str
        """
        if not value:
            return ""
        str_data = ""
        for k, v in value.items():
            str_data += f"{k}={v}; "
        return str_data.strip()

    @staticmethod
    def __valid_auth_params_dict(value) -> Optional[dict]:
        """
        参数格式转换 - dict
        """
        if not value:
            return {}
        value = value.strip()
        if isinstance(value, str):
            pairs = value.split(';')
            data_dict = {}
            for pair in pairs:
                key_value = pair.split('=')
                if len(key_value) == 2:
                    key = key_value[0].strip()
                    value = key_value[1].strip()
                    try:
                        # 尝试将值转换为合适的数据类型（如整数、布尔值等）
                        data_dict[key] = json.loads(value)
                    except json.JSONDecodeError:
                        data_dict[key] = value
            return data_dict
        elif value.startswith('{') and value.endswith('}'):
            return value
        else:
            raise Exception("传入的参数格式错误，无法转换")

    @staticmethod
    def __get_key_prefix(comp_key: str) -> str:
        """
        获取key前缀
        """
        return f"{comp_key}_"
