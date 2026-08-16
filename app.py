#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import socket
import struct
import hashlib
import base64
import asyncio
import aiohttp
import logging
import ipaddress
import subprocess
import platform
from aiohttp import web

# ==================== 环境变量 ====================
UUID = os.environ.get('UUID', '021e1223-7032-4fdf-8e3b-90e190f89b32')
DOMAIN = os.environ.get('DOMAIN', 'mghosting.cnav.cn.eu.org')
SUB_PATH = os.environ.get('SUB_PATH', 'hello-word')
NAME = os.environ.get('NAME', 'mghosting')
WSPATH = os.environ.get('WSPATH', UUID[:8])
PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or 3000)
AUTO_ACCESS = os.environ.get('AUTO_ACCESS', '').lower() == 'true'
DEBUG = os.environ.get('DEBUG', '').lower() == 'true'
CLOUDFLARED_TOKEN = os.environ.get('CLOUDFLARED_TOKEN', 'eyJhIjoiZDZlNGIzNDY3N2MzNjljOTViODM3YTcxNWFjZWNjYzciLCJ0IjoiMjBlY2Y0N2QtOGQwNy00MjNlLTljNGMtZmU5MDVlN2MxZDQ0IiwicyI6Ik4yTmtaR05tWW1ZdE5UZGlZUzAwTW1Ka0xUZzVNalF0TWpsaE1qZG1ZV0kxTVdSbCJ9')


# 全局变量
CurrentDomain = DOMAIN
CurrentPort = 443
Tls = 'tls'
ISP = ''

DNS_SERVERS = ['8.8.4.4', '1.1.1.1']
BLOCKED_DOMAINS = [
    'speedtest.net', 'fast.com', 'speedtest.cn', 'speed.cloudflare.com', 'speedof.me',
    'testmy.net', 'bandwidth.place', 'speed.io', 'librespeed.org', 'speedcheck.org'
]

# ==================== 日志配置 ====================
log_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')
for name in ['aiohttp.access', 'aiohttp.server', 'aiohttp.client', 'aiohttp.internal', 'aiohttp.websocket']:
    logging.getLogger(name).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ==================== 页面 HTML ====================
FAKE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alex's Tech Blog - 记录技术与生活</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f5f5f5; color: #333; line-height: 1.6; }
        header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 2rem 0; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        header h1 { font-size: 2rem; margin-bottom: 0.5rem; }
        header p { opacity: 0.9; font-size: 1.1rem; }
        nav { background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.05); position: sticky; top: 0; z-index: 100; }
        nav ul { list-style: none; display: flex; justify-content: center; flex-wrap: wrap; max-width: 800px; margin: 0 auto; }
        nav li { margin: 0; }
        nav a { display: block; padding: 1rem 1.5rem; text-decoration: none; color: #555; font-weight: 500; transition: color 0.3s; }
        nav a:hover { color: #667eea; }
        .container { max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
        .post { background: white; border-radius: 12px; padding: 2rem; margin-bottom: 2rem; box-shadow: 0 2px 15px rgba(0,0,0,0.05); transition: transform 0.2s; }
        .post:hover { transform: translateY(-3px); box-shadow: 0 5px 25px rgba(0,0,0,0.1); }
        .post h2 { color: #333; margin-bottom: 0.5rem; font-size: 1.5rem; }
        .meta { color: #999; font-size: 0.9rem; margin-bottom: 1rem; }
        .post p { color: #555; margin-bottom: 1rem; }
        .tag { display: inline-block; background: #f0f0f0; color: #666; padding: 0.2rem 0.8rem; border-radius: 20px; font-size: 0.85rem; margin-right: 0.5rem; }
        footer { text-align: center; padding: 2rem; color: #999; font-size: 0.9rem; margin-top: 3rem; border-top: 1px solid #eee; }
        @media (max-width: 600px) { header h1 { font-size: 1.5rem; } .post { padding: 1.5rem; } }
    </style>
</head>
<body>
    <header>
        <h1>Alex's Tech Blog</h1>
        <p>分享编程、开源与数码生活</p>
    </header>
    <nav>
        <ul>
            <li><a href="/">首页</a></li>
            <li><a href="/">文章</a></li>
            <li><a href="/">项目</a></li>
            <li><a href="/">关于</a></li>
        </ul>
    </nav>
    <div class="container">
        <article class="post">
            <h2>使用 Python 构建高性能异步服务</h2>
            <div class="meta">2026-08-10 · 阅读 2,341 · Python</div>
            <p>在现代 Web 开发中，异步编程已经成为提升并发能力的关键技术。本文将深入探讨 asyncio 与 aiohttp 的最佳实践，帮助你构建能够支撑数万并发连接的服务...</p>
            <span class="tag">Python</span>
            <span class="tag">Async</span>
            <span class="tag">Backend</span>
        </article>
        <article class="post">
            <h2>我的 Homelab 搭建日记：从 0 到 All-in-One</h2>
            <div class="meta">2026-07-28 · 阅读 4,128 · 数码</div>
            <p>最近把家里闲置的 NUC 改造成了 All-in-One 服务器，跑了 Docker、NAS、智能家居中枢。这篇文章记录了硬件选型、系统部署和踩坑全过程...</p>
            <span class="tag">Homelab</span>
            <span class="tag">Docker</span>
            <span class="tag">NAS</span>
        </article>
        <article class="post">
            <h2>Git 工作流进阶：Rebase 还是 Merge？</h2>
            <div class="meta">2026-07-15 · 阅读 1,892 · 工具</div>
            <p>团队协作中，分支管理策略往往决定了代码历史的整洁程度。今天我们来聊聊什么时候该用 rebase，什么时候该保留 merge commit，以及如何优雅地解决冲突...</p>
            <span class="tag">Git</span>
            <span class="tag">DevOps</span>
        </article>
    </div>
    <footer>
        <p> Alex's Tech Blog · Powered by Python & Love</p>
    </footer>
</body>
</html>"""

# ==================== 工具函数 ====================
def is_port_available(port, host='0.0.0.0'):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False

def find_available_port(start_port, max_attempts=100):
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port):
            return port
    return None

def is_blocked_domain(host: str) -> bool:
    if not host:
        return False
    host_lower = host.lower()
    return any(host_lower == blocked or host_lower.endswith('.' + blocked)
               for blocked in BLOCKED_DOMAINS)

async def get_isp():
    global ISP
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('https://api.ip.sb/geoip',
                                   headers={'User-Agent': 'Mozilla/5.0'}, timeout=3) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ISP = f"{data.get('country_code', '')}-{data.get('isp', '')}".replace(' ', '_')
                    return
    except:
        pass
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://ip-api.com/json',
                                   headers={'User-Agent': 'Mozilla/5.0'}, timeout=3) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ISP = f"{data.get('countryCode', '')}-{data.get('org', '')}".replace(' ', '_')
                    return
    except:
        pass
    ISP = 'Unknown'

async def get_ip():
    global CurrentDomain, Tls, CurrentPort
    if not DOMAIN or DOMAIN == 'your-domain.com':
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api-ipv4.ip.sb/ip', timeout=5) as resp:
                    if resp.status == 200:
                        ip = await resp.text()
                        CurrentDomain = ip.strip()
                        Tls = 'none'
                        CurrentPort = PORT
        except Exception as e:
            logger.error(f'Failed to get IP: {e}')
            CurrentDomain = 'change-your-domain.com'
            Tls = 'tls'
            CurrentPort = 443
    else:
        CurrentDomain = DOMAIN
        Tls = 'tls'
        CurrentPort = 443

async def resolve_host(host: str) -> str:
    try:
        ipaddress.ip_address(host)
        return host
    except:
        pass
    for dns_server in DNS_SERVERS:
        try:
            async with aiohttp.ClientSession() as session:
                url = f'https://dns.google/resolve?name={host}&type=A'
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get('Status') == 0 and data.get('Answer'):
                            for answer in data['Answer']:
                                if answer.get('type') == 1:
                                    return answer.get('data')
        except:
            continue
    return host

# ==================== Trojan 代理处理器 ====================
class ProxyHandler:
    def __init__(self, uuid: str):
        self.uuid = uuid
        self.uuid_bytes = bytes.fromhex(uuid)

    async def handle_trojan(self, websocket, first_msg: bytes) -> bool:
        try:
            if len(first_msg) < 58:
                return False
            received_hash_bytes = first_msg[:56]

            hash_obj1 = hashlib.sha224()
            hash_obj1.update(self.uuid.encode())
            expected_hash_hex1 = hash_obj1.hexdigest()

            standard_uuid = UUID
            hash_obj2 = hashlib.sha224()
            hash_obj2.update(standard_uuid.encode())
            expected_hash_hex2 = hash_obj2.hexdigest()

            received_hash_hex = received_hash_bytes.decode('ascii', errors='ignore')
            if received_hash_hex != expected_hash_hex1 and received_hash_hex != expected_hash_hex2:
                return False

            offset = 56
            if first_msg[offset:offset+2] == b'\r\n':
                offset += 2

            cmd = first_msg[offset]
            if cmd != 1:
                return False
            offset += 1

            atyp = first_msg[offset]
            offset += 1

            host = ''
            if atyp == 1:
                host = '.'.join(str(b) for b in first_msg[offset:offset+4])
                offset += 4
            elif atyp == 3:
                host_len = first_msg[offset]
                offset += 1
                host = first_msg[offset:offset+host_len].decode()
                offset += host_len
            elif atyp == 4:
                host = ':'.join(f'{(first_msg[j] << 8) + first_msg[j+1]:04x}'
                                for j in range(offset, offset+16, 2))
                offset += 16
            else:
                return False

            port = struct.unpack('!H', first_msg[offset:offset+2])[0]
            offset += 2
            if first_msg[offset:offset+2] == b'\r\n':
                offset += 2

            if is_blocked_domain(host):
                await websocket.close()
                return False

            resolved_host = await resolve_host(host)
            try:
                reader, writer = await asyncio.open_connection(resolved_host, port)
                if offset < len(first_msg):
                    writer.write(first_msg[offset:])
                    await writer.drain()

                async def forward_ws_to_tcp():
                    try:
                        async for msg in websocket:
                            if msg.type == aiohttp.WSMsgType.BINARY:
                                writer.write(msg.data)
                                await writer.drain()
                    except:
                        pass
                    finally:
                        writer.close()
                        await writer.wait_closed()

                async def forward_tcp_to_ws():
                    try:
                        while True:
                            data = await reader.read(4096)
                            if not data:
                                break
                            await websocket.send_bytes(data)
                    except:
                        pass

                await asyncio.gather(forward_ws_to_tcp(), forward_tcp_to_ws())
            except Exception as e:
                if DEBUG:
                    logger.error(f"Connection error: {e}")
            return True
        except Exception as e:
            if DEBUG:
                logger.error(f"Trojan handler error: {e}")
            return False

# ==================== WebSocket 处理器 ====================
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    CUUID = UUID.replace('-', '')
    path = request.path

    if f'/{WSPATH}' not in path:
        await ws.close()
        return ws

    proxy = ProxyHandler(CUUID)
    try:
        first_msg = await asyncio.wait_for(ws.receive(), timeout=5)
        if first_msg.type != aiohttp.WSMsgType.BINARY:
            await ws.close()
            return ws
        msg_data = first_msg.data
        if len(msg_data) >= 58:
            if await proxy.handle_trojan(ws, msg_data):
                return ws
        await ws.close()
    except asyncio.TimeoutError:
        await ws.close()
    except Exception as e:
        if DEBUG:
            logger.error(f"WebSocket handler error: {e}")
        await ws.close()
    return ws

# ==================== HTTP 处理器 ====================
async def http_handler(request):
    # 伪装页面：根路径和常见路径
    if request.path in ('/', '/index.html', '/about', '/blog', '/posts'):
        return web.Response(text=FAKE_HTML, content_type='text/html')

    # 订阅路径
    if request.path == f'/{SUB_PATH}':
        await get_isp()
        await get_ip()
        name_part = f"{NAME}-{ISP}" if NAME else ISP
        tls_param = 'tls' if Tls == 'tls' else 'none'
        trojan_url = f"trojan://{UUID}@{CurrentDomain}:{CurrentPort}?security={tls_param}&sni={CurrentDomain}&fp=chrome&type=ws&host={CurrentDomain}&path=%2F{WSPATH}#{name_part}"
        base64_content = base64.b64encode(trojan_url.encode()).decode()
        return web.Response(text=base64_content + '\n', content_type='text/plain')

    return web.Response(status=404, text='Not Found\n')

# ==================== Cloudflared ====================
def get_cloudflared_url():
    arch = platform.machine().lower()
    if 'arm' in arch or 'aarch64' in arch:
        return 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64'
    else:
        return 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64'

async def download_cloudflared():
    if not CLOUDFLARED_TOKEN:
        return
    try:
        url = get_cloudflared_url()
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    with open('cloudflared', 'wb') as f:
                        f.write(content)
                    os.chmod('cloudflared', 0o755)
                    logger.info('✅ cloudflared downloaded successfully')
    except Exception as e:
        logger.error(f'cloudflared download failed: {e}')

async def run_cloudflared():
    if not CLOUDFLARED_TOKEN:
        return
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if './cloudflared' in result.stdout and 'tunnel' in result.stdout:
            logger.info('cloudflared is already running, skip...')
            return
    except:
        pass
    await download_cloudflared()
    command = f'nohup ./cloudflared tunnel --no-autoupdate run --token {CLOUDFLARED_TOKEN} >/dev/null 2>&1 &'
    try:
        subprocess.Popen(command, shell=True, executable='/bin/bash')
        logger.info('✅ cloudflared tunnel started successfully')
    except Exception as e:
        logger.error(f'Error running cloudflared: {e}')

# ==================== 保活任务 ====================
async def add_access_task():
    if not AUTO_ACCESS or not DOMAIN:
        return
    full_url = f"https://{DOMAIN}/{SUB_PATH}"
    try:
        async with aiohttp.ClientSession() as session:
            await session.post("https://oooo.serv00.net/add-url",
                               json={"url": full_url},
                               headers={'Content-Type': 'application/json'})
        logger.info('Automatic Access Task added successfully')
    except:
        pass

def cleanup_files():
    for file in ['cloudflared']:
        try:
            if os.path.exists(file):
                os.remove(file)
        except:
            pass

# ==================== 主函数 ====================
async def main():
    actual_port = PORT
    if not is_port_available(actual_port):
        logger.warning(f"Port {actual_port} is already in use, finding available port...")
        new_port = find_available_port(actual_port + 1)
        if new_port:
            actual_port = new_port
            logger.info(f"Using port {actual_port} instead of {PORT}")
        else:
            logger.error("No available ports found")
            sys.exit(1)

    app = web.Application()
    # 路由注册
    app.router.add_get('/', http_handler)
    app.router.add_get('/index.html', http_handler)
    app.router.add_get('/about', http_handler)
    app.router.add_get('/blog', http_handler)
    app.router.add_get('/posts', http_handler)
    app.router.add_get(f'/{SUB_PATH}', http_handler)
    app.router.add_get(f'/{WSPATH}', websocket_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', actual_port)
    await site.start()
    logger.info(f"✅ server is running on port {actual_port}")

    asyncio.create_task(run_cloudflared())

    async def delayed_cleanup():
        await asyncio.sleep(180)
        cleanup_files()
    asyncio.create_task(delayed_cleanup())

    await add_access_task()

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        pass
    finally:
        await runner.cleanup()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        cleanup_files()
