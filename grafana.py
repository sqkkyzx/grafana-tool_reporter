import asyncio
from typing import List, Optional
import httpx
import time
import logging
from playwright.async_api import async_playwright
from pathlib import Path
import csv
import os
import pandas


class Grafana:
    def __init__(self, domain: str, token: str, tls: bool = True):
        self.domain = domain
        self.token = token
        self.tls = tls

        self.scheme = 'https' if tls else 'http'
        self.view_url = f'{self.scheme}://{domain}'
        self.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}'
        }

    def dashboard(self, uid):
        return Dashboard(self, uid)


class Dashboard:
    def __init__(self, grafana: Grafana, uid):
        self.uid = uid

        self.site_url = grafana.view_url
        self.headers = grafana.headers

        self.title: Optional[str] = None
        self.tags: Optional[List[str]] = None
        self.timezone: Optional[str] = None
        self.schemaVersion: Optional[int] = None
        self.version: Optional[int] = None
        self.isStarred: Optional[bool] = None
        self.path: Optional[str] = None
        self.folderId: Optional[int] = None
        self.folderUid: Optional[str] = None
        self.slug: Optional[str] = None
        self.query: Optional[str] = 'kiosk'
        self.panels: Optional[List[Panel]] = None

        self.view_url: Optional[str] = None

        self.get_info()

    def get_info(self):
        response = httpx.get(
            url=f'{self.site_url}/api/dashboards/uid/{self.uid}',
            headers=self.headers
        ).json()

        dashboard = response.get('dashboard', {})

        meta = response.get('meta', {})

        self.isStarred = meta.get('isStarred')
        self.path = meta.get('url')
        self.folderId = meta.get('folderId')
        self.folderUid = meta.get('folderUid')
        self.slug = meta.get('slug')

        self.view_url: str = f'{self.site_url}{self.path}?{self.query}'

        self.title = dashboard.get('title')
        self.tags = dashboard.get('tags')
        self.timezone = dashboard.get('timezone')
        self.schemaVersion = dashboard.get('schemaVersion')
        self.version = dashboard.get('version')
        self.panels = [Panel(self, panel) for panel in dashboard.get('panels', [])]

    def set_query(self, query_string: str):
        self.query = query_string

    def renderPNG(self, width: int = 792):
        filepath = f"temp/{self.title}_{str(time.time_ns())}.png"
        asyncio.run(renderPNG(self.view_url, self.headers, filepath, width))
        is_success = check_path(filepath)
        if is_success:
            return filepath
        else:
            return None

    def renderPDF(self, width: int = 792):
        filepath = f"temp/{self.title}_{str(time.time_ns())}.pdf"
        asyncio.run(renderPDF(self.view_url, self.headers, filepath, width))
        is_success = check_path(filepath)
        if is_success:
            return filepath
        else:
            return None

    async def creatShortUrl(self):
        uid = httpx.post(
            url=f'{self.site_url}/api/short-urls',
            headers=self.headers,
            json={
                "path": self.path.replace('/d', 'd')
            }
        ).json().get('uid')
        return f'{self.site_url}/goto/{uid}'


class Panel:
    def __init__(self, dashboard: Dashboard, data):
        self.uid = data.get('id')
        self.title = data.get('title')
        self.dashboard_title = dashboard.title
        self.headers = dashboard.headers
        self.view_url = f'{dashboard.view_url}&viewPanel={self.uid}'

    def renderPDF(self, width: int = 792):
        filepath = f"temp/{self.dashboard_title}-{self.title}_{str(time.time_ns())}.pdf"
        asyncio.run(renderPDF(self.view_url, self.headers, filepath, width))
        is_success = check_path(filepath)
        if is_success:
            return filepath
        else:
            return None

    def renderPNG(self, width: int = 792):
        filepath = f"temp/{self.dashboard_title}-{self.title}_{str(time.time_ns())}.png"
        asyncio.run(renderPNG(self.view_url, self.headers, filepath, width))
        is_success = check_path(filepath)
        if is_success:
            return filepath
        else:
            return None

    def outputCSV(self, xlsx: bool = True):
        url = f"{self.view_url}&inspect={self.uid}&inspectTab=data"
        filepath = f"temp/{self.dashboard_title}-{self.title}_{str(time.time_ns())}.csv"
        asyncio.run(outputCSV(url, self.headers, filepath))
        is_success = check_path(filepath)
        if is_success:
            if xlsx:
                try:
                    dataframe = pandas.read_csv(filepath, encoding='utf-8')
                    filepath = filepath.replace('.csv', '.xlsx')
                    dataframe.to_excel(filepath.replace('.csv', '.xlsx'), index=False, engine='openpyxl')
                except pandas.errors.EmptyDataError:
                    print(f"EmptyDataError: {filepath} is Empty")
            return filepath
        else:
            return None


def convert_csv_to_ansi(filepath, ansi_encoding='windows-1252'):
    try:
        # 使用原始字符串处理文件路径
        filepath = os.path.normpath(filepath)

        # 读取CSV文件并使用UTF-8编码
        with open(filepath, 'r', encoding='utf-8') as src_file:
            reader = csv.reader(src_file)
            rows = list(reader)

        # 写入转换后的CSV文件，使用ANSI编码覆盖原文件
        with open(filepath, 'w', encoding=ansi_encoding) as dest_file:
            writer = csv.writer(dest_file)
            writer.writerows(rows)

        print(f"CSV file '{filepath}' has been converted from UTF-8 to {ansi_encoding} encoding.")
    except Exception as e:
        print(f"An error occurred while converting the file: {e}")


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


async def open_page(browser, url, headers, width):
    page = await browser.new_page()
    await page.set_extra_http_headers(headers)
    await page.set_viewport_size({"width": width, "height": 400})
    await page.goto(url)
    await page.wait_for_load_state('networkidle')
    height = await page.evaluate("document.querySelector('.react-grid-layout').offsetHeight")
    await page.set_viewport_size({"width": width, "height": height + 50})
    return page


async def renderPDF(url, headers, filepath, width: int = 792):
    logging.info(f"Rendering {filepath} From {url}...")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await open_page(browser, url, headers, width)
            width, height = int(page.viewport_size.get('width')/3.77), int(page.viewport_size.get('height')/3.77)
            await page.pdf(path=filepath, print_background=True, width=f'{width}mm', height=f'{height}mm')
        finally:
            await browser.close()
    return filepath


async def renderPNG(url, headers, filepath, width: int = 792):
    logging.info(f"Rendering {filepath} From {url}...")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await open_page(browser, url, headers, width)
            await page.screenshot(path=filepath, full_page=True, type="png")
        finally:
            await browser.close()
    return filepath


async def outputCSV(url, headers, filepath, width: int = 792):
    logging.info(f"Outputing {filepath} From {url}...")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await open_page(browser, url, headers, width)
            span = await page.query_selector('span:text("下载 CSV")')
            if span:
                async with page.expect_download() as download_info:
                    await span.click()
                download = await download_info.value
                await download.save_as(filepath)
        finally:
            await browser.close()
    return filepath
