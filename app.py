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

# 环境变量
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

# dns server
DNS_SERVERS = ['8.8.4.4', '1.1.1.1']
BLOCKED_DOMAINS = [
    'speedtest.net', 'fast.com', 'speedtest.cn', 'speed.cloudflare.com', 'speedof.me',
    'testmy.net', 'bandwidth.place', 'speed.io', 'librespeed.org', 'speedcheck.org'
]

# 日志级别：正常只显示 WARNING 及以上，DEBUG 模式显示 DEBUG
log_level = logging.DEBUG if DEBUG else logging.WARNING
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 禁用访问,连接等日志
logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
logging.getLogger('aiohttp.server').setLevel(logging.WARNING)
logging.getLogger('aiohttp.client').setLevel(logging.WARNING)
logging.getLogger('aiohttp.internal').setLevel(logging.WARNING)
logging.getLogger('aiohttp.websocket').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

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
                                 headers={'User-Agent': 'Mozilla/5.0'},
                                 timeout=3) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    ISP = f"{data.get('country_code', '')}-{data.get('isp', '')}".replace(' ', '_')
                    return
    except:
        pass

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://ip-api.com/json',
                                 headers={'User-Agent': 'Mozilla/5.0'},
                                 timeout=3) as resp:
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
            logger.debug(f'Failed to get IP: {e}')
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

class ProxyHandler:
    def __init__(self, uuid: str):
        self.uuid = uuid
        self.uuid_bytes = bytes.fromhex(uuid)

    async def handle_trojan(self, websocket, first_msg: bytes) -> bool:
        """处理Trojan协议"""
        try:
            if len(first_msg) < 58:
                return False

            received_hash_bytes = first_msg[:56]

            # 验证密码 - 支持标准UUID和无短横线UUID
            hash_obj1 = hashlib.sha224()
            hash_obj1.update(self.uuid.encode())
            expected_hash_hex1 = hash_obj1.hexdigest()

            # 尝试使用标准UUID（带短横线）
            standard_uuid = UUID
            hash_obj2 = hashlib.sha224()
            hash_obj2.update(standard_uuid.encode())
            expected_hash_hex2 = hash_obj2.hexdigest()

            # 转换为hex字符串进行比较
            received_hash_hex = received_hash_bytes.decode('ascii', errors='ignore')

            # 检查是否匹配任一UUID格式
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

            # 解析地址
            host = ''
            if atyp == 1:  # IPv4
                host = '.'.join(str(b) for b in first_msg[offset:offset+4])
                offset += 4
            elif atyp == 3:  # 域名
                host_len = first_msg[offset]
                offset += 1
                host = first_msg[offset:offset+host_len].decode()
                offset += host_len
            elif atyp == 4:  # IPv6
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

            # 连接目标
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

                await asyncio.gather(
                    forward_ws_to_tcp(),
                    forward_tcp_to_ws()
                )

            except Exception as e:
                logger.debug(f"Connection error: {e}")

            return True

        except Exception as e:
            logger.debug(f"Trojan handler error: {e}")
            return False

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

        # 尝试Trojan
        if len(msg_data) >= 58:
            if await proxy.handle_trojan(ws, msg_data):
                return ws

        await ws.close()

    except asyncio.TimeoutError:
        await ws.close()
    except Exception as e:
        logger.debug(f"WebSocket handler error: {e}")
        await ws.close()

    return ws

async def http_handler(request):
    if request.path == '/':
        try:
            with open('index.html', 'r', encoding='utf-8') as f:
                content = f.read()
            return web.Response(text=content, content_type='text/html')
        except:
            return web.Response(text='Hello world!', content_type='text/html')

    elif request.path == f'/{SUB_PATH}':
        await get_isp()
        await get_ip()

        name_part = f"{NAME}-{ISP}" if NAME else ISP
        tls_param = 'tls' if Tls == 'tls' else 'none'

        # 生成Trojan配置链接
        trojan_url = f"trojan://{UUID}@{CurrentDomain}:{CurrentPort}?security={tls_param}&sni={CurrentDomain}&fp=chrome&type=ws&host={CurrentDomain}&path=%2F{WSPATH}#{name_part}"

        subscription = f"{trojan_url}"
        base64_content = base64.b64encode(subscription.encode()).decode()

        return web.Response(text=base64_content + '\n', content_type='text/plain')

    return web.Response(status=404, text='Not Found\n')

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
                    logger.debug('cloudflared downloaded successfully')
    except Exception as e:
        logger.debug(f'cloudflared download failed: {e}')

async def run_cloudflared():
    if not CLOUDFLARED_TOKEN:
        return

    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        if './cloudflared' in result.stdout and 'tunnel' in result.stdout:
            logger.debug('cloudflared is already running, skip...')
            return
    except:
        pass

    await download_cloudflared()

    command = f'nohup ./cloudflared tunnel --no-autoupdate run --token {CLOUDFLARED_TOKEN} >/dev/null 2>&1 &'

    try:
        subprocess.Popen(command, shell=True, executable='/bin/bash')
        # 隧道启动成功后删除二进制文件
        await asyncio.sleep(2)
        if os.path.exists('cloudflared'):
            try:
                os.remove('cloudflared')
                logger.debug('cloudflared binary removed after start')
            except Exception as e:
                logger.debug(f'Failed to remove cloudflared: {e}')
    except Exception as e:
        logger.debug(f'Error running cloudflared: {e}')

async def add_access_task():
    if not AUTO_ACCESS or not DOMAIN:
        return

    full_url = f"https://{DOMAIN}/{SUB_PATH}"
    try:
        async with aiohttp.ClientSession() as session:
            await session.post("https://oooo.serv00.net/add-url",
                             json={"url": full_url},
                             headers={'Content-Type': 'application/json'})
        logger.debug('Automatic Access Task added successfully')
    except:
        pass

def cleanup_files():
    for file in ['cloudflared']:
        try:
            if os.path.exists(file):
                os.remove(file)
        except:
            pass

async def main():
    actual_port = PORT

    # 检查端口是否可用，如果不可用则查找可用端口
    if not is_port_available(actual_port):
        logger.debug(f"Port {actual_port} is already in use, finding available port...")
        new_port = find_available_port(actual_port + 1)
        if new_port:
            actual_port = new_port
            logger.debug(f"Using port {actual_port} instead of {PORT}")
        else:
            logger.error("No available ports found")
            sys.exit(1)

    app = web.Application()

    # 路由
    app.router.add_get('/', http_handler)
    app.router.add_get(f'/{SUB_PATH}', http_handler)
    app.router.add_get(f'/{WSPATH}', websocket_handler)

    # 启动服务
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', actual_port)
    await site.start()

    # 只保留这一行控制台输出
    print(f"INFO - ✅ server is running on port {actual_port}", flush=True)

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
