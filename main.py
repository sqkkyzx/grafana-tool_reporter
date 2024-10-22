import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Literal

import boto3
import httpx
import pandas as pd
import uvicorn
from botocore.client import Config, BaseClient
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from fastapi import FastAPI
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field


app = FastAPI()


class Payload(BaseModel):
    dashboard_uid: str = Field(description="Dashboard UID")
    panel_uid: str|None = Field(default=None, description="Panel UID")
    query_string: str|None = Field(default=None, description="Query String")

    render_type: Literal['jpg', 'xlsx', 'png'] = Field(default='png', description="Render Type")
    render_width: int = Field(default=796, description="Render Width")

    base_url: str = Field(default=os.getenv("GF_URL"), description="Grafana URL")
    service_token: str = Field(default=os.getenv("GF_TOKEN"), description="Grafana Token")


@app.post("/render")
async def render(data: Payload):
    grafana = Grafana(data.base_url, data.service_token)
    if data.panel_uid:
        page=grafana.dashboard(data.dashboard_uid).set_query(data.query_string).panel(data.panel_uid)
    else:
        page=grafana.dashboard(data.dashboard_uid).set_query(data.query_string)

    return await page.render(data.render_type, data.render_width)


class Grafana:
    _instances: Dict[tuple, 'Grafana'] = {}

    def __new__(cls, base_url: str, token: str) -> 'Grafana':
        key = (base_url, token)

        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls)

        return cls._instances[key]

    def __init__(self, base_url: str, token: str) -> None:
        if not hasattr(self, 'initialized'):
            self.base_url = base_url.rstrip('/')
            self.headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }
            try:
                self._validation()
                self.initialized = True
            except Exception as e:
                # 处理验证失败的情况
                print(f"Initialization failed: {e}")
                # 可能的话，从 _instances 中移除这个实例
                key = (base_url, token)
                self.__class__._instances.pop(key, None)
                raise

    def _validation(self):
        try:
            logging.info("Grafana 配置验证：尝试连接中...")
            response = httpx.get(url=f'{self.base_url}/api/user', headers=self.headers)
            if response.status_code != 200:
                raise Exception(f"Grafana 验证失败: 无法访问 {self.base_url}. 请检查URL和令牌是否正确。")
            else:
                logging.info(f"Grafana 配置验证：验证成功，登录账户为 {response.json().get('login')}")
        except httpx.RequestError as e:
            raise Exception(f"Grafana 验证失败: 连接到 {self.base_url} 时出现错误。错误信息: {str(e)}")

    def dashboard(self, uid):
        return Dashboard(self, uid)


class Dashboard:
    def __init__(self, grafana: Grafana, uid):
        self.base_url = grafana.base_url
        self.headers = grafana.headers
        self.uid = uid
        self.title: Optional[str] = None
        self.url: Optional[str] = None
        self.description: Optional[str] = None

        self.tags: Optional[List[str]] = None
        self.query: Optional[str] = 'kiosk'
        self.panels: Optional[List[Panel]] = None

        self.get_info()

    def get_info(self):
        response = httpx.get(url=f'{self.base_url}/api/dashboards/uid/{self.uid}', headers=self.headers).json()

        dashboard = response.get('dashboard', {})
        meta = response.get('meta', {})

        self.title = dashboard.get('title')
        self.url: str = f'{self.base_url}{meta.get('url')}?{self.query}'
        self.description = meta.get('description')
        self.panels = [Panel(self, panel) for panel in dashboard.get('panels', [])]

    def panel(self, uid):
        for p in self.panels:
            if str(p.uid) == str(uid):
                return p
        return None

    def set_query(self, query_string: str | None = None):
        if query_string:
            self.query = query_string
            self.url: str = f'{self.url.split('?')[0]}?{self.query}'
        return self

    def creatShortUrl(self):
        uid = httpx.post(url=f'{self.base_url}/api/short-urls', headers=self.headers,
                         json={"path": self.url.replace(f'{self.base_url}/', '')}).json().get('uid')
        return f'{self.base_url}/goto/{uid}'

    def render(self, render_type: Literal['jpg', 'xlsx', 'png'], render_width: int):
        return Render(self, render_type, render_width).render_file()


class Panel:
    def __init__(self, dashboard: Dashboard, data):
        self.base_url = dashboard.base_url
        self.headers = dashboard.headers
        self.uid = str(data.get('id'))
        self.title = f"{dashboard.title}-{data.get('title')}"
        self.url = f'{dashboard.url}&viewPanel={self.uid}'
        self.description: Optional[str] = dashboard.description

    def creatShortUrl(self):
        uid = httpx.post(url=f'{self.base_url}/api/short-urls', headers=self.headers,
                         json={"path": self.url.replace(f'{self.base_url}/', '')}).json().get('uid')
        return f'{self.base_url}/goto/{uid}'

    def render(self, render_type: Literal['jpg', 'xlsx', 'png'], render_width: int):
        return Render(self, render_type, render_width).render_file()


class Render:
    def __init__(self, page: Dashboard | Panel, render_type: Literal['jpg', 'xlsx', 'png'], render_width: int):
        self.render_type=render_type
        self.render_width=render_width
        self.page=page

    @staticmethod
    def _check_path(relative_path):
        path = Path(relative_path)
        if path.exists():
            return True
        else:
            return False

    @staticmethod
    async def _open_page(browser, url, headers, width):
        browser_page = await browser.new_page()
        await browser_page.set_extra_http_headers(headers)
        await browser_page.set_viewport_size({"width": width, "height": 400})

        await browser_page.goto(url)
        await browser_page.wait_for_load_state('networkidle')

        # 获取到 .react-grid-layout 的高度并加 50 作为真实高度，然后重新设置窗口大小
        height = await browser_page.evaluate("document.querySelector('.react-grid-layout').offsetHeight") + 50
        await browser_page.set_viewport_size({"width": width, "height": height})

        # 重新进入页面
        await browser_page.goto(url)
        await browser_page.wait_for_load_state('networkidle')

        return browser_page

    @staticmethod
    def _sanitize_filename(filename: str, replacement: str = "") -> str:
        # 定义非法字符的正则表达式
        illegal_characters = r'[\/:*?"<>|]'
        # 使用正则表达式替换非法字符，去除开头和结尾的空白字符
        sanitized_name = re.sub(illegal_characters, replacement, filename).strip()
        # 限制文件名长度为30个字符
        max_length = 30
        if len(sanitized_name) > max_length:
            sanitized_name = sanitized_name[:max_length]
        return sanitized_name

    async def render_file(self) -> Dict | None:

        logging.info(f'正在渲染页面：{self.page.url}')

        # width = self.render_width
        # filetype = self.render_type
        if self.render_type not in ['png', 'pdf', 'csv', 'xlsx']:
            logging.warning(f'任务指定的 {self.render_type} 不支持。')
            return None

        filepath = f"files/{self._sanitize_filename(self.page.title)}_{str(time.time_ns())}.{self.render_type}"

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                if self.render_type == 'png':
                    browser_page = await self._open_page(browser, self.page.url, self.page.headers, self.render_width)
                    await browser_page.screenshot(path=filepath, full_page=True, type="png")
                elif self.render_type == 'pdf':
                    browser_page = await self._open_page(browser, self.page.url, self.page.headers, self.render_width)
                    # 根据窗口尺寸计算纸张毫米单位
                    # ⚠ 此处 3.77 由实际调试得到，不同设备是否存在影响尚未得到证实
                    width = int(await browser_page.viewport_size.get('width') / 3.77)
                    height = int(await browser_page.viewport_size.get('height') / 3.77)
                    await browser_page.pdf(path=filepath, print_background=True, width=f'{width}mm', height=f'{height}mm')
                else:  # 将会匹配 filetype in ['xlsx', 'csv']
                    # 如果页面不是 Panel 则跳过打开页面
                    if not isinstance(self.page, Panel):
                        logging.warning(f"无法将整个仪表盘导出为{self.render_type}，请为任务指定一个Panel。")
                    else:
                        browser_page = self._open_page(browser, self.page.url, self.page.headers, self.render_width)
                        # 无论是否导出 xlsx 都需要先导出 csv
                        csv_filepath = filepath.replace('.xlsx', '.csv')


                        span = await browser_page.query_selector('span:text("下载 CSV")')
                        if span:
                            async with browser_page.expect_download() as download_info:
                                await span.click()
                            download = await download_info.value
                            await download.save_as(csv_filepath)

                        # 如果需要 xlsx 则将 csv 转换为 xlsx
                        if self.render_type == 'xlsx':
                            dataframe = pd.read_csv(csv_filepath, encoding='utf-8')
                            dataframe.to_excel(filepath, index=False, engine='openpyxl')
            finally:
                await browser.close()

        if self._check_path(filepath):
            file_url = S3Client().upload(filepath)
            os.remove(filepath)
            return {
            'title': self.page.title,
            'description': self.page.description,
            'file_type': self.render_type,
            'file_url': file_url,
            'webpage_url': self.page.creatShortUrl()
        }
        else:
            raise


class S3Client:
    _instance: Optional['S3Client'] = None

    def __new__(cls) -> 'S3Client':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.region = os.getenv('S3_REGION')
        self.bucket = os.getenv('S3_BUCKET')
        self.endpoint_url = os.getenv('S3_ENDPOINT_URL')
        self.public_url = os.getenv('S3_PUBLIC_URL').rstrip('/')
        self.access_key_id = os.getenv('S3_ACCESS_KEY_ID')
        self.secret_access_key = os.getenv('S3_SECRET_ACCESS_KEY')
        self.addressing_style = os.getenv('S3_ADDRESSING_STYLE') or 'virtual'

        if self.addressing_style == 'virtual' and self.bucket in self.endpoint_url:
            self.endpoint_url = self.endpoint_url.replace(f'{self.bucket}.', '')

        self.client: BaseClient = boto3.client(
            's3',
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': self.addressing_style}),
        )

        self._validate()
        self._initialized = True

    def _validate(self):
        content = f"CREATE_BY: grafana-tool_reporter\nCREATE_TS: {datetime.now().timestamp()}"
        try:
            logging.info("S3配置验证：上传验证中...")
            self.client.put_object(Bucket=self.bucket, Key='.s3_config_validate', Body=content.encode())
            logging.info("S3配置验证：上传成功")

            # 如果存在 public_url，则尝试使用 public_url 下载
            if self.public_url:
                try:
                    response = httpx.get(f"{self.public_url}/.s3_config_validate")
                    response.raise_for_status()
                    downloaded_content = response.text
                    if content.strip() == downloaded_content.strip():
                        logging.warning("S3配置验证：public_url 验证成功。")
                    else:
                        logging.error(f"S3配置验证失败：上传与读取文件内容不匹配。")
                        raise Exception("S3配置验证失败：上传与读取文件内容不匹配。")
                except Exception as e:
                    logging.debug(e)
                    logging.warning(
                        "S3配置验证：配置中的 public_url 不可用，将使用预签名链接返回对象url，预签名链接将在 1 小时后过期。")
                    self.public_url = None
            else:
                logging.warning(
                    "S3配置验证：未配置 public_url ，将使用预签名链接返回对象url，预签名链接将在 1 小时后过期。")

            if self.public_url is None:
                logging.info("S3配置验证：读取验证中...")
                response = self.client.get_object(Bucket=self.bucket, Key='.s3_config_validate')
                downloaded_content = response['Body'].read().decode()
                if content.strip() == downloaded_content.strip():
                    logging.info(f"S3配置验证：读取成功")
                else:
                    logging.error(f"S3配置验证失败：上传与读取文件内容不匹配。")
                    raise Exception("S3配置验证失败：上传与读取文件内容不匹配。")

        except NoCredentialsError:
            logging.error("S3配置验证失败：缺少有效凭证。")
            raise Exception("S3配置验证失败：缺少有效凭证。")
        except PartialCredentialsError:
            logging.error("S3配置验证失败：凭证不完整。")
            raise Exception("S3配置验证失败：凭证不完整。")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                logging.error("S3配置验证失败：桶不存在。请检查桶名称是否正确。")
                raise Exception("S3配置验证失败：桶不存在。请检查桶名称是否正确。")
            elif error_code == 'AccessDenied':
                logging.error("S3配置验证失败：访问被拒绝。请检查您的访问权限。")
                raise Exception("S3配置验证失败：访问被拒绝。请检查您的访问权限。")
            else:
                logging.error(f"S3配置验证失败：{e.response['Error']['Message']}")
                raise Exception(f"S3配置验证失败：{e.response['Error']['Message']}")
        except Exception as e:
            logging.error(f"S3配置验证失败：{str(e)}")
            raise Exception(f"S3配置验证失败：{str(e)}")

    def _create_pre_signed_url(self, object_name, expiration=3600) -> str | None:
        """Generate a pre-signed URL to share an S3 object
        :param object_name:
        :param expiration: Time in seconds for the pre-signed URL to remain valid
        :return: Pre-signed URL as string. If error, returns None.
        """
        try:
            response = self.client.generate_presigned_url('get_object',
                                                          Params={'Bucket': self.bucket, 'Key': object_name},
                                                          ExpiresIn=expiration)
            logging.info(f"创建了有效期为 {expiration} 秒的对象预签名链接：{response}")
        except ClientError as e:
            logging.error(e)
            return None
        return response

    def upload(self, filepath) -> str | None:
        """
        :param filepath: 要上传的文件
        :return: True 如果上传成功，否则 False
        """
        try:
            self.client.upload_file(filepath, self.bucket, filepath)

            object_url = None
            # 如果存在 public_url，则尝试拼接公开访问链接
            if self.public_url:
                object_url = f"{self.public_url}/{filepath}"
            # 如果 public_url 不存在或无法拼接链接，则生成预签名链接
            if not object_url:
                object_url = self._create_pre_signed_url(filepath)

            return object_url
        except FileNotFoundError:
            logging.error("文件上传错误: 文件不存在")
            return None
        except Exception as e:
            logging.error(f"文件上传错误: {e}")
            return None


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
