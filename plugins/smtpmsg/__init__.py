from typing import Any, List, Dict, Tuple

import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

from app.core.event import eventmanager, Event
from app.log import logger
from app.plugins import _PluginBase
from app.schemas.types import EventType, NotificationType

# cp -r /config/smtpmsg /app/app/plugins
# rm -rf /app/app/plugins/smtpmsg
# cp -a /config/smtp.png /public/plugin
# pip install -r requirements.txt


class SmtpMsg(_PluginBase):
    # 插件名称
    plugin_name = "SMTP邮件消息通知"
    # 插件描述
    plugin_desc = "支持使用邮件服务器发送消息通知。"
    # 插件图标
    plugin_icon = "Synomail_A.png"
    # 插件版本
    plugin_version = "1.2"
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
    # 插件开关
    _enabled = False
    # 备用服务器开关
    _secondary = False
    # 发送测试消息
    _test = False

    """
     # 调试开关
     _debug = False
     """

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

    def init_plugin(self, config: dict = None):
        logger.info(f"初始化插件 {self.plugin_name}")
        if config:
            # 插件开关
            self._enabled = config.get("enabled")
            # 备用服务器开关
            self._secondary = config.get("secondary")
            # 测试开关
            self._test = config.get("test")
            # self._test = False

            """
            # debug开关
            self._debug = config.get("debug")
            """

            # 主服务器-地址/端口/加密方式
            self._main_smtp_host = config.get("main_smtp_host")
            self._main_smtp_port = config.get("main_smtp_port")
            self._main_smtp_encryption = config.get("main_smtp_encryption")
            # 主服务器-账号/密码
            self._main_sender_mail = config.get("main_sender_mail")
            self._main_sender_password = config.get("main_sender_password")

            # 备用服务器
            if self._secondary:
                # 备用服务器-地址/端口/加密方式
                self._secondary_smtp_host = config.get("secondary_smtp_host")
                self._secondary_smtp_port = config.get("secondary_smtp_port")
                self._secondary_smtp_encryption = config.get("secondary_smtp_encryption")
                # 备用服务器-账号/密码
                self._secondary_sender_mail = config.get("secondary_sender_mail")
                self._secondary_sender_password = config.get("secondary_sender_password")

            # 发件人类型
            self._sender_name = config.get("sender_name")
            self._receiver_mail = config.get("receiver_mail")

            # 消息类型
            self._msgtypes = config.get("msgtypes") or []

        if (not self._main_smtp_host or
                not self._main_smtp_port or
                not self._main_smtp_encryption or
                not self._main_sender_mail or
                not self._main_sender_password or
                not self._receiver_mail):
            self._enabled = False
            logger.warn(f"{self.plugin_name} 基础参数配置不完整，关闭插件")

        if self._test and self._enabled:
            logger.info("发送测试邮件")
            self.send_msg_to_main_smtp(title="测试服务器配置",
                                       text="这是一封测试邮件~~~",
                                       image="/public/plugin_icon/Synomail_A.png")
            if self._secondary:
                self.send_msg_to_secondary_smtp(title="测试备用服务器配置",
                                                text="这是一封测试邮件~~~",
                                                image="/public/plugin_icon/Synomail_A.png")
            self._test = False

            self.update_config({
                # 测试开关
                "test": False,
                # 插件开关
                "enabled": self._enabled,
                # 备用服务器开关
                "secondary": self._secondary,

                # 主服务器-地址/端口/加密方式
                "main_smtp_host": self._main_smtp_host,
                "main_smtp_port": self._main_smtp_port,
                "main_smtp_encryption": self._main_smtp_encryption,
                # 主服务器-账号/密码
                "main_sender_mail": self._main_sender_mail,
                "main_sender_password": self._main_sender_password,

                # 备用服务器-地址/端口/加密方式
                "secondary_smtp_host": self._secondary_smtp_host,
                "secondary_smtp_port": self._secondary_smtp_port,
                "secondary_smtp_encryption": self._secondary_smtp_encryption,
                # 备用服务器-账号/密码
                "secondary_sender_mail": self._secondary_sender_mail,
                "secondary_sender_password": self._secondary_sender_password,

                # 发件人用户名/收件人地址
                "sender_name": self._sender_name,
                "receiver_mail": self._receiver_mail,

                # 消息类型
                "msgtypes": self._msgtypes or []
            })

    def get_state(self) -> bool:
        return self._enabled and (True
                                  if self._main_smtp_host and
                                     self._main_smtp_port and
                                     self._main_smtp_encryption and
                                     self._main_sender_mail and
                                     self._main_sender_password and
                                     self._receiver_mail
                                  else False)

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
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
                                            'model': 'secondary',
                                            'label': '启动备用服务器',
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
                                    'cols': 12,
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
                                    'cols': 12,
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
                                    'cols': 12,
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
                                    'cols': 12,
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
                                            'placeholder': '不输入时默认使用邮箱地址',
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
                                            'placeholder': 'example@example.com',
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
                                            'text': '打开 "启动备用服务器" 后，会在 "服务器" 发送失败时，尝试使用 "备用服务器" 发送消息'
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
                                            'text': '打开 "发送测试邮件" 并 "保存" 后，'
                                                    '出现邮件服务器访问缓慢或是因为参数有误，导致出现配置页面长时间未关闭时，请手动关闭插件并重置插件设置；'
                                                    ' "发送测试邮件" 会在点击 "保存" 关闭配置页面后，自动恢复关闭状态'

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
                                            'text': '收件人地址可填入多个邮箱，多个邮箱间用 "," 分割，如：test-1@example.com,test-2@example.com'
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                ]
            }
        ], {
            # 插件开关
            'enabled': False,
            # 备用服务器开关
            'secondary': False,
            # 测试开关
            'test': False,

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

        if not title and not text:
            logger.warn("标题和内容不能同时为空")
            return

        if (msg_type and self._msgtypes
                and msg_type.name not in self._msgtypes):
            logger.info(f"消息类型 {msg_type.value} 未开启消息发送")
            return

        try:
            self.send_msg_to_main_smtp(title=title,
                                       text=text,
                                       image="" if image is None else image)

        except Exception as msg_e:
            logger.error(f"Smtp消息发送失败，错误信息：{str(msg_e)}")

    # 主服务器
    def send_msg_to_main_smtp(self, title, text="", image=""):
        # 设置邮件参数
        message = MIMEMultipart()
        # 邮件主题
        message['Subject'] = Header(title, "utf-8")
        # 发送人设置
        message['From'] = f'{self._sender_name} <{self._main_sender_mail}>'
        # 文本正文
        text_part = MIMEText(text, 'plain', 'utf-8')
        # 添加文本正文
        message.attach(text_part)

        # 如果有图片
        if image is not None:
            try:
                with open(image, 'rb') as image_file:
                    # 读取照片为二进制数据
                    image_part = MIMEImage(image_file.read())
                    # 设置图片在邮件中显示的位置
                    image_part.add_header('Content-ID', '<image1>')
                    # 添加图片
                    message.attach(image_part)
                    # html代码
                    html_part = MIMEText(
                        f'<html>\n'
                        f'<body>\n'
                        f'  <div style="text-align:center;">\n'
                        f'  <p '
                        f'style="'
                        f'background-color:#1864f5; '
                        f'padding:20px; '
                        f'color:white; '
                        f'"'
                        f'>'
                        f'{text}'
                        f'</p>\n'
                        f'  </div>\n'
                        f'  <div style="width:100%; background-color:#f6f6f6;">'
                        f'  <img '
                        f'src="cid:image1" '
                        f'width="256px" '
                        f'style="'
                        f'padding:30px; '
                        f'display: block; '
                        f'margin-left: auto; '
                        f'margin-right: auto;" '
                        f'alt="Image 1"'
                        f'>\n'
                        f'  </div>\n'
                        f'</body>\n'
                        f'</html>',
                        'html', 'utf-8')

                    # 添加html正文
                    message.attach(html_part)

            except Exception as e:
                logger.info("无法使用html邮件格式，使用纯文本邮件格式发送")
                logger.info(f"错误报告：{e}")

        # 开始连接并发送
        if self._main_smtp_encryption == "SSL":
            # 使用SSL加密，创建一个安全的SMTP连接
            main_server = smtplib.SMTP_SSL(self._main_smtp_host, self._main_smtp_port)
            logger.info("使用SSL连接")
        elif self._main_smtp_encryption == "TLS":
            # 使用TLS加密，创建一个安全的SMTP连接
            main_server = smtplib.SMTP(self._main_smtp_host, self._main_smtp_port)
            logger.info("使用TLS连接")
        else:
            main_server = smtplib.SMTP(self._main_smtp_host, self._main_smtp_port)
            logger.info("不使用加密方式连接")

        # 使用with语句自动管理SMTP连接
        with main_server:
            try:
                # 验证服务器
                main_server.ehlo(self._main_smtp_host)

                # 如果使用TLS，需要再次验证并启动加密
                if self._main_smtp_encryption == "TLS":
                    main_server.starttls()
                    main_server.ehlo(self._main_smtp_host)
                logger.info("连接成功")

                # 登录服务器
                main_server.login(self._main_sender_mail, self._main_sender_password)
                logger.info("登录成功")

            except Exception as e:
                # 如果出现异常，打印错误信息
                logger.error("无法与服务器建立连接")
                logger.debug(f"错误报告：{e}")

                if self._secondary is True and self._test is False:
                    logger.warn("尝试使用备用服务器进行发送")
                    return self.send_msg_to_secondary_smtp(title=title, text=text, image=image)
                else:
                    logger.error("未启动备用服务器，运行失败，请检查配置")

            else:
                # 如果没有异常，发送邮件
                try:
                    # 拆分多个发件人
                    _receiver_list = self._receiver_mail.split(",")
                    # 发送邮件
                    main_server.sendmail(self._main_sender_mail, _receiver_list, message.as_string())

                except Exception as e:
                    # 如果出现异常，打印错误信息
                    logger.warn(f"发送失败")
                    logger.debug(f"错误报告：{e}")

                    if self._secondary is True and self._test is False:
                        logger.warn("尝试使用备用服务器进行发送")
                        return self.send_msg_to_secondary_smtp(title=title,
                                                               text=text,
                                                               image=image)
                    else:
                        logger.error("未启动备用服务器，运行失败，请检查配置")

                else:
                    # 如果没有异常，打印成功信息
                    logger.info("发送成功")

            finally:
                if not self._secondary:
                    # 无论是否有异常，都打印退出信息
                    logger.info("退出连接")

    # 备用服务器
    def send_msg_to_secondary_smtp(self, title, text="", image=""):
        # 检查配置完整性
        if (not self._secondary_smtp_host or
                not self._secondary_smtp_port or
                not self._secondary_smtp_encryption or
                not self._secondary_sender_mail or
                not self._secondary_sender_password):
            logger.error("备用服务器参数配置不完整，终止运行")
            return False, "参数未配置"

        # 设置邮件参数
        message = MIMEMultipart()
        # 邮件主题
        message['Subject'] = Header(title, "utf-8")
        # 发送人设置
        message['From'] = f'{self._sender_name} <{self._secondary_sender_mail}>'
        # 文本正文
        text_part = MIMEText(text, 'plain', 'utf-8')
        # 添加文本正文
        message.attach(text_part)

        # 如果有图片
        if image is not None:
            try:
                with open(image, 'rb') as image_file:
                    # 读取照片为二进制数据
                    image_part = MIMEImage(image_file.read())
                    # 设置图片在邮件中显示的位置
                    image_part.add_header('Content-ID', '<image1>')
                    # 添加图片
                    message.attach(image_part)
                    # html代码
                    html_part = MIMEText(
                        f'<html>\n'
                        f'<body>\n'
                        f'  <div style="text-align:center;">\n'
                        f'  <p '
                        f'style="'
                        f'background-color:#1864f5; '
                        f'padding:20px; '
                        f'color:white; '
                        f'"'
                        f'>'
                        f'{text}'
                        f'</p>\n'
                        f'  </div>\n'
                        f'  <div style="width:100%; background-color:#f6f6f6;">'
                        f'  <img '
                        f'src="cid:image1" '
                        f'width="256px" '
                        f'style="'
                        f'padding:30px; '
                        f'display: block; '
                        f'margin-left: auto; '
                        f'margin-right: auto;" '
                        f'alt="Image 1"'
                        f'>\n'
                        f'  </div>\n'
                        f'</body>\n'
                        f'</html>',
                        'html', 'utf-8')

                    # 添加html正文
                    message.attach(html_part)

            except Exception as e:
                logger.info("无法使用html邮件格式，使用纯文本邮件格式发送")
                logger.info(f"错误报告：{e}")

        # 开始连接并发送
        if self._secondary_smtp_encryption == "SSL":
            secondary_server = smtplib.SMTP_SSL(self._secondary_smtp_host, self._secondary_smtp_port)
            logger.info("使用SSL连接备用服务器")
        elif self._secondary_smtp_encryption == "TLS":
            # 使用TLS加密，创建一个安全的SMTP连接
            secondary_server = smtplib.SMTP(self._secondary_smtp_host, self._secondary_smtp_port)
            logger.info("使用TLS连接备用服务器")
        else:
            secondary_server = smtplib.SMTP(self._secondary_smtp_host, self._secondary_smtp_port)
            logger.info("不使用加密方式连接备用服务器")

        # 使用with语句自动管理SMTP连接
        with secondary_server:
            try:
                # 验证服务器
                secondary_server.ehlo(self._secondary_smtp_host)

                # 如果使用TLS，需要再次验证并启动加密
                if self._secondary_smtp_encryption == "TLS":
                    secondary_server.starttls()
                    secondary_server.ehlo(self._secondary_smtp_host)
                logger.info("备用服务器连接成功")

                # 登录服务器
                secondary_server.login(self._secondary_sender_mail, self._secondary_sender_password)
                logger.info("备用服务器登录成功")

            except Exception as e:
                # 如果出现异常，打印错误信息
                logger.warn("无法与备用服务器建立连接")
                logger.debug(f"错误报告:{e}")

            else:
                # 如果没有异常，发送邮件
                try:
                    # 拆分多个收件人
                    _receiver_list = self._receiver_mail.split(",")
                    # 发送邮件
                    secondary_server.sendmail(self._secondary_sender_mail, _receiver_list, message.as_string())

                except Exception as e:
                    # 如果出现异常，打印错误信息
                    logger.warn("备用服务器发送失败")
                    logger.debug(f"错误报告：{e}")
                else:
                    # 如果没有异常，打印成功信息
                    logger.info("备用服务器发送成功")

            finally:
                # 无论是否有异常，都打印退出信息
                logger.info("退出连接")

    # 退出插件
    def stop_service(self):
        """
        退出插件
        """
        pass
