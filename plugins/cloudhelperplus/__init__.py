import threading
from functools import partial
from typing import Any, List, Dict, Tuple

from app import schemas
from app.core.config import settings
from app.log import logger
from app.plugins import _PluginBase

lock = threading.Lock()


class CloudHelperPlus(_PluginBase):
    # 插件名称
    plugin_name = "云盘拓展功能"
    # 插件描述
    plugin_desc = "拓展官方内置支持的云盘的部分功能，功能开放API接口。"
    # 插件图标
    plugin_icon = "Alidrive_A.png"
    # 插件版本
    plugin_version = "1.4"
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

    # 清除认证
    _aliyun_connect_clear_enabled = False
    _u115_connect_clear_enabled = False

    _scheduler = None
    _event = threading.Event()

    def __init__(self):
        """
        初始化
        """
        super().__init__()
        try:
            # 获取主版本号
            from version import APP_VERSION
            version = APP_VERSION
            self.major_version = int(version.split('.')[0][1:])

            # v1.0版本
            if self.major_version == 1:
                from app.helper.aliyun import AliyunHelper as AliyunHelper
                from app.helper.u115 import U115Helper as U115Helper
            # v2.0及以上版本
            elif self.major_version >= 2:
                from app.modules.filemanager.storage.alipan import AliPan as AliyunHelper
                from app.modules.filemanager.storage.u115 import U115Pan as U115Helper
            # 未知版本
            else:
                raise ValueError(f"未知版本号 【{version}】 ，无法判断")

            # 导入依赖
            self.__AliyunHelper = AliyunHelper
            self.__U115Helper = U115Helper

        except Exception as e:
            # 初始化失败
            self.systemmessage.put(f"初始化【{self.plugin_name}】插件失败，插件无法正常使用，请检查日志查看原因！")
            self._build_log(False, f"无法初始化 【{self.plugin_name}】 插件 - {e}")
            raise Exception(f"无法初始化【{self.plugin_name}】插件 - {e}")

    def init_plugin(self, config: dict = None):
        """
        插件初始化
        """
        logger.info(f"【{self.plugin_name}】 插件 初始化")

        if config:
            self._aliyun_connect_clear_enabled = config.get("aliyun_connect_clear_enabled", False)
            self._u115_connect_clear_enabled = config.get("u115_connect_clear_enabled", False)

        self._cloud_connect_clear()

    def __update_config(self):
        """
        更新配置
        """
        config = {
            "aliyun_connect_clear_enabled": self._aliyun_connect_clear_enabled,
            "u115_connect_clear_enabled": self._u115_connect_clear_enabled,
        }
        self.update_config(config)

    def get_state(self) -> bool:
        return True

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

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
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
                                    'md': 3,
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'aliyun_connect_clear_enabled',
                                            'label': '清除阿里云盘认证缓存',
                                            'hint': '清除阿里云盘认证缓存，主动断开连接',
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
                                            'model': 'u115_connect_clear_enabled',
                                            'label': '清除115网盘认证缓存',
                                            'hint': '清除115网盘认证缓存，主动断开连接',
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
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'warning',
                                            'variant': 'tonal',
                                            'text': '注意：阿里云盘有设备认证上限限制，清除认证不会清除上限，记得自行去除过期的设备记录!'
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
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'info',
                                            'variant': 'tonal',
                                            'style': 'white-space: pre-line;',
                                            'text': '清除认证缓存后，请刷新网页，再选择指定网盘；浏览器有显示缓存，不刷新网页时，会导致无法重新刷新二维码。\n'
                                                    '需要使用API接口功能，请在安装插件后，重启MoviePilot项目；未重启时，无法注册API接口服务。'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                ]
            }
        ], {
            'aliyun_connect_clear_enabled': False,
            'u115_connect_clear_enabled': False,
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
                    self._scheduler.shutdown()
                    self._event.clear()
                self._scheduler = None
        except Exception as e:
            print(str(e))

    def get_api(self) -> List[Dict[str, Any]]:
        """
        开放 Api 接口
        """
        api = []

        cloud_services = self.get_cloud_services()
        for key, (attr, helper, method, cloud_name) in cloud_services.items():
            endpoint = partial(self._api_connect_clear, helper, method, cloud_name, True, apikey=None)

            api.append({
                "path": f"/{key}/clear",
                "endpoint": endpoint,
                "methods": ["DELETE"],
                "summary": f"清除{cloud_name}认证缓存",
                "description": f"清除{cloud_name}认证缓存，主动断开连接\n",
            })

        return api

    def get_cloud_services(self):
        """
        支持的网盘 - 适配后期快速增加
        """
        # 增加新网盘，添加此项配置
        if str(self.major_version) == '2':
            cloud_services = {
                'aliyun': ("_aliyun_connect_clear_enabled", self.__AliyunHelper(), "_AliyunHelper__clear_params", "阿里云盘"),
                'u115': ("_u115_connect_clear_enabled", self.__U115Helper(), "_U115Helper__clear_credential", "115网盘"),
            }
        elif str(self.major_version) == '1':
            cloud_services = {
                'aliyun': ("_aliyun_connect_clear_enabled", self.__AliyunHelper(), "_AliyunHelper__clear_params", "阿里云盘"),
                'u115': ("_u115_connect_clear_enabled", self.__U115Helper(), "_U115Helper__clear_credential", "115网盘"),
            }
        else:
            raise Exception(f"未知版本号，判断失败 { f'- 【{self.major_version}】' if {self.major_version} else ''}")
        return cloud_services

    def _cloud_connect_clear(self, api_mode: bool = False):
        """
        开始清除
        """
        with lock:
            try:
                cloud_services = self.get_cloud_services()
            except Exception as e:
                self._build_log(False, f"获取云盘服务失败 - {e}")
                return

            for key, (attr, helper, method, cloud_name) in cloud_services.items():
                if getattr(self, attr, False):
                    success, message = self.__connect_clear(helper, method, cloud_name, api_mode)
                    self._build_log(success, message)
                    # 关闭开关
                    setattr(self, attr, False)
                    self.__update_config()

    def _api_connect_clear(self, helper, method_name, cloud_name, api_mode: bool, apikey: str):
        """
        清除认证缓存 - API调用
        """
        if apikey != settings.API_TOKEN:
            return schemas.Response(success=False, message="API密钥错误")
        return self.__connect_clear(helper, method_name, cloud_name, api_mode)

    @staticmethod
    def __connect_clear(helper, method_name, cloud_name, api_mode: bool = False):
        """
        清除认证缓存方法 - 通用
        """
        if api_mode:
            mode_type = "API调用汇报 - "
        else:
            mode_type = ''
        try:
            # 规避私有方法警告
            connect_clear = getattr(helper, method_name)
            connect_clear()
            message = f"{mode_type}{cloud_name}认证缓存清除成功"
            success = True
        except Exception as e:
            success = False
            message = f"{mode_type}{cloud_name}认证缓存清除失败 - {e}"

        return success, message

    @staticmethod
    def _build_log(success, message):
        """
        统一处理结果信息
        """
        if success:
            logger.info(message)
        else:
            logger.error(message)
