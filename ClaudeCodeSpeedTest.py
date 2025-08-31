#!/usr/bin/env python3
"""
Claude Code API 线路性能测试工具
Github:jsrcode
"""

import asyncio
import aiohttp
import time
import statistics
import configparser
import os
import sys
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TaskID
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich import box
from rich.columns import Columns

@dataclass
class TestResult:
    success: bool
    total_time: float
    first_byte_time: float
    error: str
    thread_id: int

class ConcurrentRouteTest:
    def __init__(self, config_path: str = "config.ini"):
        self.console = Console()
        self.config_path = config_path
        self.routes = {}
        self.auth_token = ""
        
        self.results = []
        self.stats_lock = threading.Lock()
        self.load_config()

    def create_default_config(self) -> None:
        """创建默认配置文件"""
        config = configparser.ConfigParser()
        
        # 添加默认配置
        config['DEFAULT'] = {
            'timeout': '30',
            'test_count': '10',
            'delay_between_tests': '0.2',
            'model': 'claude-3-5-haiku-20241022',
            'content': 'Hello'
        }
        
        # 并发配置
        config['concurrent'] = {
            'max_concurrent_routes': '3',
            'max_concurrent_per_route': '5',
            'use_async': 'true',
            'connection_pool_size': '100'
        }
        
        config['routes'] = {}
        
        # 默认线路配置
        routes_config = [
            ('route_Main', '主线路', 'https://anyrouter.top/v1/messages', 'Main'),
            ('route_CDN', 'CDN线路', 'https://pmpjfbhq.cn-nb1.rainapp.top/v1/messages', 'CDN'),
        ]
        
        for section_name, name, url, desc in routes_config:
            config[section_name] = {
                'name': name,
                'url': url,
                'description': desc,
                'enabled': 'true' if section_name != 'route_us_west' else 'false'
            }
        
        with open(self.config_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)

    def load_config(self) -> None:
        """加载配置文件"""
        if not os.path.exists(self.config_path):
            self.console.print(f"[yellow]配置文件 {self.config_path} 不存在，正在创建默认配置...")
            self.create_default_config()
        
        try:
            config = configparser.ConfigParser()
            config.read(self.config_path, encoding='utf-8')
            
            # 加载路由配置
            for section_name in config.sections():
                if section_name.startswith('route_') and config.getboolean(section_name, 'enabled', fallback=True):
                    route_info = {
                        'name': config.get(section_name, 'name'),
                        'url': config.get(section_name, 'url'),
                        'description': config.get(section_name, 'description', fallback=''),
                    }
                    self.routes[route_info['name']] = route_info
            
            # 加载测试配置
            self.timeout = config.getint('DEFAULT', 'timeout', fallback=30)
            self.test_count = config.getint('DEFAULT', 'test_count', fallback=10)
            self.delay = config.getfloat('DEFAULT', 'delay_between_tests', fallback=0.2)
			
			
            # 加载请求负载配置
            self.payload = {
                "model": config.get('DEFAULT', 'model', fallback="claude-3-5-haiku-20241022"),
                "max_tokens": 1024,
                "stream": True,
                "messages": [
                    {
                        "role": "user",
                        "content": config.get('DEFAULT', 'content', fallback="Hello")
                    }
                ]
            }
            
            # 加载并发配置
            if config.has_section('concurrent'):
                self.max_concurrent_routes = config.getint('concurrent', 'max_concurrent_routes', fallback=3)
                self.max_concurrent_per_route = config.getint('concurrent', 'max_concurrent_per_route', fallback=5)
                self.use_async = config.getboolean('concurrent', 'use_async', fallback=True)
                self.connection_pool_size = config.getint('concurrent', 'connection_pool_size', fallback=100)
            
        except Exception as e:
            self.console.print(f"[red]配置文件加载失败: {e}")
            sys.exit(1)

    def show_banner(self) -> None:
        """显示启动横幅"""
        width = self.console.size.width
        banner_width = min(80, width - 4)
        
        banner_text = Text("Claude Code API 线路性能测试工具", style="bold cyan")
        subtitle_text = Text("V1.1.0 Github:jsrcode", style="italic dim")
        help_text = Text("开发赞助方:anyrouter,anyhelp", style="italic dim")
        
        banner_panel = Panel(
            Align.center(f"{banner_text}\n{subtitle_text}\n{help_text}"),
            box=box.DOUBLE,
            border_style="cyan",
            padding=(1, 2),
            width=banner_width
        )
        
        self.console.print()
        self.console.print(Align.center(banner_panel))
        self.console.print()

    def show_config_info(self) -> None:
        """显示配置信息"""
        config_table = Table.grid(padding=1)
        config_table.add_column(style="cyan", justify="right", width=20)
        config_table.add_column(style="white", width=15)
        
        config_table.add_row("📊 每线路测试次数:", f"{self.test_count}")
        config_table.add_row("🚀 线路并发数:", f"{self.max_concurrent_routes}")
        config_table.add_row("⚡ 单线路并发数:", f"{self.max_concurrent_per_route}")
        config_table.add_row("🔄 异步模式:", f"{'✅ 是' if self.use_async else '❌ 否'}")
        config_table.add_row("⏱ 请求间隔:", f"{self.delay}s")
        config_table.add_row("⏰ 超时时间:", f"{self.timeout}s")
        
        config_panel = Panel(
            config_table, 
            title="⚙ 测试配置", 
            border_style="blue", 
            box=box.ROUNDED,
            width=40
        )
        
        # 线路信息表格
        routes_table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
        routes_table.add_column("", style="cyan", width=4, justify="center")
        routes_table.add_column("线路名称", style="green bold", width=16)
        routes_table.add_column("服务器地址", style="blue", width=35)
        routes_table.add_column("描述", style="dim", width=20)
        
        for i, (name, info) in enumerate(self.routes.items(), 1):
            host = info['url'].split('//')[1].split('/')[0]
            # 处理显示长度
            name_display = name if len(name) <= 14 else name[:11] + "..."
            host_display = host if len(host) <= 33 else host[:30] + "..."
            desc_display = info['description'] if len(info['description']) <= 18 else info['description'][:15] + "..."
            
            routes_table.add_row(
                str(i), 
                name_display, 
                host_display, 
                desc_display
            )
        
        routes_panel = Panel(
            routes_table, 
            title="📡 测试线路", 
            border_style="green", 
            box=box.ROUNDED,
            width=80
        )
        
        # 显示对齐
        self.console.print(Columns([config_panel, routes_panel], equal=False, expand=False))
        self.console.print()

    def get_auth_token(self) -> bool:
        """获取认证令牌"""
        auth_panel = Panel(
            "[bold yellow]🔐 身份验证[/bold yellow]\n"
            "[dim]请输入您的 Claude API Authorization token[/dim]",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(1, 2)
        )
        
        self.console.print(auth_panel)
        
        token = Prompt.ask(
            "[cyan]Token (sk-开头)[/cyan]"
        )
        
        if not token.startswith('sk-'):
            error_panel = Panel(
                "[red]❌ 错误：Token 应该以 'sk-' 开头[/red]",
                border_style="red",
                box=box.ROUNDED
            )
            self.console.print(error_panel)
            return False
        
        success_panel = Panel(
            "[green]✅ Token 验证通过[/green]",
            border_style="green",
            box=box.ROUNDED
        )
        self.console.print(success_panel)
        
        self.auth_token = token
        return True

    async def test_single_request_async(self, session: aiohttp.ClientSession, url: str) -> TestResult:
        """异步测试单个请求"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.auth_token
        }
        
        thread_id = threading.get_ident()
        
        try:
            start_time = time.perf_counter()
            
            async with session.post(url, json=self.payload, headers=headers, timeout=self.timeout) as response:
                if response.status != 200:
                    return TestResult(False, 0, 0, f"HTTP {response.status}", thread_id)
                
                first_byte_time = None
                content_received = False
                
                # 读取第一个数据块来测量首字节时间
                async for chunk in response.content.iter_chunked(1024):
                    if chunk and first_byte_time is None:
                        first_byte_time = time.perf_counter()
                        content_received = True
                        break
                
                if not content_received or first_byte_time is None:
                    return TestResult(False, 0, 0, "No response data", thread_id)
                
                # 读取剩余内容
                async for _ in response.content.iter_chunked(8192):
                    pass
                
                total_time = time.perf_counter() - start_time
                first_byte_duration = first_byte_time - start_time
                
                return TestResult(True, total_time, first_byte_duration, "", thread_id)
                
        except asyncio.TimeoutError:
            return TestResult(False, 0, 0, "Timeout", thread_id)
        except aiohttp.ClientError as e:
            return TestResult(False, 0, 0, f"Client Error: {str(e)}", thread_id)
        except Exception as e:
            return TestResult(False, 0, 0, str(e), thread_id)

    def test_single_request_sync(self, url: str) -> TestResult:
        """同步测试单个请求"""
        import requests
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.auth_token
        }
        
        thread_id = threading.get_ident()
        
        try:
            start_time = time.perf_counter()
            
            response = requests.post(
                url,
                json=self.payload,
                headers=headers,
                stream=True,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return TestResult(False, 0, 0, f"HTTP {response.status_code}", thread_id)
            
            first_byte_time = None
            content_received = False
            
            for chunk in response.iter_content(chunk_size=1, decode_unicode=False):
                if chunk and first_byte_time is None:
                    first_byte_time = time.perf_counter()
                    content_received = True
                    break
            
            if not content_received or first_byte_time is None:
                return TestResult(False, 0, 0, "No response data", thread_id)
            
            # 消费剩余数据
            for _ in response.iter_content(chunk_size=8192):
                pass
            
            total_time = time.perf_counter() - start_time
            first_byte_duration = first_byte_time - start_time
            
            return TestResult(True, total_time, first_byte_duration, "", thread_id)
            
        except requests.exceptions.Timeout:
            return TestResult(False, 0, 0, "Timeout", thread_id)
        except requests.exceptions.ConnectionError:
            return TestResult(False, 0, 0, "Connection Error", thread_id)
        except Exception as e:
            return TestResult(False, 0, 0, str(e), thread_id)

    async def test_route_async(self, route_name: str, route_info: Dict, progress: Progress, task_id: TaskID) -> Dict:
        """异步测试指定线路"""
        connector = aiohttp.TCPConnector(limit=self.connection_pool_size, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # 创建并发任务
            semaphore = asyncio.Semaphore(self.max_concurrent_per_route)
            
            async def limited_test():
                async with semaphore:
                    result = await self.test_single_request_async(session, route_info['url'])
                    progress.advance(task_id)
                    await asyncio.sleep(self.delay)
                    return result
            
            # 执行并发测试
            tasks = [limited_test() for _ in range(self.test_count)]
            test_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        results = {
            'route_name': route_name,
            'url': route_info['url'],
            'description': route_info['description'],
            'success_count': 0,
            'fail_count': 0,
            'total_times': [],
            'first_byte_times': [],
            'errors': [],
            'concurrent_threads': set()
        }
        
        for result in test_results:
            if isinstance(result, TestResult):
                results['concurrent_threads'].add(result.thread_id)
                if result.success:
                    results['success_count'] += 1
                    results['total_times'].append(result.total_time)
                    results['first_byte_times'].append(result.first_byte_time)
                else:
                    results['fail_count'] += 1
                    results['errors'].append(result.error)
            else:
                results['fail_count'] += 1
                results['errors'].append(str(result))
        
        return results

    def test_route_sync(self, route_name: str, route_info: Dict, progress: Progress, task_id: TaskID) -> Dict:
        """同步多线程测试指定线路"""
        results = {
            'route_name': route_name,
            'url': route_info['url'],
            'description': route_info['description'],
            'success_count': 0,
            'fail_count': 0,
            'total_times': [],
            'first_byte_times': [],
            'errors': [],
            'concurrent_threads': set()
        }
        
        def single_test():
            result = self.test_single_request_sync(route_info['url'])
            time.sleep(self.delay)
            progress.advance(task_id)
            return result
        
        # 使用线程池执行并发测试
        with ThreadPoolExecutor(max_workers=self.max_concurrent_per_route) as executor:
            futures = [executor.submit(single_test) for _ in range(self.test_count)]
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results['concurrent_threads'].add(result.thread_id)
                    if result.success:
                        results['success_count'] += 1
                        results['total_times'].append(result.total_time)
                        results['first_byte_times'].append(result.first_byte_time)
                    else:
                        results['fail_count'] += 1
                        results['errors'].append(result.error)
                except Exception as e:
                    results['fail_count'] += 1
                    results['errors'].append(str(e))
        
        return results

    def calculate_stats(self, times: List[float]) -> Dict:
        """计算统计数据"""
        if not times:
            return {'avg': 0, 'min': 0, 'max': 0, 'median': 0}
        
        return {
            'avg': statistics.mean(times),
            'min': min(times),
            'max': max(times),
            'median': statistics.median(times)
        }

    async def run_tests_async(self) -> None:
        """异步运行所有测试"""
        if not self.routes:
            self.console.print("[red]❌ 没有配置的测试线路")
            return
        
        total_tests = len(self.routes) * self.test_count
        # 耗时计算：
        # 1. 超时情况下的最长时间：超时时间 * 请求间隔 * 2（重试两次）+超时时间 * 2（重试两次）
        # 2. 考虑线路并发：取整(节点数量/线路并发数)
        import math

        routes_count = len(self.routes)
        concurrent_batches = math.ceil(routes_count / self.max_concurrent_routes)

        estimated_time = self.timeout * concurrent_batches + self.delay * 2 * self.timeout * concurrent_batches

        confirm_panel = Panel(
        	f"[yellow]将并发测试 {len(self.routes)} 个线路，每个线路 {self.test_count} 次请求\n"
        	f"总计 {total_tests} 个请求，预计最长耗时约 {estimated_time/60:.1f} 分钟[/yellow]",
        	title="🚀 测试确认",
        	border_style="yellow",
        	box=box.ROUNDED
        )
        self.console.print(confirm_panel)
        
        if not Confirm.ask("是否继续?"):
            self.console.print("[yellow]已取消测试")
            return
        
        start_time = time.time()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}", justify="left"),
            BarColumn(bar_width=30),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeElapsedColumn(),
            console=self.console,
            expand=True
        ) as progress:
            
            # 创建任务
            tasks = {}
            for route_name in self.routes.keys():
                # 限制显示的线路名称长度
                display_name = route_name[:10] + "..." if len(route_name) > 10 else route_name
                task_id = progress.add_task(f"[green]{display_name}", total=self.test_count)
                tasks[route_name] = task_id
            
            # 使用信号量控制并发线路数
            semaphore = asyncio.Semaphore(self.max_concurrent_routes)
            
            async def test_with_semaphore(route_name, route_info):
                async with semaphore:
                    return await self.test_route_async(route_name, route_info, progress, tasks[route_name])
            
            # 创建所有线路的并发任务
            route_tasks = [
                test_with_semaphore(route_name, route_info)
                for route_name, route_info in self.routes.items()
            ]
            
            # 执行并发测试
            route_results = await asyncio.gather(*route_tasks)
            
            # 处理结果
            for result in route_results:
                self.results.append(result)
                
                # 显示单个线路结果 - 格式化对齐
                success_rate = (result['success_count'] / self.test_count) * 100
                concurrent_count = len(result['concurrent_threads'])
                
                if result['first_byte_times']:
                    avg_first_byte = statistics.mean(result['first_byte_times']) * 1000
                    avg_total = statistics.mean(result['total_times']) * 1000
                    status = "✅" if success_rate >= 90 else "⚠️" if success_rate >= 70 else "❌"
                    
                    # 格式化输出，确保对齐
                    route_display = result['route_name'][:12].ljust(12)
                    progress.console.print(
                        f"  {status} {route_display}: "
                        f"成功率 [green]{success_rate:5.1f}%[/green], "
                        f"首字 [cyan]{avg_first_byte:6.0f}ms[/cyan], "
                        f"总时 [blue]{avg_total:6.0f}ms[/blue], "
                        f"并发 [yellow]{concurrent_count:2d}[/yellow]"
                    )
                else:
                    route_display = result['route_name'][:12].ljust(12)
                    progress.console.print(f"  ❌ {route_display}: [red]测试失败[/red]")
        
        end_time = time.time()
        
        # 完成提示面板
        complete_panel = Panel(
            f"[green]🎉 所有并发测试完成！[/green]\n"
            f"总耗时: [cyan]{end_time - start_time:.1f}[/cyan] 秒",
            title="✅ 测试完成",
            border_style="green",
            box=box.ROUNDED
        )
        self.console.print()
        self.console.print(complete_panel)

    def run_tests_sync(self) -> None:
        """同步多线程运行所有测试"""
        if not self.routes:
            self.console.print("[red]❌ 没有配置的测试线路")
            return
        
        total_tests = len(self.routes) * self.test_count
        estimated_time = total_tests * self.delay / self.max_concurrent_per_route / self.max_concurrent_routes
        
        confirm_panel = Panel(
            f"[yellow]将并发测试 {len(self.routes)} 个线路，每个线路 {self.test_count} 次请求\n"
            f"总计 {total_tests} 个请求，预计耗时约 {estimated_time/60:.1f} 分钟[/yellow]",
            title="🚀 测试确认",
            border_style="yellow",
            box=box.ROUNDED
        )
        self.console.print(confirm_panel)
        
        if not Confirm.ask("是否继续?"):
            self.console.print("[yellow]已取消测试")
            return
        
        start_time = time.time()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}", justify="left"),
            BarColumn(bar_width=30),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeElapsedColumn(),
            console=self.console,
            expand=True
        ) as progress:
            
            # 创建任务
            tasks = {}
            for route_name in self.routes.keys():
                # 限制显示的线路名称长度，确保对齐
                display_name = route_name[:10] + "..." if len(route_name) > 10 else route_name
                task_id = progress.add_task(f"[green]{display_name}", total=self.test_count)
                tasks[route_name] = task_id
            
            # 使用线程池控制并发线路数
            with ThreadPoolExecutor(max_workers=self.max_concurrent_routes) as executor:
                futures = {
                    executor.submit(self.test_route_sync, route_name, route_info, progress, tasks[route_name]): route_name
                    for route_name, route_info in self.routes.items()
                }
                
                for future in as_completed(futures):
                    route_name = futures[future]
                    try:
                        result = future.result()
                        self.results.append(result)
                        
                        # 显示单个线路结果 - 格式化对齐
                        success_rate = (result['success_count'] / self.test_count) * 100
                        concurrent_count = len(result['concurrent_threads'])
                        
                        if result['first_byte_times']:
                            avg_first_byte = statistics.mean(result['first_byte_times']) * 1000
                            avg_total = statistics.mean(result['total_times']) * 1000
                            status = "✅" if success_rate >= 90 else "⚠️" if success_rate >= 70 else "❌"
                            
                            # 格式化输出，确保对齐
                            route_display = result['route_name'][:12].ljust(12)
                            progress.console.print(
                                f"  {status} {route_display}: "
                                f"成功率 [green]{success_rate:5.1f}%[/green], "
                                f"首字 [cyan]{avg_first_byte:6.0f}ms[/cyan], "
                                f"总时 [blue]{avg_total:6.0f}ms[/blue], "
                                f"并发 [yellow]{concurrent_count:2d}[/yellow]"
                            )
                        else:
                            route_display = result['route_name'][:12].ljust(12)
                            progress.console.print(f"  ❌ {route_display}: [red]测试失败[/red]")
                    except Exception as e:
                        route_display = route_name[:12].ljust(12)
                        progress.console.print(f"  ❌ {route_display}: [red]测试异常 - {e}[/red]")
        
        end_time = time.time()
        
        # 完成提示面板
        complete_panel = Panel(
            f"[green]🎉 所有并发测试完成！[/green]\n"
            f"总耗时: [cyan]{end_time - start_time:.1f}[/cyan] 秒",
            title="✅ 测试完成",
            border_style="green",
            box=box.ROUNDED
        )
        self.console.print()
        self.console.print(complete_panel)

    def generate_report(self) -> None:
        """生成测试报告"""
        if not self.results:
            self.console.print("[red]没有测试结果")
            return
        
        # 创建结果表格
        table = Table(
            title="📊 并发测试结果汇总", 
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            title_style="bold magenta"
        )
        
        table.add_column("线路名称", style="green bold", width=12, no_wrap=True)
        table.add_column("服务器", style="blue", width=28, no_wrap=True)
        table.add_column("成功率", justify="center", width=8)
        table.add_column("首字时间", justify="center", width=10)
        table.add_column("总响应时间", justify="center", width=12)
        table.add_column("并发数", justify="center", width=8)
        table.add_column("状态", justify="center", width=8)
        
        # 按成功率和响应时间排序
        sorted_results = sorted(
            self.results,
            key=lambda x: (
                x['success_count'],
                -self.calculate_stats(x['first_byte_times'])['avg'] if x['first_byte_times'] else 999
            ),
            reverse=True
        )
        
        best_route = None
        best_score = -1
        
        for result in sorted_results:
            route_name = result['route_name'][:10] + "..." if len(result['route_name']) > 10 else result['route_name']
            server = result['url'].split('//')[1].split('/')[0]
            server_display = server[:26] + "..." if len(server) > 26 else server
            success_rate = (result['success_count'] / self.test_count) * 100
            concurrent_count = len(result['concurrent_threads'])
            
            # 计算性能评分
            if result['success_count'] > 0:
                success_ratio = result['success_count'] / self.test_count
                avg_first_byte = statistics.mean(result['first_byte_times']) if result['first_byte_times'] else 999
                score = success_ratio * 0.7 + (1 / (avg_first_byte + 0.1)) * 0.3
                
                if score > best_score:
                    best_score = score
                    best_route = result
            
            # 设置行样式
            if success_rate >= 90:
                rate_style = "green"
                status = "🟢 优秀"
            elif success_rate >= 70:
                rate_style = "yellow"
                status = "🟡 良好"
            else:
                rate_style = "red"
                status = "🔴 较差"
            
            if result['first_byte_times'] and result['total_times']:
                first_byte_stats = self.calculate_stats(result['first_byte_times'])
                total_stats = self.calculate_stats(result['total_times'])
                avg_first = f"{first_byte_stats['avg']*1000:.0f}ms"
                avg_total = f"{total_stats['avg']*1000:.0f}ms"
            else:
                avg_first = "超时"
                avg_total = "超时"
            
            table.add_row(
                route_name,
                server_display,
                f"[{rate_style}]{success_rate:.1f}%[/{rate_style}]",
                avg_first,
                avg_total,
                f"{concurrent_count}",
                status
            )
        
        self.console.print()
        self.console.print(table)
        
        # 并发性能统计
        total_threads = sum(len(result['concurrent_threads']) for result in self.results)
        avg_threads_per_route = total_threads / len(self.results) if self.results else 0
        
        # 统计信息表格
        stats_table = Table.grid(padding=1)
        stats_table.add_column(style="cyan", justify="right", width=16)
        stats_table.add_column(style="white", width=12)
        
        stats_table.add_row("🚀 并发模式:", f"{'异步' if self.use_async else '多线程'}")
        stats_table.add_row("📊 总并发线程:", f"{total_threads}")
        stats_table.add_row("⚡ 平均线程数:", f"{avg_threads_per_route:.1f}")
        stats_table.add_row("🔄 线路并发:", f"{self.max_concurrent_routes}")
        stats_table.add_row("⚙ 单线路并发:", f"{self.max_concurrent_per_route}")
        
        concurrent_stats = Panel(
            stats_table,
            title="📈 并发性能统计",
            border_style="yellow",
            box=box.ROUNDED,
            width=35
        )
        
        # 显示推荐线路
        if best_route:
            avg_first_byte = statistics.mean(best_route['first_byte_times']) * 1000
            avg_total = statistics.mean(best_route['total_times']) * 1000
            success_rate = (best_route['success_count'] / self.test_count) * 100
            
            # 推荐信息内容
            recommendation_content = (
                f"[bold green]🏆 推荐线路[/bold green]\n"
                f"[bold]{best_route['route_name']}[/bold]\n\n"
                f"[cyan]📊 首字时间:[/cyan] {avg_first_byte:.0f}ms\n"
                f"[cyan]⏱ 总响应时间:[/cyan] {avg_total:.0f}ms\n"
                f"[cyan]✅ 成功率:[/cyan] {success_rate:.1f}%\n"
                f"[cyan]🚀 并发数:[/cyan] {len(best_route['concurrent_threads'])}\n"
                f"[cyan]📝 描述:[/cyan] {best_route['description'][:25]}"
            )
            
            recommendation = Panel(
                recommendation_content,
                title="💡 性能推荐",
                border_style="green",
                box=box.ROUNDED,
                width=35
            )
            
            # 并排显示统计和推荐
            self.console.print()
            self.console.print(Columns([concurrent_stats, recommendation], equal=True))

    def run(self) -> None:
        """主运行方法"""
        self.show_banner()
        
        # 显示配置文件路径
        config_path = Path(self.config_path).absolute()
        path_panel = Panel(
            f"[dim]📁 配置文件: {config_path}[/dim]",
            border_style="dim",
            box=box.SIMPLE
        )
        self.console.print(path_panel)
        self.console.print()
        
        self.show_config_info()
        
        if not self.get_auth_token():
            return
        
        self.console.print()
        
        # 根据配置选择并发模式
        if self.use_async:
            asyncio.run(self.run_tests_async())
        else:
            self.run_tests_sync()
        
        self.generate_report()

def main():
    """主函数"""
    try:
        tester = ConcurrentRouteTest()
        tester.run()
    except KeyboardInterrupt:
        Console().print("\n[yellow]⚠️ 用户中断操作[/yellow]")
    except Exception as e:
        Console().print(f"\n[red]❌ 程序出错: {e}[/red]")
        import traceback
        Console().print(f"[dim]{traceback.format_exc()}[/dim]")

if __name__ == "__main__":
    main()