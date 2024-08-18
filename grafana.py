from typing import List, Optional, Literal
import httpx
import time
from playwright.sync_api import sync_playwright
from pathlib import Path
import pandas
import re
from notifier.base import BaseNotifier


class Grafana:
    def __init__(self, public_url: str, token: str):
        self.public_url = public_url[:-1] if public_url.endswith('/') else public_url
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }

    def dashboard(self, uid):
        return Dashboard(self, uid)


class Dashboard:
    def __init__(self, grafana: Grafana, uid):
        self.public_url = grafana.public_url
        self.headers = grafana.headers
        self.uid = uid
        self.title: Optional[str] = None
        self.url: Optional[str] = None
        self.slug: Optional[str] = None

        self.tags: Optional[List[str]] = None
        self.query: Optional[str] = 'kiosk'
        self.panels: Optional[List[Panel]] = None

        self.get_info()

    def get_info(self):
        response = httpx.get(
            url=f'{self.public_url}/api/dashboards/uid/{self.uid}',
            headers=self.headers
        ).json()

        dashboard = response.get('dashboard', {})
        meta = response.get('meta', {})

        self.title = dashboard.get('title')
        self.url: str = f'{self.public_url}{meta.get('url')}?{self.query}'
        self.slug = meta.get('slug')
        self.panels = [Panel(self, panel) for panel in dashboard.get('panels', [])]

    def panel(self, uid):
        for p in self.panels:
            if p.uid == uid:
                return p
        return None

    def set_query(self, query_string: str | None = None):
        if query_string:
            self.query = query_string
        return self

    async def creatShortUrl(self):
        uid = httpx.post(
            url=f'{self.public_url}/api/short-urls',
            headers=self.headers,
            json={"path": self.url.replace(f'{self.public_url}/', '')}
        ).json().get('uid')
        return f'{self.public_url}/goto/{uid}'


class Panel:
    def __init__(self, dashboard: Dashboard, data):
        self.public_url = dashboard.public_url
        self.headers = dashboard.headers
        self.uid = str(data.get('id'))
        self.title = dashboard.title + '-' + data.get('title')
        self.url = f'{dashboard.url}&viewPanel={self.uid}'
        self.slug: Optional[str] = dashboard.slug


class File:
    def __init__(self, title, filepath, fileurl, viewurl, slug):
        self.title = title
        self.filepath = filepath
        self.fileurl = fileurl
        self.viewurl = viewurl
        self.slug = slug


class Renderer:
    def __init__(
            self,
            public_url,
            width: int = 792,
            filetype: Literal['png', 'pdf', 'csv', 'xlsx'] = 'png'
    ):
        self.public_url = public_url
        self.directory = 'file'
        self.width = width
        self.filetype = filetype

    def render(self, gfpage: Dashboard | Panel):
        filepath = f"{self.directory}/{self.sanitize_filename(gfpage.title)}_{str(time.time_ns())}.{self.filetype}"
        fileurl = f"{self.public_url}/{filepath}"

        if self.filetype == 'png':
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    page = self.open_page(browser, gfpage.url, gfpage.headers, self.width)
                    page.screenshot(path=filepath, full_page=True, type="png")
                finally:
                    browser.close()
            if self.check_path(filepath):
                return File(title=gfpage.title, filepath=filepath, fileurl=fileurl, viewurl=gfpage.url,
                            slug=gfpage.slug)
            else:
                return None
        elif self.filetype == 'pdf':
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    page = self.open_page(browser, gfpage.url, gfpage.headers, self.width)
                    width = int(page.viewport_size.get('width') / 3.77)
                    height = int(page.viewport_size.get('height') / 3.77)
                    page.pdf(path=filepath, print_background=True, width=f'{width}mm', height=f'{height}mm')
                finally:
                    browser.close()
            if self.check_path(filepath):
                return File(title=gfpage.title, filepath=filepath, fileurl=fileurl, viewurl=gfpage.url,
                            slug=gfpage.slug)
            else:
                return None
        else:
            # 如果页面不是 Panel 则直接返回 None
            if not isinstance(gfpage, Panel):
                return None

            # 首先导出 csv
            csv_filepath = filepath.replace('.xlsx', '.csv')
            xlsx_filepath = filepath.replace('.csv', '.xlsx')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    page = self.open_page(browser, gfpage.url, gfpage.headers, self.width)
                    span = page.query_selector('span:text("下载 CSV")')
                    if span:
                        with page.expect_download() as download_info:
                            span.click()
                        download = download_info.value
                        download.save_as(csv_filepath)
                finally:
                    browser.close()

            # 如果需要 csv 则直接返回
            if self.filetype == 'csv':
                if self.check_path(filepath):
                    return File(title=gfpage.title, filepath=filepath, fileurl=fileurl, viewurl=gfpage.url,
                                slug=gfpage.slug)
                else:
                    return None
            # 如果需要 xlsx 则将 csv 转换为 xlsx 编码后返回
            else:
                try:
                    dataframe = pandas.read_csv(csv_filepath, encoding='utf-8')
                    dataframe.to_excel(xlsx_filepath, index=False, engine='openpyxl')
                except Exception as e:
                    pass

                if self.check_path(filepath):
                    return File(title=gfpage.title, filepath=filepath, fileurl=fileurl, viewurl=gfpage.url,
                                slug=gfpage.slug)
                else:
                    return None

    @staticmethod
    def check_path(relative_path):
        # 创建 Path 对象
        path = Path(relative_path)

        # 检查路径是否存在
        if path.exists():
            # 获取绝对路径
            absolute_path = path.resolve()
            print(f"Absolute path: {absolute_path}")
            return True
        else:
            print(f"The path '{relative_path}' does not exist.")
            return False

    @staticmethod
    def open_page(browser, url, headers, width):
        page = browser.new_page()
        page.set_extra_http_headers(headers)
        page.set_viewport_size({"width": width, "height": 400})
        page.goto(url)
        page.wait_for_load_state('networkidle')
        height = page.evaluate("document.querySelector('.react-grid-layout').offsetHeight")
        page.set_viewport_size({"width": width, "height": height + 50})
        return page

    @staticmethod
    def sanitize_filename(filename: str, replacement: str = "") -> str:
        # 定义非法字符的正则表达式
        illegal_characters = r'[\/:*?"<>|]'

        # 使用正则表达式替换非法字符
        sanitized_name = re.sub(illegal_characters, replacement, filename)

        # 去除开头和结尾的空白字符
        sanitized_name = sanitized_name.strip()

        # 限制文件名长度为30个字符
        max_length = 30
        if len(sanitized_name) > max_length:
            sanitized_name = sanitized_name[:max_length]

        # 检查是否为保留名称
        reserved_names = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8",
                          "COM9",
                          "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
        if sanitized_name.upper() in reserved_names:
            sanitized_name = f"{sanitized_name}_file"

        return sanitized_name


def render_and_send(
        gfpage: Dashboard | Panel,
        public_url: str,
        filetype: Literal['png', 'pdf', 'csv', 'xlsx'],
        width: int,
        notifier: BaseNotifier,
        receiver: List[str]):

    file = Renderer(public_url, width, filetype).render(gfpage)
    notifier.send(file, receiver)
