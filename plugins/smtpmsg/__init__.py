import shutil
from typing import Any, List, Dict, Tuple

import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

from app.core.config import settings
from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType


class SmtpMsg(_PluginBase):
    # 插件名称
    plugin_name = "SMTP邮件消息通知"
    # 插件描述
    plugin_desc = "支持使用邮件服务器发送消息通知。"
    # 插件图标
    plugin_icon = "Synomail_A.png"
    # 插件版本
    plugin_version = "2.1"
    # 插件作者
    plugin_author = "Aqr-K"
    # 作者主页
    author_url = "https://github.com/Aqr-K"
    # 插件配置项ID前缀
    plugin_config_prefix = "smtpmsg_"
    # 加载顺序
    plugin_order = 29
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    _test_image = "/public/plugin_icon/Synomail_A.png"
    # 插件开关
    _enabled = False
    # 发送图片开关
    _image_send = False
    # 备用服务器开关
    _secondary = False
    # 发送测试消息
    _test = False
    # 自定义模板
    _custom = False
    # 保存自定义模板
    _save = False
    # 恢复默认模板
    _reset = False

    # 默认模板路径
    default_template = settings.ROOT_PATH / "app" / "plugins" / "smtpmsg" / "template" / "default.html"
    # 自定义模板目录
    custom_template_dir = settings.PLUGIN_DATA_PATH / "smtpmsg" / "template"
    # 自定义模板路径
    custom_template = custom_template_dir / "custom.html"

    # 主服务器-地址/端口/加密方式
    _main_smtp_host = None
    _main_smtp_port = None
    _main_smtp_encryption = None
    # 主服务器-账号/密码
    _main_sender_mail = None
    _main_sender_password = None

    # 备用服务器-地址/端口/加密方式
    _secondary_smtp_host = None
    _secondary_smtp_port = None
    _secondary_smtp_encryption = None
    # 备用服务器-账号/密码
    _secondary_sender_mail = None
    _secondary_sender_password = None

    # 发件人用户名与收件人地址
    _sender_name = None
    _receiver_mail = None

    # 消息类型
    _msgtypes = []
    _content = ""

    def init_plugin(self, config: dict = None):
        """
        初始化插件
        """
        logger.info(f"初始化插件 {self.plugin_name}")

        if config:
            # 插件开关
            self._enabled = config.get("enabled")
            # 发送图片开关
            self._image_send = config.get("image_send")
            # 备用服务器开关
            self._secondary = config.get("secondary")
            # 测试开关
            self._test = config.get("test")
            # 自定义模板
            self._custom = config.get("custom")
            # 保存自定义模板
            self._save = config.get("save")
            # 恢复默认模板
            self._reset = config.get("reset")

            # 主服务器
            self._main_smtp_host = config.get("main_smtp_host")
            self._main_smtp_port = config.get("main_smtp_port")
            self._main_smtp_encryption = config.get("main_smtp_encryption")
            self._main_sender_mail = config.get("main_sender_mail")
            self._main_sender_password = config.get("main_sender_password")

            # 备用服务器
            self._secondary_smtp_host = config.get("secondary_smtp_host")
            self._secondary_smtp_port = config.get("secondary_smtp_port")
            self._secondary_smtp_encryption = config.get("secondary_smtp_encryption")
            self._secondary_sender_mail = config.get("secondary_sender_mail")
            self._secondary_sender_password = config.get("secondary_sender_password")

            # 发件人类型
            self._sender_name = config.get("sender_name")
            self._receiver_mail = config.get("receiver_mail")

            # 消息类型
            self._msgtypes = config.get("msgtypes") or []
            # 自定义模板内容
            self._content = config.get("content") or ""

            # 检查自定义模板是否存在
            self.check_custom_template()

            # 状态判断
            self.__on_config_change(config=config)

    def check_custom_template(self):
        """
        检查自定义模板
        """
        # 自定义模板不存在，创建模板文件
        if not self.custom_template.exists():
            self.custom_template_dir.mkdir(parents=True, exist_ok=True)
            self.custom_template.touch()
            # 如果_content不为空，写入自定义模板
            if self._content:
                self.custom_template.write_text(self._content, encoding="utf-8")
            # 否则，复制默认模板到自定义模板
            else:
                self.default_template.replace(self.custom_template)
            logger.warning(f"自定义邮件模板文件不存在，已创建模板文件！")

        # 自定义模板存在
        elif self.custom_template.exists():
            # 读取自定义模板内容
            # 判断self._content与自定义模板内容是否一致
            if (self._save is not True
                    and self._reset is not True
                    and self._content != self.custom_template.read_text(encoding="utf-8")):
                # 更新配置与显示
                self._content = self.custom_template.read_text(encoding="utf-8")
                self.update_config({"content": self._content})
            else:
                logger.debug(f"自定义邮件模板文件已存在！")

    def __on_config_change(self, config: dict):
        """
        状态判断
        """
        tag = "" if self._enabled else "未开启，"
        # 保存自定义模板
        if self._save is True:
            if self._reset is True:
                config.update({"reset": False})
                # 更新配置
                self.update_config(config)
                logger.warning(f"自定义模板与恢复默认模板不可同时启动，关闭恢复默认模板按钮！")
                self.systemmessage.put(f"{self.plugin_name}自定义模板与恢复默认模板不可同时启动，关闭恢复默认模板按钮！")
            # 写入自定义模板文件
            self.custom_template.write_text(self._content, encoding="utf-8")
            # 保存存自定义模板，更新显示，并关闭开关
            config.update({"save": False, "content": self._content})
            # 更新配置
            self.update_config(config)
            logger.info(f"{self.plugin_name}{tag}自定义邮件模板保存成功！")
            self.systemmessage.put(f"{self.plugin_name}{tag}自定义邮件模板保存成功！")

        # 恢复默认模板
        elif self._save is not True and self._reset is True:
            # 恢复默认模板
            shutil.copy(self.default_template, self.custom_template)
            # 更新显示，关闭恢复默认模板开关
            self._content = self.custom_template.read_text(encoding="utf-8")
            config.update({"reset": False, "content": self._content})
            # 更新配置
            self.update_config(config)
            logger.info(f"{self.plugin_name}{tag}默认邮件模板恢复成功！")
            self.systemmessage.put(f"{self.plugin_name}{tag}默认邮件模板恢复成功！")

        # 启用插件
        if self._enabled:
            # 参数配置不完整，关闭插件
            if (not self._main_smtp_host or
                    not self._main_smtp_port or
                    (self._main_smtp_encryption is None) or
                    not self._main_sender_mail or
                    not self._main_sender_password):
                # 关闭插件
                config.update({"enabled": False, "test": False})
                self.update_config(config)
                logger.warning(f"参数配置不完整，关闭插件")
                self.systemmessage.put(f"{self.plugin_name}参数配置不完整，关闭插件！")

            # 测试邮件
            elif self._test:
                m_success, s_success = self.send_to_smtp(test=True,
                                                         secondary=self._secondary,
                                                         title="",
                                                         text="这是一封测试邮件~~~",
                                                         image=self._test_image,
                                                         _smtp_settings=self._merge_config())

                if m_success:
                    if s_success:
                        message = "所有服务器测试邮件发送成功！"
                        logger.info(f"{message}")
                    else:
                        message = "主服务器测试邮件发送成功！备用服务器测试邮件发送失败！" if s_success is not None else "主服务器测试邮件发送成功！未启动备用服务器！"
                        logger.warning(f"{message}")
                else:
                    if s_success:
                        message = "备用服务器测试邮件发送成功！主服务器测试邮件发送失败！"
                        logger.warning(f"{message}")
                    else:
                        message = "所有服务器测试邮件发送失败！" if s_success is not None else "服务器未启动！无法测试！"
                        logger.error(f"{message}")
                # 关闭测试开关
                config.update({"test": False})
                # 更新配置
                self.update_config(config)
                logger.info(f"{message}")
                self.systemmessage.put(message)

    def get_state(self) -> bool:
        return self._enabled

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        # 编历 NotificationType 枚举，生成消息类型选项
        MsgTypeOptions = []
        for item in NotificationType:
            MsgTypeOptions.append({
                "title": item.value,
                "value": item.name
            })

        encryption_options = ["不加密", "SSL", "TLS"]

        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
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
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            },
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
                                            'model': 'image_send',
                                            'label': '发送图片',
                                        }
                                    }
                                ]
                            },
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
                                            'model': 'secondary',
                                            'label': '启用备用服务器',
                                        }
                                    }
                                ]
                            },
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
                                            'model': 'test',
                                            'label': '发送测试邮件',
                                        }
                                    }
                                ]
                            },
                        ]
                    },
                    {
                        'component': 'VRow',
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
                                            'text': '打开 "启动备用服务器" 后，会在 "服务器" 发送失败时，尝试使用 "备用服务器" 发送消息。'
                                        }
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
                            'style': {
                                'margin-top': '8px',
                                'margin-bottom': '10px',
                            }
                        },
                        'content': [
                            {
                                'component': 'VTab',
                                'props': {
                                    'value': 'main_smtp',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '主SMTP服务器'
                            },
                            {
                                'component': 'VTab',
                                'props': {
                                    'value': 'secondary_smtp',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '备用SMTP服务器'
                            },
                            {
                                'component': 'VTab',
                                'props': {
                                    'value': 'email_setting',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '邮件设置'
                            },
                            {
                                'component': 'VTab',
                                'props': {
                                    'value': 'custom_template',
                                    'style': {
                                        'padding-top': '10px',
                                        'padding-bottom': '10px',
                                        'font-size': '16px'
                                    },
                                },
                                'text': '自定义邮件模板'
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
                                    'value': 'main_smtp',
                                    'style': {
                                        'padding-top': '20px',
                                        'padding-bottom': '20px'
                                    },
                                },
                                'content': [
                                    {
                                        'component': 'VForm',
                                        'content': [
                                            {
                                                'component': 'VRow',
                                                'content': [
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': '12',
                                                            'md': 6
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VTextField',
                                                                'props': {
                                                                    'model': 'main_smtp_host',
                                                                    'label': 'SMTP服务器地址',
                                                                    'placeholder': 'smtp.example.com',
                                                                }
                                                            }
                                                        ]
                                                    },
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': '12',
                                                            'md': 4
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VTextField',
                                                                'props': {
                                                                    'model': 'main_smtp_port',
                                                                    'label': 'SMTP服务器端口',
                                                                    'placeholder': '常见：25、465、587、995……',
                                                                }
                                                            }
                                                        ]
                                                    },
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': '12',
                                                            'md': 2
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VSelect',
                                                                'props': {
                                                                    'model': 'main_smtp_encryption',
                                                                    'label': '加密方式',
                                                                    'items': encryption_options
                                                                }
                                                            }
                                                        ]
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VRow',
                                                'content': [
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': '12',
                                                            'md': 6
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VTextField',
                                                                'props': {
                                                                    'model': 'main_sender_mail',
                                                                    'label': 'SMTP邮箱',
                                                                    'placeholder': 'example@example.com',
                                                                }
                                                            }
                                                        ]
                                                    },
                                                    {
                                                        'component': 'VCol',
                                                        'props': {
                                                            'cols': '12',
                                                            'md': 6
                                                        },
                                                        'content': [
                                                            {
                                                                'component': 'VTextField',
                                                                'props': {
                                                                    'model': 'main_sender_password',
                                                                    'label': 'SMTP邮箱密码/Token',
                                                                    'placeholder': 'Passwd or Token'
                                                                }
                                                            }
                                                        ]
                                                    }
                                                ]
                                            },
                                        ]
                                    }
                                ]
                            },
                            {
                                'component': 'VWindowItem',
                                'props': {
                                    'value': 'secondary_smtp',
                                    'style': {
                                        'padding-top': '20px',
                                        'padding-bottom': '20px'
                                    },
                                },
                                'content': [
                                    {
                                        'component': 'VRow',
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 6
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'secondary_smtp_host',
                                                            'label': '备用SMTP服务器地址',
                                                            'placeholder': 'smtp.example.com',
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
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'secondary_smtp_port',
                                                            'label': '备用SMTP服务器端口',
                                                            'placeholder': '常见：25、465、587、995……',
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
                                                        'component': 'VSelect',
                                                        'props': {
                                                            'model': 'secondary_smtp_encryption',
                                                            'label': '加密方式',
                                                            'items': encryption_options
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VRow',
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 6
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'secondary_sender_mail',
                                                            'label': '备用SMTP邮箱',
                                                            'placeholder': 'example@example.com',
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 6
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'secondary_sender_password',
                                                            'label': '备用SMTP邮箱密码/Token',
                                                            'placeholder': 'Passwd or Token'
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
                                    'value': 'email_setting',
                                    'style': {
                                        'padding-top': '20px',
                                        'padding-bottom': '20px'
                                    },
                                },
                                'content': [
                                    {
                                        'component': 'VRow',
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 6
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'sender_name',
                                                            'label': '发件人用户名',
                                                            'placeholder': '不输入时，默认使用发件人邮箱作为发件人用户名',
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 6
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VTextField',
                                                        'props': {
                                                            'model': 'receiver_mail',
                                                            'label': '收件人邮箱',
                                                            'placeholder': '默认发送至发件人地址，多个邮箱用英文","分割'
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VRow',
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSelect',
                                                        'props': {
                                                            'multiple': True,
                                                            'chips': True,
                                                            'model': 'msgtypes',
                                                            'label': '消息类型',
                                                            'items': MsgTypeOptions
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
                                    'value': 'custom_template',
                                    'style': {
                                        'padding-top': '20px',
                                        'padding-bottom': '20px'
                                    },
                                },
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
                                                            'model': 'custom',
                                                            'label': '启用自定义模板',
                                                        }
                                                    }
                                                ]
                                            },
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                    'md': 9
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VAlert',
                                                        'props': {
                                                            'type': 'warning',
                                                            'variant': 'tonal',
                                                            'text': '开启"写入自定义模板"后，"恢复默认模板"不会生效！配置在写入后才会生效！'
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
                                                    'md': 3,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VSwitch',
                                                        'props': {
                                                            'model': 'save',
                                                            'label': '写入自定义模板',
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
                                                            'model': 'reset',
                                                            'label': '恢复默认模板',
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
                                                        'component': 'VAlert',
                                                        'props': {
                                                            'type': 'info',
                                                            'variant': 'tonal',
                                                            'text': '重置插件不会重置自定义模板配置，请放心使用！'
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VRow',
                                        'content': [
                                            {
                                                'component': 'VCol',
                                                'props': {
                                                    'cols': 12,
                                                },
                                                'content': [
                                                    {
                                                        'component': 'VAceEditor',
                                                        'props': {
                                                            'modelvalue': 'content',
                                                            'lang': 'html',
                                                            'theme': 'monokai',
                                                            'style': 'height: 20rem; font-size: 14px;',
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'VRow',
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
                                                            'text': "自定义配置支持的变量："
                                                                    "类型：{msg_type}、用户ID：{userid}、"
                                                                    "标题：{title}、内容：{text}、图片：cid:image。"
                                                        }
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                ]
                            }
                        ]
                    },
                ]
            }
        ], {
            # 插件开关
            'enabled': False,
            # 发送图片开关
            'image_send': False,
            # 备用服务器开关
            'secondary': False,
            # 测试开关
            'test': False,
            # 自定义模板开关
            'custom': False,
            # 保存自定义模板
            'save': False,
            # 恢复默认模板
            'reset': False,
            # 自定义模板内容
            'content': self.custom_template.read_text(encoding="utf-8"),

            # 消息类型
            'msgtypes': [],

            # 主服务器-地址/端口/加密方式
            'main_smtp_host': "",
            'main_smtp_port': "",
            'main_smtp_encryption': "不加密",
            # 主服务器-账号/密码
            'main_sender_mail': "",
            'main_sender_password': "",

            # 备用服务器-地址/端口/加密方式
            'secondary_smtp_host': "",
            'secondary_smtp_port': "",
            'secondary_smtp_encryption': "不加密",
            # 备用服务器-账号/密码
            'secondary_sender_mail': "",
            'secondary_sender_password': "",

            # 发件人用户名/收件人地址
            'sender_name': "MoviePilot",
            'receiver_mail': ""
        }

    def get_page(self) -> List[dict]:
        pass

    @eventmanager.register(EventType.NoticeMessage)
    def send(self, event: Event):
        """
        消息发送事件
        """
        if not self.get_state():
            return

        if not event.event_data:
            return

        msg_body = event.event_data
        # 渠道
        channel = msg_body.get("channel")
        if channel:
            return
        # 类型
        msg_type: NotificationType = msg_body.get("type")
        # 标题
        title = msg_body.get("title")
        # 文本
        text = msg_body.get("text")
        # 图片
        image = msg_body.get("image")
        # 用户id
        userid = msg_body.get("userid")

        if not title and not text:
            logger.warning("标题和内容不能同时为空")
            return

        if (msg_type and self._msgtypes
                and msg_type.name not in self._msgtypes):
            logger.info(f"消息类型 {msg_type.value} 未开启消息发送")
            return

        self.send_to_smtp(test=self._test,
                          userid=userid,
                          msg_type=str(msg_type),
                          secondary=self._secondary,
                          title=title if title is not None else f"【{self.plugin_name}】",
                          text=text if text is not None else "",
                          image=image if image is not None else "",
                          _smtp_settings=self._merge_config())

    def send_to_smtp(self, _smtp_settings, test, secondary, title, text, image="", userid="", msg_type="",
                     smtp_type="main", message=None, m_success=None, s_success=None):
        """
        发送邮件
        """
        # 获取 SMTP 服务器配置
        smtp_config = _smtp_settings.get(smtp_type)

        if smtp_type == "main":
            log_type = ""
            m_success = False
        elif smtp_type == "secondary":
            log_type = "备用"
            s_success = False
        else:
            logger.error("未知的SMTP服务器类型")
            raise ValueError("未知的SMTP服务器类型")

        test_type = "测试" if test else ""
        logger.info(f"开始使用{log_type}服务器发送{test_type}邮件")

        try:
            host = smtp_config["host"]
            port = smtp_config["port"]
            encryption = smtp_config["encryption"]
            sender_mail = smtp_config["mail"]
            password = smtp_config["password"]
            sender_name = self._sender_name if self._sender_name else sender_mail

            # 连接到 SMTP 服务器
            server = self._connect_to_smtp_server(host=host, port=port, encryption=encryption, log_type=log_type)
            # 登录到 SMTP 服务器
            self._login_to_smtp_server(server=server, sender_mail=sender_mail, password=password, log_type=log_type)
            # 构建邮件正文
            if not message:
                message = self._msg_build(title=title, text=text, image=image, userid=userid, msg_type=msg_type)
            # 测试模式，修改邮件主题
            if test:
                del message['Subject']
                message['Subject'] = Header(f"测试{log_type}服务器配置", "utf-8")
            # 发件人与收件人
            del message['From']
            message['From'] = f'{sender_name} <{sender_mail}>'
            if self._receiver_mail:
                receiver_list = self._receiver_mail.split(",")
            else:
                logger.warning("收件人地址未配置, 使用发件人地址作为收件人地址")
                receiver_list = sender_mail
            # 发送邮件
            if smtp_type == "main":
                m_success = self._send_msg_to_smtp(server=server, message=message, sender_mail=sender_mail,
                                                   receiver_list=receiver_list, log_type=log_type, test_type=test_type)
            elif smtp_type == "secondary":
                s_success = self._send_msg_to_smtp(server=server, message=message, sender_mail=sender_mail,
                                                   receiver_list=receiver_list, log_type=log_type, test_type=test_type)
                # 备用服务器结果
                return s_success

            # 测试模式，如果同步测试备用服务器
            if test and secondary and smtp_type == "main":
                s_success = self.send_to_smtp(test=test, secondary=secondary, message=message, title=title,
                                              text=text, image=image, _smtp_settings=_smtp_settings,
                                              smtp_type="secondary", m_success=m_success)
                return m_success, s_success
            # 非测试模式，主服务器发送成功不使用备用服务器
            elif (not test and m_success) or (test and not secondary):
                return m_success, s_success
            # 非测试模式，主服务器发送失败 or 测试模式，主服务器发送失败，且为开启备用服务器：抛出异常
            elif (not test and not m_success) or (not m_success and not secondary):
                raise ValueError(f"{log_type}服务器发送{test_type}邮件失败")

        except Exception as e:
            logger.warning(f"{log_type}服务器发送{test_type}邮件失败")
            if not test and not secondary and smtp_type == "main":
                logger.error("未启动备用服务器，运行失败，请检查配置")
                logger.debug(e)

            elif secondary and smtp_type == "main":
                s_success = self.send_to_smtp(test=test, secondary=secondary, message=message, title=title,
                                              text=text, image=image, _smtp_settings=_smtp_settings,
                                              smtp_type="secondary")
            elif secondary and smtp_type == "secondary":
                logger.debug(e)
                return s_success
            return m_success, s_success

    def _merge_config(self):
        """
        整合配置参数
        """
        _smtp_settings = {
            "main": {
                "host": self._main_smtp_host,
                "port": self._main_smtp_port,
                "encryption": self._main_smtp_encryption,
                "mail": self._main_sender_mail,
                "password": self._main_sender_password,
            },
            "secondary": {
                "host": self._secondary_smtp_host,
                "port": self._secondary_smtp_port,
                "encryption": self._secondary_smtp_encryption,
                "mail": self._secondary_sender_mail,
                "password": self._secondary_sender_password,
            }
        }

        return _smtp_settings

    @staticmethod
    def _connect_to_smtp_server(host, port, encryption, log_type):
        """
        连接到 SMTP 服务器
        """
        logger.debug(f"开始尝试连接到{log_type} SMTP 服务器")
        try:
            if encryption == "SSL":
                server = smtplib.SMTP_SSL(host, port, timeout=5)
            else:
                server = smtplib.SMTP(host, port, timeout=5)
                if encryption == "TLS":
                    server.starttls()

            server.ehlo(host)
            logger.info(f"{log_type}SMTP服务器连接成功")
            return server

        except smtplib.SMTPConnectError:
            logger.error(f"无法与{log_type}SMTP服务器建立连接")
            raise

    @staticmethod
    def _login_to_smtp_server(server, sender_mail, password, log_type):
        """
        登录到 SMTP 服务器
        """
        logger.debug(f"开始尝试登录到{log_type} SMTP 服务器")
        try:
            server.login(sender_mail, password)
            logger.info(f"{log_type}SMTP服务器登录成功")

        except smtplib.SMTPAuthenticationError:
            logger.error(f"{log_type}SMTP服务器登录失败")
            raise

    def _msg_build(self, title, text, image, userid, msg_type):
        """
        构建邮件正文
        """
        logger.debug("开始构建邮件")
        try:
            message = MIMEMultipart()
            message['Subject'] = Header(title, "utf-8")
            message_alternative = MIMEMultipart('alternative')
            message.attach(message_alternative)
            logger.debug("邮件标题构建成功")

            # 读取模板文件
            try:
                logger.debug("开始读取邮件正文模板文件")
                if not self._custom:
                    logger.debug("使用默认邮件模板")
                    template = self.default_template
                else:
                    logger.debug("使用自定义邮件模板")
                    template = self.custom_template

                with open(template, "r", encoding="utf-8") as template_file:
                    template_content = template_file.read()
                    logger.debug("邮件正文模板文件读取成功，开始构建邮件正文")

                msg_html = template_content.format(text=text, image=image, title=title, userid=userid,
                                                   msg_type=msg_type)

                if self._image_send and image:
                    try:
                        logger.debug("开始嵌入图片文件到邮件正文中")
                        with open(image, 'rb') as image_file:
                            message_image = MIMEImage(image_file.read())

                            message_image.add_header('Content-ID', '<image>')
                            message.attach(message_image)
                            logger.debug("图片文件嵌入成功")

                    except ImportError:
                        logger.warning("图片文件无法嵌入到邮件正文中")

                elif not self._image_send:
                    logger.debug("不发送图片")

                # 构建邮件正文
                html_part = MIMEText(msg_html, 'html', 'utf-8')
                message_alternative.attach(html_part)

                logger.debug("邮件内容构建成功")
                return message

            except ImportError:
                logger.debug("无法读取邮件模板文件")
                raise

        except ImportError:
            logger.debug(f"邮件创建失败")
            raise

    @staticmethod
    def _send_msg_to_smtp(server, message, sender_mail, receiver_list, log_type, test_type):
        """
        发送邮件到指定 SMTP 服务器
        """
        logger.debug("开始发送邮件")
        try:
            server.sendmail(sender_mail, receiver_list, message.as_string())
            logger.debug(f"使用{log_type}SMTP服务器，发送{test_type}邮件成功")
            server.quit()
            return True
        except ImportError:
            logger.debug(f"使用{log_type}SMTP服务器发送{test_type}邮件失败")
            server.quit()
            return False

    def stop_service(self):
        """
        退出插件
        """
        pass
