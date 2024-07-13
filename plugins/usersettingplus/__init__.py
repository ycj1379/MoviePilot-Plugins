import re
from typing import Any, List, Dict, Tuple

from app.db import SessionFactory
from app.db.models.user import User
from app.log import logger
from app.core.security import get_password_hash
from app.plugins import _PluginBase


class UserSettingPlus(_PluginBase):
    # 插件名称
    plugin_name = "用户管理拓展功能"
    # 插件描述
    plugin_desc = "支持快速添加新的超级管理员；支持管理用户权限等级、用户密码、用户状态、用户邮箱。"
    # 插件图标
    plugin_icon = "setting.png"
    # 插件版本
    plugin_version = "1.0"
    # 插件作者
    plugin_author = "Aqr-K"
    # 作者主页
    author_url = "https://github.com/Aqr-K"
    # 插件配置项ID前缀
    plugin_config_prefix = "usersettingplus_"
    # 加载顺序
    plugin_order = 29
    # 可使用的用户级别
    auth_level = 1

    _enabled = False

    _name = None
    _password = None
    _email = None
    _is_superuser = False
    _is_active = True

    def init_plugin(self, config: dict = None):
        logger.info(f"{self.plugin_name} 插件初始化")

        if config:
            self._enabled = config.get("enabled", False)
            self._name = config.get("name", None)
            self._password = config.get("password", None)
            self._email = config.get("email", None)
            self._is_superuser = config.get("is_superuser", False)
            self._is_active = config.get("is_active", True)

        if self._enabled:
            self.run_plugin()

        self.__default_config()
        self.__update_config()

    def __update_config(self):
        """
        更新配置
        """
        config = {
            "enabled": self._enabled,
            "name": self._name,
            "password": self._password,
            "email": self._email,
            "is_superuser": self._is_superuser,
            "is_active": self._is_active,
        }
        self.update_config(config)

    def __default_config(self):
        """
        默认配置
        """
        self._enabled = False
        self._name = None
        self._password = None
        self._email = None
        self._is_superuser = False
        self._is_active = True

    def get_state(self):
        return False

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
                                            'label': '导入本次用户设置',
                                            'hint': '一次性任务；谨慎使用，请确认参数准确性',
                                            'persistent-hint': True,
                                        }
                                    }
                                ]
                            },
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 8,
                                },
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'warning',
                                            'variant': 'tonal',
                                            'style': 'white-space: pre-line;',
                                            'text': '注意：所有参数均为一次性配置，保存后会自行清除，不会进行缓存！'
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
                                    'md': 6,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'name',
                                            'label': '用户名',
                                            'placeholder': 'admin',
                                            'hint': '必选项；登录时使用的用户名',
                                            'persistent-hint': True,
                                            'clearable': True,
                                            'active': True,
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
                                            'model': 'password',
                                            'label': '用户密码',
                                            'placeholder': 'Password',
                                            'hint': '登录时使用的用户密码',
                                            'persistent-hint': True,
                                            'clearable': True,
                                            'active': True,
                                        }
                                    },
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
                                    'md': 4,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'email',
                                            'label': '用户邮箱',
                                            'hint': '用户绑定的用户邮箱',
                                            'placeholder': 'example@example.com',
                                            'persistent-hint': True,
                                            'clearable': True,
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
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'is_superuser',
                                            'label': '用户权限等级',
                                            'placeholder': '未选择用户权限等级',
                                            'hint': '必选项；设置或修改用户权限等级',
                                            'persistent-hint': True,
                                            'active': True,
                                            'items': [
                                                {'title': '普通用户', 'value': False},
                                                {'title': '超级管理员', 'value': True},
                                            ],
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
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'is_active',
                                            'label': '用户状态控制',
                                            'placeholder': '未选择用户状态',
                                            'hint': '必选项；设置是否启用该用户',
                                            'persistent-hint': True,
                                            'active': True,
                                            'items': [
                                                {'title': '启用', 'value': True},
                                                {'title': '冻结', 'value': False},
                                            ],
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
                                'content': [
                                    {
                                        'component': 'VAlert',
                                        'props': {
                                            'type': 'error',
                                            'variant': 'tonal',
                                            'style': 'white-space: pre-line;',
                                            'text': '使用注意事项：\n'
                                                    '1、新建 "普通用户" 时，强制需要同时写入 "用户名"、"用户密码"、"用户邮箱"。（对标MP默认的设置普通用户的方式）\n'
                                                    '2、新建 "超级管理员" 时，强制需要同时写入 "用户名"、"用户密码"。（对标MP默认的设置超级管理员的方式）\n'
                                                    '3、已有用户，从 "超级管理员" 降级为 "普通用户" 或 从 "普通用户" 升级 "超级管理员" 时，均强制需要重新设置密码。（对标MP超级管理员的密码规范）\n'
                                                    '4、已有的 "超级管理员" 降级为 "普通用户" 时，如果降级前的 "超级管理员" 没有绑定邮箱，需要写入邮箱才能降级。(使降级后 "普通用户"，能匹配规则 "1")\n'
                                                    '5、已有用户，在降级为 "普通用户" 时，如果为最后一个 "超级管理员"，则不允许降级。（请至少保留一个及以上的 "超级管理员" ）\n'
                                                    '6、已有的用户，在没有改变权限等级时，如果不输入新密码，将保留原有的密码；如果不输入邮箱，将保留原有邮箱。（简述：权限不变，配置留空，使用原配置）\n'
                                                    '7、当用户密码、用户邮箱等配置项为空时，符合上述 3、4、5 条件的情况下，会保留原有的数据配置。（简述：配置留空，使用原配置）\n'
                                                    '8、插件修改与创建用户时，不会影响已有的用户的 ”双重认证“、"头像" 等功能；新用户如需使用这些功能，请在创建后，自行登录设置！\n'
                                                    '9、插件只提供创建与修改用户功能，如需删除用户，请到 "设定" 页面进行操作！\n'
                                                    '10、插件不会在日志里打印设置后的用户密码，请保存设置前，自行确定密码准确性！\n'
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                ]
            },
        ], {
            'enabled': False,

            'name': None,
            'password': None,
            'email': None,
            'is_superuser': False,
            'is_active': True,
        }

    def get_page(self) -> List[dict]:
        pass

    def stop_service(self):
        """
        退出插件
        """
        pass

    def __check_user_exists(self, db):
        """
        检查用户是否存在

        :param db: 数据库连接
        """
        try:
            if not self._name:
                err = "用户名不能为空，请填写用户名！"
                self.systemmessage.put(err)
                raise ValueError(err)
            user = User.get_by_name(db=db, name=self._name)
            if user:
                logger.info(f"用户 【 {self._name} 】 已存在，将更新此用户信息！")
                return True
            logger.info(f"用户 【 {self._name} 】 不存在，将创建此用户！")
            return False
        except Exception as e:
            raise Exception(f"无法判断当前用户名是否已存在 - {e}")

    def __validate_is_superuser(self):
        """
        校验权限等级
        """
        try:
            if not (self._is_superuser is True or self._is_superuser is False):
                err = "权限等级错误，请选择合法的用户权限等级！"
                self.systemmessage.put(err)
                raise ValueError(err)
            return self._is_superuser
        except Exception as e:
            raise Exception(f"用户 【 {self._name} 】 的权限等级参数校验失败 - {e}")

    def __validate_is_active(self):
        """
        校验用户状态
        """
        try:
            if not (self._is_active is True or self._is_active is False):
                err = "请选择合法的用户状态！"
                self.systemmessage.put(err)
                raise ValueError(err)
            return self._is_active
        except Exception as e:
            raise Exception(f"用户 【 {self._name} 】 的 启用状态 校验失败 - {e}")

    def __validate_password(self, db, flag):
        """
        校验密码

        :param db: 数据库连接
        :param flag: 用户是否存在 , True: 存在, False: 不存在

        用户不存在时，没有输入新密码时，报错；\n
        用户不存在时，如果创建的是管理员账户，有输入新密码时，有密码规范；\n
        用户不存在时，如果创建的是普通用户，有输入新密码时，没有密码规范；\n

        用户存在时，如果权限未发生变化，如果是管理员用户，有输入新密码时，有密码规范；\n
        用户存在时，如果权限未发生变化，如果是管理员用户，没有输入新密码时，保留数据库中的密码；\n
        用户存在时，如果权限未发生变化，如果是普通用户，有输入新密码时，没有密码规范；\n
        用户存在时，如果权限未发生变化，如果是普通用户，没有输入新密码时，保留数据库中的密码；\n

        用户存在时，如果是从普通用户升级为管理员用户，有输入新密码时，有密码规范；\n
        用户存在时，如果是从普通用户升级为管理员用户，没有输入新密码时，报错，提示强制需要重新设置密码；\n

        用户存在时，如果是从管理员降级为普通用户，如果是最后一个管理员用户，不允许降级；\n
        用户存在时，如果是从管理员降级为普通用户，如果不是最后一个管理员用户，有输入新密码时，有密码规范；\n
        用户存在时，如果是从管理员降级为普通用户，如果不是最后一个管理员用户，没有输入新密码时，报错，提示强制需要重新设置密码；\n

        用户存在时，如果权限等级未知错误，报错；\n
        """
        try:
            # 用户不存在
            if not flag:
                # 新建用户密码不能为空
                if not self._password:
                    err = "新建用户密码不能为空，请设置密码"
                    self.systemmessage.put(err)
                    raise ValueError(err)
                # 新建用户密码规范
                else:
                    # 管理员密码规范
                    if self._is_superuser:
                        pattern = r'^(?![a-zA-Z]+$)(?!\d+$)(?![^\da-zA-Z\s]+$).{6,50}$'
                        if not re.match(pattern, self._password):
                            err = "超级管理员用户的密码需要同时包含字母、数字、特殊字符中的至少两项，且长度大于6位"
                            self.systemmessage.put(err)
                            raise ValueError(err)
                        hashed_password = get_password_hash(self._password)
                    # 普通用户密码规范
                    else:
                        hashed_password = get_password_hash(self._password)

            # 用户存在
            else:
                # 获取当前用户信息
                current_user = User.get_by_name(db=db, name=self._name)

                # 用户权限等级未发生变化
                if self._is_superuser == (True if current_user.is_superuser == 1 else False):

                    # 管理员用户
                    if self._is_superuser:
                        # 有密码时，判断密码规范
                        if self._password:
                            pattern = r'^(?![a-zA-Z]+$)(?!\d+$)(?![^\da-zA-Z\s]+$).{6,50}$'
                            if not re.match(pattern, self._password):
                                err = "超级管理员用户的密码需要同时包含字母、数字、特殊字符中的至少两项，且长度大于6位！"
                                self.systemmessage.put(err)
                                raise ValueError(err)
                            hashed_password = get_password_hash(self._password)
                        # 无密码时，保持原密码
                        else:
                            hashed_password = current_user.hashed_password

                    # 普通用户
                    else:
                        # 有密码时，直接更新密码
                        if self._password:
                            hashed_password = get_password_hash(self._password)
                        # 无密码时，保持原密码
                        else:
                            hashed_password = current_user.hashed_password

                # 普通用户升级为管理员用户
                elif (self._is_superuser is True and
                      self._is_superuser != (True if current_user.is_superuser == 1 else False)):

                    # 有密码时，判断密码规范
                    if self._password:
                        pattern = r'^(?![a-zA-Z]+$)(?!\d+$)(?![^\da-zA-Z\s]+$).{6,50}$'
                        if not re.match(pattern, self._password):
                            err = "超级管理员用户的密码需要同时包含字母、数字、特殊字符中的至少两项，且长度大于6位！"
                            self.systemmessage.put(err)
                            raise ValueError(err)
                        hashed_password = get_password_hash(self._password)

                    # 无密码时，报错，提示强制需要重新设置密码
                    else:
                        err = "从普通用户升级为管理员用户时，强制需要重新设置密码！"
                        self.systemmessage.put(f"请填写密码，{err}")
                        raise ValueError(err)

                # 管理员用户降级为普通用户
                elif (self._is_superuser is False and
                      self._is_superuser != (True if current_user.is_superuser == 1 else False)):
                    # 获取所有管理员用户名，并提取每个{}里面的is_superuser字段
                    users = current_user.list(db)
                    superuser_count = 0
                    for user in users:
                        if user.is_superuser == 1:
                            superuser_count += 1

                    # 如果管理员低于一个，则不允许降级
                    if superuser_count <= 1:
                        err = "当前仅有一个管理员用户，不允许此用户降级为普通用户！"
                        logger.error(err)
                        self.systemmessage.put(err)
                        raise ValueError(err)

                    # 如果管理员不止一个，则允许降级
                    else:
                        # 有密码时，更新密码
                        if self._password:
                            hashed_password = get_password_hash(self._password)
                        # 无密码时，保持原密码
                        else:
                            err = "从超级管理员降级为普通用户时，强制需要重新设置密码！"
                            self.systemmessage.put(f"请填写密码，{err}")
                            raise ValueError(err)
                # 权限等级未知错误
                else:
                    err = "权限等级未知错误。"
                    logger.error(f"{err}")
                    raise ValueError(err)
            return hashed_password

        except Exception as e:
            raise Exception(f"用户 【 {self._name} 】 的用户密码参数校验失败 - {e}")

    def __validate_email(self, db, flag):
        """
        校验邮箱

        :param db: 数据库连接
        :param flag: 用户是否存在 , True: 存在, False: 不存在

        用户不存在时，如果创建的是管理员账户，邮箱可以为空；\n
        用户不存在时，如果创建的是普通用户，邮箱不能为空；\n

        户存在时，如果权限未发生变化，如果是普通用户，有输入新邮箱时，更新数据库中的邮箱；\n
        用户存在时，如果权限未发生变化，如果是普通用户，没有输入新邮箱时，保留数据库中的原邮箱；\n
        用户存在时，如果权限未发生变化，如果是管理员用户，有输入新邮箱时，更新数据库中的邮箱；\n
        用户存在时，如果权限未发生变化，如果是管理员用户，没有输入新邮箱时，保留数据库中的原邮箱；\n

        用户存在时，如果是从普通用户升级为管理员用户，没有输入新邮箱时，保留数据库中的原邮箱；\n
        用户存在时，如果是从普通用户升级为管理员用户，有输入新邮箱时，更新数据库中的邮箱；\n

        用户存在时，如果是从管理员降级为普通用户，有输入新邮箱时，更新数据库中的邮箱；\n
        用户存在时，如果是从管理员降级为普通用户，没有输入新邮箱时，数据库中没有邮箱，报错；\n
        用户存在时，如果是从管理员降级为普通用户，没有输入新邮箱时，数据库中有邮箱，保留数据库中的邮箱；\n

        用户存在时，如果权限等级未知错误，报错；\n
        """
        try:
            # 用户不存在
            if not flag:
                # 管理员用户
                if self._is_superuser:
                    email = self._email
                # 普通用户
                else:
                    if not self._email:
                        err = "新建的普通用户的邮箱不能为空，请填写邮箱。"
                        self.systemmessage.put(err)
                        raise ValueError(err)
                    else:
                        email = self._email
            # 用户存在
            else:
                # 获取当前用户信息
                current_user = User.get_by_name(db=db, name=self._name)

                # 用户权限等级未发生变化
                if self._is_superuser == (True if current_user.is_superuser == 1 else False):
                    # 有输入新邮箱时
                    if self._email:
                        email = self._email
                    # 没有输入新邮箱时
                    else:
                        email = current_user.email

                # 普通用户升级为管理员用户
                elif (self._is_superuser is True and
                      self._is_superuser != (True if current_user.is_superuser == 1 else False)):
                    # 有输入新邮箱时
                    if self._email:
                        email = self._email
                    # 没有输入新邮箱时
                    else:
                        email = current_user.email

                # 管理员用户降级为普通用户
                elif (self._is_superuser is False and
                      self._is_superuser != (True if current_user.is_superuser == 1 else False)):
                    # 有输入新邮箱时
                    if self._email:
                        email = self._email
                    # 没有输入新邮箱时
                    else:
                        # 数据库中没有邮箱，报错
                        if not current_user.email:
                            err = f"没有绑定邮箱，无法降级为普通用户，请填写邮箱。"
                            self.systemmessage.put(err)
                            raise ValueError(err)
                        else:
                            email = current_user.email
                # 权限等级未知错误
                else:
                    logger.error(f"权限等级未知错误。")
                    raise ValueError(f"权限等级未知错误。")
            return email
        except Exception as e:
            raise Exception(f"用户 【 {self._name} 】 的 邮箱参数 校验失败 - {e}")

    def __validate_avatar(self, db, flag):
        """
        校验头像

        :param db: 数据库连接
        :param flag: 用户是否存在 , True: 存在, False: 不存在
        """
        try:
            # 用户不存在
            if not flag:
                avatar = "/src/assets/images/avatars/avatar-1.png"
            # 用户存在
            else:
                # 获取当前用户信息
                current_user = User.get_by_name(db=db, name=self._name)
                avatar = current_user.avatar
            return avatar
        except Exception as e:
            raise Exception(f"用户 【 {self._name} 】 的 头像路径 校验失败 - {e}")

    def _get_user_info(self, db, flag):
        """
        校验数据 - 生成用户信息
        """
        try:
            # 校验权限等级
            is_superuser = self.__validate_is_superuser()
            # 校验用户状态
            is_active = self.__validate_is_active()
            # 校验密码
            hashed_password = self.__validate_password(db, flag)
            # 校验邮箱
            email = self.__validate_email(db, flag)
            # 校验头像
            avatar = self.__validate_avatar(db, flag)

            user_info = {
                "name": self._name,
                "hashed_password": hashed_password,
                "email": email,
                "is_superuser": is_superuser,
                "is_active": is_active,
                "avatar": avatar,
            }
            return user_info
        except Exception as e:
            raise Exception(e)

    @staticmethod
    def __create_user(db, user_info: Dict[str, Any] = None):
        """
        新增用户
        """
        try:
            user = User(**user_info)
            user.create(db)
        except Exception as e:
            raise Exception(e)

    @staticmethod
    def __update_user(db, user_info: Dict[str, Any] = None):
        """
        更新用户
        """
        try:
            user = User.get_by_name(db, name=user_info["name"])
            user.update(db, user_info)
        except Exception as e:
            raise Exception(e)

    def run_plugin(self):
        """
        启动
        """
        try:
            with SessionFactory() as db:
                # 查看用户是否存在
                flag = self.__check_user_exists(db=db)
                # 验证配置并获取字典
                user_info = self._get_user_info(db=db, flag=flag)
                # 创建/更新用户
                if flag:
                    self.__update_user(db=db, user_info=user_info)
                else:
                    self.__create_user(db=db, user_info=user_info)
                # 打印结果日志
                if self._is_superuser:
                    superuser_type = "超级管理员"
                else:
                    superuser_type = "普通用户"
                if flag:
                    flag_type = "更新"
                else:
                    flag_type = "创建"
                log = (f"用户 【 {self._name} 】 {flag_type}成功 - "
                       f"当前用户权限 【 {superuser_type} 】 - "
                       f"当前用户状态 【 {'启用' if self._is_active else '冻结'} 】")
                logger.info(log)
                self.systemmessage.put(log)
                return True
        except Exception as e:
            self.systemmessage.put("处理用户配置失败！")
            logger.error(f"处理用户配置失败 - {e}")
            return False
