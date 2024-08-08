import re
from typing import Any, List, Dict, Tuple

from app.db import SessionFactory
from app.db.models.user import User
from app.log import logger
from app.core.security import get_password_hash, verify_password
from app.plugins import _PluginBase


class UserSettingPlus(_PluginBase):
    # 插件名称
    plugin_name = "用户管理拓展功能"
    # 插件描述
    plugin_desc = "支持快速添加新的超级管理员；支持管理用户权限等级、用户名、用户密码、用户状态、用户邮箱。"
    # 插件图标
    plugin_icon = "setting.png"
    # 插件版本
    plugin_version = "1.4"
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

    _original_name = None
    _original_password = None
    _new_name = None
    _new_password = None
    _two_password = None
    _email = None
    _is_superuser = False
    _is_active = True

    def init_plugin(self, config: dict = None):
        logger.info(f"{self.plugin_name} 插件初始化")

        if config:
            self._enabled = config.get("enabled", False)
            self._original_name = config.get("original_name", None)
            self._original_password = config.get("original_password", None)
            self._new_name = config.get("new_name", None)
            self._new_password = config.get("new_password", None)
            self._two_password = config.get("two_password", None)
            self._email = config.get("email", None)
            self._is_superuser = config.get("is_superuser", False)
            self._is_active = config.get("is_active", True)

        if self._enabled:
            self.run()

        self.__default_config()
        self.__update_config()

    def __update_config(self):
        """
        更新配置
        """
        config = {
            "enabled": self._enabled,
            "original_name": self._original_name,
            "email": self._email,
            "original_password": self._original_password,
            "new_name": self._new_name,
            "new_password": self._new_password,
            "two_password": self._two_password,
            "is_superuser": self._is_superuser,
            "is_active": self._is_active,
        }
        self.update_config(config)

    def __default_config(self):
        """
        默认配置
        """
        self._enabled = False
        self._original_name = None
        self._email = None
        self._original_password = None
        self._new_name = None
        self._new_password = None
        self._two_password = None
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
        UserTypeOptions = []

        users = self.__get_users()
        for user in users:
            UserTypeOptions.append({
                 "title": f"{'超级管理员' if user.get('superuser') else '普通用户'} - {user.get('name')} - {'启用' if user.get('active') else '冻结'}",
                 "value": user.get('name'),
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
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'is_superuser',
                                            'label': '用户权限等级',
                                            'placeholder': '未选择用户权限等级',
                                            'hint': '必选；设置或修改用户权限等级',
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
                                    'md': 6,
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'model': 'is_active',
                                            'label': '用户状态控制',
                                            'placeholder': '未选择用户状态',
                                            'hint': '必选；设置是否启用该用户',
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
                                'props': {
                                    'cols': 12,
                                    'md': 6,
                                },
                                'content': [
                                    {
                                        'component': 'VCombobox',
                                        'props': {
                                            'model': 'original_name',
                                            'label': '用户名',
                                            'placeholder': 'admin',
                                            'multiple': False,
                                            'items': UserTypeOptions,
                                            'hint': '必选；登录时使用的用户名，支持手动输入与下拉框快速选择两种方式',
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
                                            'model': 'new_name',
                                            'label': '新的用户名',
                                            'placeholder': 'admin',
                                            'multiple': False,
                                            'items': UserTypeOptions,
                                            'hint': '修改登录时使用的用户名',
                                            'persistent-hint': True,
                                            'clearable': True,
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
                                    'md': 6,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'original_password',
                                            'label': '用户原密码',
                                            'placeholder': 'Password',
                                            'hint': '超级管理员 必选；用户登录时使用的用户密码',
                                            'persistent-hint': True,
                                            'clearable': True,
                                            'active': True,
                                        }
                                    },
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
                                            'model': 'email',
                                            'label': '用户邮箱',
                                            'hint': '创建 新普通用户 必选；用户绑定的用户邮箱',
                                            'placeholder': 'example@example.com',
                                            'persistent-hint': True,
                                            'clearable': True,
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
                                    'md': 6,
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'new_password',
                                            'label': '用户新密码',
                                            'placeholder': 'Password',
                                            'hint': '登录时使用的新的用户密码',
                                            'persistent-hint': True,
                                            'clearable': True,
                                            'active': True,
                                        }
                                    },
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
                                            'model': 'two_password',
                                            'label': '用户新密码-二次确认',
                                            'placeholder': 'Password',
                                            'hint': '再次新的用户密码',
                                            'persistent-hint': True,
                                            'clearable': True,
                                            'active': True,
                                        }
                                    },
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
                                            'type': 'warning',
                                            'variant': 'tonal',
                                            'style': 'white-space: pre-line;',
                                            'text': '使用前，请先阅读下方规则！以下规则，根据MoviePilot官方逻辑进行提取总结。 问题反馈：'
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
                                                        'text': 'ISSUES（点击跳转）'
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
                                    'value': 'other_rules',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '插件须知'
                            },
                            {
                                'component': 'VTab',
                                'props': {
                                    'value': 'user_rules',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '普通用户相关规则'
                            },
                            {
                                'component': 'VTab',
                                'props': {
                                    'value': 'superuser_rules',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '超级管理员相关规则'
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
                                    'value': 'other_rules',
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
                                                'content': [
                                                    {
                                                        'component': 'VAlert',
                                                        'props': {
                                                            'type': 'error',
                                                            'variant': 'tonal',
                                                            'style': 'white-space: pre-line;',
                                                            'text': '1、插件 "创建" 或 "修改" 用户时，不会影响已有 "用户" 的 ”双重认证“、"头像" 等功能；"新用户" 如需设置这部分功能，请在创建后，自行登录设置！\n\n'
                                                                    '2、本插件只提供 "创建" 与 "修改" 功能，如需 "删除" 用户，请到 "设定" 页面进行操作！\n\n'
                                                                    '3、插件不会在日志里打印设置后的用户密码，请保存设置前，自行确定密码准确性！\n\n'
                                                                    '4、"用户名" 支持通过下拉框快速选择 "已有用户"，名称虽显示为 "权限等级-用户名-状态组成"，但后台调用值仍为 "用户名"；手动输入 "用户名" 功能保持不变，请放心使用！\n\n'
                                                                    '5、当启动时设置好的 "SUPERUSER" 变量的 "用户名" 被改名或被删除时，下次重启 MoviePilot 时，系统会重新创建这个用户，建议设置一个同名用户将其冻结，以免 MoviePilot 自动创建，避免可能出现安全风险！'
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
                                    'value': 'user_rules',
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
                                                'content': [
                                                    {
                                                        'component': 'VAlert',
                                                        'props': {
                                                            'type': 'error',
                                                            'variant': 'tonal',
                                                            'style': 'white-space: pre-line;',
                                                            'text':
                                                                    '1、新建 "普通用户" 时，强制需要同时写入 "用户名"、"用户新密码"、"用户新密码-二次确认"、"用户邮箱"，不需要 "用户原密码" 认证。\n（对标MP默认的添加 "普通用户" 的逻辑处理方式）\n\n'
                                                                    '2、新建 "普通用户" 时，没有密码规范，长短不限，但不能为空。\n\n'
                                                                    '3、已有的 "普通用户"，在修改任何配置时，都不需要输入 "用户原密码" 作为身份认证。\n\n'
                                                                    '4、已有的 "普通用户" 升级为 "超级管理员" 时，强制需要重新设置 "用户新密码" 与 "用户新密码-二次确认"，不需要 "用户原密码" 认证。（使 "普通用户" 升级后能匹配 "超级管理员规则 2" ）\n\n'
                                                                    '5、已有的 "普通用户" 升级为 "超级管理员" 时，遵循 "超级管理员" 的密码规范：同时包含字母、数字、特殊字符中的至少两项，且长度大于6位。\n\n'
                                                                    '6、符合上述 2 条件时，当 "用户新密码" "用户新密码-二次确认" "用户邮箱" 为空时，会保留原有的数据配置。\n（配置留空，使用原配置，不进行修改）\n'
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
                                    'value': 'superuser_rules',
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
                                                'content': [
                                                    {
                                                        'component': 'VAlert',
                                                        'props': {
                                                            'type': 'error',
                                                            'variant': 'tonal',
                                                            'style': 'white-space: pre-line;',
                                                            'text': '1、新建 "超级管理员" 时，强制需要同时写入 "用户名"、"用户新密码"、"用户新密码-二次确认"，不需要 "用户原密码" 认证。\n（对标MP默认的添加 "超级管理员" 的逻辑处理方式）\n\n'
                                                                    '2、新建 "超级管理员" 时，密码规范为：同时包含字母、数字、特殊字符中的至少两项，且长度大于6位。\n\n'
                                                                    '3、已有的 "超级管理员"，在修改任何配置时，都强制需要输入 "用户原密码" 作为身份认证。\n\n'
                                                                    '4、已有的 "超级管理员" 降级为 "普通用户" 时，不强制需要重新设置密码，可通过留空 "用户新密码" 与 "用户新密码" 实现保留 "用户原密码"。\n\n'
                                                                    '5、已有的 "超级管理员" 降级为 "普通用户" 时，如果降级前的 "超级管理员" 没有绑定 "用户邮箱"，则需要写入 "用户邮箱" 才能降级。\n（使 "超级管理员" 降级后能匹配 "普通用户规则 1"）\n\n'
                                                                    '6、已有的 "超级管理员" 降级为 "普通用户" 时，如果为最后一个 "超级管理员"，则不允许降级。\n（请至少保留一个及以上的 "超级管理员" ）\n\n'
                                                                    '7、符合上述 2、4、5 条件时，当 "用户新密码" "用户新密码-二次确认" "用户邮箱" 为空时，会保留原有数据配置。\n（身份认证通过后，配置留空，则使用原配置，不进行修改）\n'
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                ]
                            },
                        ]
                    }
                ]
            },
        ], {
            'enabled': False,

            'original_name': None,
            'email': None,
            'original_password': None,
            'new_name': None,
            'new_password': None,
            'two_password': None,
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

    # init

    def run(self):
        """
        启动
        """
        try:
            with SessionFactory() as db:
                # 提取用户名
                name = self._get_user_name(self._original_name)
                # 查看用户是否存在
                flag = self.__check_user_exists(db=db, name=name)
                # 验证配置并获取字典
                user_info = self._get_user_info(db=db, flag=flag, name=name)
                # 创建/更新用户
                self.__update_user(db=db, user_info=user_info) if flag else self.__create_user(db=db, user_info=user_info)
                # 打印结果日志
                user_type = "超级管理员" if self._is_superuser else "普通用户"
                flag_type = "更新" if flag else "创建"
                log = (f"用户 【 {name} 】 {flag_type}成功 - "
                       f"当前用户权限 【 {user_type} 】 - "
                       f"当前用户状态 【 {'启用' if self._is_active else '冻结'} 】")
                logger.info(log)
                self.systemmessage.put(log)
                return True
        except Exception as e:
            self.systemmessage.put("处理用户配置失败！")
            logger.error(f"处理用户配置失败 - {e}")
            return False

    # 参数校验

    @staticmethod
    def _get_user_name(value):
        """
        获取用户名
        """
        if isinstance(value, dict) and 'value' in value:
            return value.get('value', None)
        return value

    def _get_user_info(self, db, flag, name):
        """
        校验数据 - 生成用户信息
        """
        try:
            # 校验权限等级
            is_superuser = self.__validate_is_superuser(name=name)
            # 校验用户状态
            is_active = self.__validate_is_active(name=name)
            # 校验新密码
            new_hashed_password = self.__validate_password(db=db, flag=flag, name=name)
            # 校验邮箱
            email = self.__validate_email(db=db, flag=flag, name=name)
            # 校验头像
            avatar = self.__validate_avatar(db=db, flag=flag, name=name)

            user_info = {
                "name": self._new_name if self._new_name else name,
                "hashed_password": new_hashed_password,
                "email": email,
                "is_superuser": is_superuser,
                "is_active": is_active,
                "avatar": avatar,
            }
            return user_info
        except Exception as e:
            raise Exception(e)

    def __check_user_exists(self, db, name):
        """
        检查用户是否存在
        """
        try:
            if not name:
                err = "用户名不能为空，请填写用户名！"
                self.systemmessage.put(err)
                raise ValueError(err)
            user = User.get_by_name(db=db, name=name)
            if user:
                logger.info(f"用户 【 {name} 】 已存在，将更新此用户信息！")
                return True
            logger.info(f"用户 【 {name} 】 不存在，将创建此用户！")
            return False
        except Exception as e:
            raise Exception(f"无法判断当前用户名是否已存在 - {e}")

    def __validate_is_superuser(self, name):
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
            raise Exception(f"用户 【 {name} 】 的权限等级参数校验失败 - {e}")

    def __validate_is_active(self, name):
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
            raise Exception(f"用户 【 {name} 】 的 启用状态 校验失败 - {e}")

    def __validate_password(self, db, flag, name):
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
                if not self._new_password:
                    err = "新建用户密码不能为空，请设置密码"
                    self.systemmessage.put(err)
                    raise ValueError(err)
                # 新建用户密码规范
                else:
                    self.__validate_two_password()
                    # 管理员密码规范
                    if self._is_superuser:
                        pattern = r'^(?![a-zA-Z]+$)(?!\d+$)(?![^\da-zA-Z\s]+$).{6,50}$'
                        if not re.match(pattern, self._new_password):
                            err = "超级管理员用户的密码需要同时包含字母、数字、特殊字符中的至少两项，且长度大于6位"
                            self.systemmessage.put(err)
                            raise ValueError(err)
                        hashed_password = get_password_hash(self._new_password)
                    # 普通用户密码规范
                    else:
                        hashed_password = get_password_hash(self._new_password)

            # 用户存在
            else:
                # 获取当前用户信息
                current_user = User.get_by_name(db=db, name=name)

                # 用户权限等级未发生变化
                if self._is_superuser == (True if current_user.is_superuser == 1 else False):

                    # 管理员用户
                    if self._is_superuser:
                        if self._original_password:
                            if not verify_password(plain_password=self._original_password,
                                                   hashed_password=current_user.hashed_password):
                                err = "原密码错误，请重新输入！"
                                self.systemmessage.put(err)
                                raise Exception(err)
                        else:
                            err = "修改超级管理原用户时，请输入原密码！"
                            self.systemmessage.put(err)
                            raise Exception(err)
                        # 有密码时，判断密码规范
                        if self._new_password:
                            pattern = r'^(?![a-zA-Z]+$)(?!\d+$)(?![^\da-zA-Z\s]+$).{6,50}$'
                            if not re.match(pattern, self._new_password):
                                err = "超级管理员用户的密码需要同时包含字母、数字、特殊字符中的至少两项，且长度大于6位！"
                                self.systemmessage.put(err)
                                raise ValueError(err)
                            hashed_password = get_password_hash(self._new_password)
                        # 无密码时，保持原密码
                        else:
                            hashed_password = current_user.hashed_password

                    # 普通用户
                    else:
                        # 有密码时，直接更新密码；无密码时，保持原密码
                        hashed_password = get_password_hash(self._new_password) if self._new_password else current_user.hashed_password

                # 普通用户升级为管理员用户
                elif (self._is_superuser is True and
                      self._is_superuser != (True if current_user.is_superuser == 1 else False)):
                    self.__validate_two_password()
                    # 有密码时，判断密码规范
                    if self._new_password:
                        pattern = r'^(?![a-zA-Z]+$)(?!\d+$)(?![^\da-zA-Z\s]+$).{6,50}$'
                        if not re.match(pattern, self._new_password):
                            err = "超级管理员用户的密码需要同时包含字母、数字、特殊字符中的至少两项，且长度大于6位！"
                            self.systemmessage.put(err)
                            raise ValueError(err)
                        hashed_password = get_password_hash(self._new_password)

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
                        self.__validate_two_password()
                        # 有密码时，更新密码
                        if self._new_password:
                            hashed_password = get_password_hash(self._new_password)
                        # 无密码时，保持原密码
                        else:
                            hashed_password = current_user.hashed_password
                # 权限等级未知错误
                else:
                    err = "权限等级未知错误。"
                    logger.error(f"{err}")
                    raise ValueError(err)
            return hashed_password

        except Exception as e:
            raise Exception(f"用户 【 {name} 】 的用户密码参数校验失败 - {e}")

    def __validate_two_password(self):
        """
        新密码二次认证
        """
        if self._new_password != self._two_password:
            err = "两次输入的密码不一致，请重新输入！"
            self.systemmessage.put(err)
            raise ValueError(err)

    def __validate_email(self, db, flag, name):
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
                current_user = User.get_by_name(db=db, name=name)

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
            raise Exception(f"用户 【 {name} 】 的 邮箱参数 校验失败 - {e}")

    @staticmethod
    def __validate_avatar(db, flag, name):
        """
        校验头像
        """
        try:
            # 用户不存在
            if not flag:
                avatar = "/src/assets/images/avatars/avatar-1.png"
            # 用户存在
            else:
                # 获取当前用户信息
                current_user = User.get_by_name(db=db, name=name)
                avatar = current_user.avatar
            return avatar
        except Exception as e:
            raise Exception(f"用户 【 {name} 】 的 头像路径 校验失败 - {e}")

    # 数据处理

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
