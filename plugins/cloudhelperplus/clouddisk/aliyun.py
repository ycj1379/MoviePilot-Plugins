from typing import Tuple, List, Dict, Any, Optional

from packaging.version import Version

from app.log import logger
from app.plugins.cloudhelperplus import CloudDisk


class AliyunPanHelper(CloudDisk):
    """
    阿里云盘
    """
    # 组件key
    comp_key: str = "aliyun"
    # 组件名称
    comp_name: str = "阿里云盘"
    # 组件顺序
    comp_order: int = 1
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
                        from app.helper.aliyun import AliyunHelper as Helper
                        from app.schemas.types import SystemConfigKey as SystemConfigKey

                        self.systemconfig_key = SystemConfigKey.UserAliyunParams

                    elif Version(self.app_version) >= Version("v2.0.0"):
                        from app.helper.storage import StorageHelper as SystemConfig
                        from app.modules.filemanager.storages.alipan import AliPan as Helper
                        from app.schemas.types import StorageSchema as SystemConfigKey

                        self.systemconfig_key = SystemConfigKey.Alipan

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
            'text': 'loginResult=***;'
                    'loginSucResultAction=***;'
                    'st=***;'
                    'qrCodeStatus=***;'
                    'loginType=***;'
                    'loginScene=***;'
                    'resultCode=***;'
                    'appEntrance=***;'
                    'smartlock=***;'
                    'processFinished=***;'
                    'tip=***;'
                    'userId=****;'
                    'expiresIn=***;'
                    'nickName=***;'
                    'avatar=***;'
                    'tokenType=***;'
                    'refreshToken=***;'
                    'accessToken=***;'
                    'defaultDriveId=***;'
                    'updateTime=***;'
                    'x_device_id=***;'
                    'resourceDriveId=***;'
                    'backDriveId=***'}
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
                                        '1、每次换绑阿里云盘时，都相当于创建一个新的设备ID；'
                                        '用户账号存在设备上限（一般10个），清除旧的认证参数后，该上限占用不会被自动清除；建议到阿里云盘app中手动清除设备ID认证。\n'
                                        '2、主程序存在自动清除功能，会清除过期且无法自动更新的认证参数，如果输入了不可用值，重新打开后没有cookie显示，属于正常情况。',
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

    def extra_info(self) -> str:
        """
        获取额外信息方法
        """
        value = self.get_params_value(comp_name=self.comp_name,
                                      comp_systemconfig_method=self.systemconfig_method,
                                      comp_systemconfig_key=self.systemconfig_key,
                                      key='nickName')
        if value == "无法获取" or value == "未绑定":
            return value

        extra_info = value if value else "未知用户名"
        return extra_info
