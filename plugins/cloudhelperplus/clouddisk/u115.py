from typing import Tuple, List, Dict, Any, Optional

from packaging.version import Version

from app.log import logger
from app.plugins.cloudhelperplus import CloudDisk


class U115PanHelper(CloudDisk):
    """
    u115网盘
    """
    # 组件key
    comp_key: str = "u115"
    # 组件名称
    comp_name: str = "115网盘"
    # 组件顺序
    comp_order: int = 2
    # 组件最低版本
    comp_min_version: str = "v1.9.7"
    # 组件最高版本
    comp_max_version: Optional[str] = None
    # 组件跳过版本
    comp_skip_version: List[str] = []

    # 配置相关
    # 组件缺省配置
    config_default: Dict[str, Any] = {
        "notify_level": "off",
        "notify_type": "Plugin",
        "corn": 0,
        "params": "",
        "api_notify_enable": False,
        "notify_methods": [],
    }

    helper = None
    systemconfig_key = None
    systemconfig_method = None
    authorization = False

    def init_comp(self):
        """
        初始化组件
        """

        def __check_version():
            """
            检查版本
            """
            msg = None
            if Version(self.app_version) < Version(self.comp_min_version):
                msg = f"组件【{self.comp_name}】需要系统版本【{self.comp_min_version}】以上"
            if self.comp_max_version and Version(self.app_version) > Version(self.comp_max_version):
                msg = f"组件【{self.comp_name}】已经不支持系统版本【{self.app_version}】"
            if self.comp_skip_version and Version(self.app_version) in self.comp_skip_version:
                msg = f"组件【{self.comp_name}】不支持在当前系统版本【{self.app_version}】上使用"
            if msg:
                logger.warning(msg)
                return False
            return True

        def __import_depend():
            """
            导入组件
            """
            try:
                if __check_version():
                    # 检查需要导入哪个版本的组件
                    if Version(self.app_version) < Version("v2.0.0"):
                        from app.db.systemconfig_oper import SystemConfigOper as SystemConfig
                        from app.helper.u115 import U115Helper as Helper
                        from app.schemas.types import SystemConfigKey as SystemConfigKey

                        self.systemconfig_key = SystemConfigKey.User115Params

                    elif Version(self.app_version) >= Version("v2.0.0"):
                        from app.helper.storage import StorageHelper as SystemConfig
                        from app.modules.filemanager.storages.u115 import U115Pan as Helper
                        from app.schemas.types import StorageSchema as SystemConfigKey

                        self.systemconfig_key = SystemConfigKey.U115

                    else:
                        raise Exception(f"不支持的系统版本【{self.app_version}】")

                    self.systemconfig_method = SystemConfig()
                    self.helper = Helper()

                    return True
                else:
                    return False
            except Exception as e:
                logger.warning(f"【{self.comp_name}】 - {str(e)}")
                return False

        self.authorization = __import_depend()

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        获取组件的配置表单
        :return: 配置表单, 建议的配置
        """
        # 默认配置
        default_config = {}
        if self.authorization:
            data = self.query_params(comp_name=self.comp_name,
                                     comp_systemconfig_method=self.systemconfig_method,
                                     comp_systemconfig_key=self.systemconfig_key)
            self.config_default["params"] = self.valid_auth_params_str(auth_params=data)
        # 合并默认配置
        default_config.update(self.config_default)
        # 允许运行
        if self.authorization:
            # 基础设置开关
            base_settings = self.build_base_settings_select_and_switch_row_element()
            # params显示
            base_settings_cookie = self.build_base_settings_textarea_row_element_with_cookie(md=12,
                                                                                             placeholder=self.__cookie_placeholder)
            statement = self.__statement
            elements = [base_settings, base_settings_cookie, statement]
        else:
            elements = [self.build_not_supported_div_row_element()]
        # 处理缺省配置
        self.save_default_config()
        return elements, default_config

    @property
    def __cookie_placeholder(self):
        """
        cookie 输入格式占位符
        """
        placeholder = {
            'text': 'UID=***_**_***;'
                    'CID=***;'
                    'SEID=***'
        }
        return placeholder.get('text')

    @property
    def __statement(self) -> dict:
        """
        使用声明
        """
        return {
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
                                'text': '注意：\n'
                                        '1、使用官方扫码登录时，获取到的cookie为网页端cookie；\n'
                                        '2、当前支持判断与使用13种客户端cookie类型。\n'
                                        '3、主程序存在自动清除功能，会清除过期且无法自动更新的认证参数，如果输入了不可用值，重新打开后没有cookie显示，属于正常情况。',
                            }
                        }
                    ]
                }
            ]
        }

    def check_params(self):
        """
        认证检测方法
        """
        if Version(self.app_version) < Version("v2.0.0"):
            return self.helper.list()
        elif Version(self.app_version) >= Version("v2.0.0"):
            return self.helper.list()
        else:
            raise Exception(f"不支持的系统版本【{self.app_version}】")

    @property
    def __channel_id_map(self):
        """
        115网盘渠道ID
        """
        return {
            'A1': '网页端',
            'D1': '115生活(iOS)',
            'N1': '115管理(iOS)',
            'D3': '115(iOS)',
            'F1': '115生活(安卓端)',
            'M1': '115管理(安卓端)',
            'F3': '115(安卓端)',
            'H1': '115生活(iPad端)',
            'O1': '115管理(iPda端)',
            'H3': '115(iPad端)',
            'I1': '115网盘(安卓电视端)',
            'R1': '115生活(微信小程序)',
            'R2': '115(支付宝小程序)',
        }

    def extra_info(self) -> str:
        """
        获取额外信息方法
        """
        value = self.get_params_value(comp_name=self.comp_name,
                                      comp_systemconfig_method=self.systemconfig_method,
                                      comp_systemconfig_key=self.systemconfig_key,
                                      key='UID')
        if value == "无法获取" or value == "未绑定":
            return value

        channel_id_map = self.__channel_id_map
        channel_id = value.split('_')[1]
        extra_info = channel_id_map.get(channel_id, f'未知渠道【{channel_id}】') if channel_id_map and channel_id else '无'
        return extra_info
