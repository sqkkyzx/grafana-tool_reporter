import logging
from typing import List, Optional, Dict, Tuple
import httpx
import time

from playwright.sync_api import sync_playwright
from pathlib import Path
import pandas as pd
import re

from notifier import BaseNotifier, File
from s3 import S3Client
from openai import OpenAI


class Grafana:
    def __init__(self, public_url: str, token: str):
        self.public_url = public_url[:-1] if public_url.endswith('/') else public_url
        self.headers = {'Accept': 'application/json', 'Content-Type': 'application/json',
                        'Authorization': f'Bearer {token}'}
        self.validation()

    def validation(self):
        try:
            logging.info("Grafana 配置验证：尝试连接中...")
            response = httpx.get(url=f'{self.public_url}/api/user', headers=self.headers)
            if response.status_code != 200:
                raise Exception(f"Grafana 验证失败: 无法访问 {self.public_url}. 请检查URL和令牌是否正确。")
            else:
                logging.info(f"Grafana 配置验证：验证成功，登录账户为 {response.json().get('login')}")
        except httpx.RequestError as e:
            raise Exception(f"Grafana 验证失败: 连接到 {self.public_url} 时出现错误。错误信息: {str(e)}")

    def dashboard(self, uid):
        return Dashboard(self, uid)


class Dashboard:
    def __init__(self, grafana: Grafana, uid):
        self.public_url = grafana.public_url
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
        response = httpx.get(url=f'{self.public_url}/api/dashboards/uid/{self.uid}', headers=self.headers).json()

        dashboard = response.get('dashboard', {})
        meta = response.get('meta', {})

        self.title = dashboard.get('title')
        self.url: str = f'{self.public_url}{meta.get('url')}?{self.query}'
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
        uid = httpx.post(url=f'{self.public_url}/api/short-urls', headers=self.headers,
                         json={"path": self.url.replace(f'{self.public_url}/', '')}).json().get('uid')
        return f'{self.public_url}/goto/{uid}'


class Panel:
    def __init__(self, dashboard: Dashboard, data):
        self.public_url = dashboard.public_url
        self.headers = dashboard.headers
        self.uid = str(data.get('id'))
        self.title = f"{dashboard.title}-{data.get('title')}"
        self.url = f'{dashboard.url}&viewPanel={self.uid}'
        self.description: Optional[str] = dashboard.description

    def creatShortUrl(self):
        uid = httpx.post(url=f'{self.public_url}/api/short-urls', headers=self.headers,
                         json={"path": self.url.replace(f'{self.public_url}/', '')}).json().get('uid')
        return f'{self.public_url}/goto/{uid}'


class RenderJob:
    def __init__(self, grafana_client: Grafana, enable_notifiers: Dict[str, BaseNotifier], s3client: S3Client,
                 openai: OpenAI | None,
                 **kwargs  # 使用 **job_info 传入
                 ):
        self.grafana_client: Grafana = grafana_client
        self.enable_notifiers: Dict[str, BaseNotifier] = enable_notifiers
        self.s3client: S3Client = s3client
        self.openai: OpenAI | None = openai

        self.name: str = kwargs.get('name', 'UnnamedJob')

        self.page_cfg: dict = self._get_must_value(kwargs, 'page')
        self.render_cfg: dict = self._get_must_value(kwargs, 'render')
        self.crontab_cfg: str = self._get_must_value(kwargs, 'crontab')
        self.notifier_cfg: dict = self._get_must_value(kwargs, 'notifier')

        self.page: Dashboard | Panel = self._get_page()

        # 没有使用API请求时，必循
        if self.notifier_cfg != {'None': 'None'}:
            notifier: Tuple[BaseNotifier, List[str]] = self._get_notifier()
            self.notifier: BaseNotifier = notifier[0]
            self.receiver: List[str] = notifier[1]
        else:
            self.notifier = None
            self.receiver = None

    def _get_must_value(self, dictionary: dict, key: str):
        value = dictionary.get(key)
        if value:
            return value
        else:
            logging.error(f'任务 {self.name} 的配置中缺少字段： {key}')
            raise Exception(f'任务 {self.name} 的配置中缺少字段： {key}')

    def _get_page(self) -> Dashboard | Panel:
        dashboard_uid = self._get_must_value(self.page_cfg, 'dashboard_uid')
        panel_uid = self.page_cfg.get('panel_uid', None)
        query = self.page_cfg.get('query', 'kiosk')

        if panel_uid:
            return self.grafana_client.dashboard(dashboard_uid).set_query(query).panel(panel_uid)
        else:
            return self.grafana_client.dashboard(dashboard_uid).set_query(query)

    def _get_notifier(self) -> Tuple[BaseNotifier, List[str]]:
        name: str = self._get_must_value(self.notifier_cfg, 'type')
        receiver: List[str] = self._get_must_value(self.notifier_cfg, 'receiver')
        notifiers: BaseNotifier = self.enable_notifiers.get(name)
        if notifiers:
            return notifiers, receiver
        elif receiver is None or receiver == [None]:
            logging.error(f'任务 {self.name} 没有设置通知接收人。')
            raise Exception(f'任务 {self.name} 没有设置通知接收人。')
        else:
            logging.error(f'不支持任务 {self.name} 的配置中设置的通知器 {name} 。')
            raise Exception(f'不支持任务 {self.name} 的配置中设置的通知器 {name} 。')

    @staticmethod
    def _check_path(relative_path):
        path = Path(relative_path)
        if path.exists():
            return True
        else:
            return False

    @staticmethod
    def _open_page(browser, url, headers, width):
        page = browser.new_page()
        page.set_extra_http_headers(headers)
        page.set_viewport_size({"width": width, "height": 400})

        page.goto(url)
        page.wait_for_load_state('networkidle')

        # 获取到 .react-grid-layout 的高度并加 50 作为真实高度，然后重新设置窗口大小
        height = page.evaluate("document.querySelector('.react-grid-layout').offsetHeight") + 50
        page.set_viewport_size({"width": width, "height": height})

        # 重新进入页面
        page.goto(url)
        page.wait_for_load_state('networkidle')

        return page

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

    def _aidesc(self, imgurl, prompt):
        if imgurl:
            content = [
                {"type": "text", "text": F"你是一个数据分析专家，请对这张数据截图做出你的分析。这张图的用途(描述)是：{prompt}"},
                {"type": "image_url", "image_url": {"url": imgurl}},
            ]
            response = self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": content}],
                max_tokens=300,
            )
            return response.choices[0].message.content
        else:
            return None

    def render_file(self) -> File | None:

        logging.info(f'正在渲染页面：{self.page.url}')

        width = self.render_cfg.get('width', 792)
        filetype = self.render_cfg.get('filetype', 'png')
        if filetype not in ['png', 'pdf', 'csv', 'xlsx']:
            logging.warning(f'任务 {self.name} 指定的 {filetype} 不支持。')
            return None

        filename = f'{self._sanitize_filename(self.page.title)}_{str(time.time_ns())}'

        filepath = f"files/{filename}.{filetype}"

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                if filetype == 'png':
                    browser_page = self._open_page(browser, self.page.url, self.page.headers, width)
                    browser_page.screenshot(path=filepath, full_page=True, type="png")
                elif filetype == 'pdf':
                    browser_page = self._open_page(browser, self.page.url, self.page.headers, width)
                    # 根据窗口尺寸计算纸张毫米单位
                    # ⚠ 此处 3.77 由实际调试得到，不同设备是否存在影响尚未得到证实
                    width = int(browser_page.viewport_size.get('width') / 3.77)
                    height = int(browser_page.viewport_size.get('height') / 3.77)
                    browser_page.pdf(path=filepath, print_background=True, width=f'{width}mm', height=f'{height}mm')
                else:  # 将会匹配 filetype in ['xlsx', 'csv']
                    # 如果页面不是 Panel 则跳过打开页面
                    if not isinstance(self.page, Panel):
                        logging.warning(f"无法将整个仪表盘导出为{filetype}，请为任务 {self.name} 指定一个Panel。")
                    else:
                        browser_page = self._open_page(browser, self.page.url, self.page.headers, width)
                        # 无论是否导出 xlsx 都需要先导出 csv
                        csv_filepath = filepath.replace('.xlsx', '.csv')
                        span = browser_page.query_selector('span:text("下载 CSV")')
                        if span:
                            with browser_page.expect_download() as download_info:
                                span.click()
                            download = download_info.value
                            download.save_as(csv_filepath)
                        # 如果需要 xlsx 则将 csv 转换为 xlsx
                        if filetype == 'xlsx':
                            dataframe = pd.read_csv(csv_filepath, encoding='utf-8')
                            dataframe.to_excel(filepath, index=False, engine='openpyxl')
            finally:
                browser.close()
        if self._check_path(filepath):
            fileurl = self.s3client.upload(filepath)
            viewurl = self.page.creatShortUrl()
            if self.openai and '[AI]' in self.page.description and filetype == 'png':
                description = self._aidesc(fileurl, self.page.description.replace('[AI]', ''))
            else:
                description = self.page.description
            return File(title=self.page.title, filetype=filetype, filepath=filepath, fileurl=fileurl, viewurl=viewurl,
                        description=description)
        else:
            return None

    def notice(self):
        # 渲染文件并发送通知
        file: File = self.render_file()
        if file and self.receiver:
            self.notifier.send(file, self.receiver)
        else:
            logging.error(f"任务 {self.name} 页面渲染失败，无法发送通知。")
