"""
网关通用基础类
支持 mqtt回调,http心跳,http回调
设备状态维护
flask服务启动
配置文件维护
设备ip获取
数据文件回传
"""
import json
import os
import random
import socket
import threading
import time

from flask import Flask
import requests
import paho.mqtt.client as mqtt
from gevent import pywsgi

from logger_handler import create_logger
log = create_logger("INFO", "GetwayBase")

import psutil

"""mqtt开关"""
mqtt_enable = False

"""http回调开关"""
http_callback_enable = True

"""心跳开关"""
heartbeat_enable = True

"""在线检查开关"""
online_check_enable = False

"""设备状态锁"""
class MachineStatus:
    machine_status = 0
    machine_online_status = "ONLINE"
    lock_online = threading.Lock()
    lock = threading.Lock()

    def increase(self):
        with self.lock:
            self.machine_status = 1

    def decrease(self):
        with self.lock:
            self.machine_status = 0

    def reset(self):
        with self.lock:
            self.machine_status = 0

    def get_machine_status(self):
        if self.machine_online_status != "ONLINE":
            return "OFFLINE"
        with self.lock:
            if self.machine_status == 0:
                status = "IDLE"
            elif self.machine_status == 1:
                status = "BUSY"
            else:
                status = "ONLINE"
        return status

#网关异常
class GateWayError(Exception):
    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code

    def __str__(self):
        return f"[{self.error_code}] {super().__str__()}"

settings_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'settings.json'))

class GetwayBase:
    app = Flask(__name__)

    def __init__(self):
        self.mqtt_host = None
        self.machine_status = MachineStatus()
        self.heart_beat_callback = None
        self.instance_id = None
        self.pipeline_id = None

    def load_config(self, path = settings_path):            
        with open(path, 'r', encoding='utf-8') as f:
            self.app.config.from_mapping(json.load(f))

        """构造MQTT对象"""
        if mqtt_enable:
            self.mqtt_host = self.app.config.get('MQ')['MQTT_HOST']
            self.mqtt_port = self.app.config.get('MQ')['MQTT_PORT']
            self.mqtt_topic = self.topic_name = self.app.config.get('MQ')['TOPIC']
            self.client_id = self.app.config.get('MQ')['CLIENT_ID'] + str(random.randint(1000, 9999))
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.username_pw_set(username=self.app.config.get('MQ')['USER_NAME'],
                                        password=self.app.config.get('MQ')['PASSWORD'])
            
        self.target_ip = self.app.config.get('TARGET_IP')
        self.target_port = self.app.config.get('TARGET_PORT')

        self.target_ip_2 = self.app.config.get('TARGET_IP_2')
        self.target_port_2 = self.app.config.get('TARGET_PORT_2')

        # 操作过期时间
        self.operate_timeout = self.app.config.get('OPERATE_TIMEOUT')
        # 端口号
        self.port = self.app.config.get('PORT')
        # 设备编码
        self.url = self.app.config.get("URI")
        # 设备编码
        self.machine_code = self.app.config.get("MACHINE_CODE")
        # 设备编码2
        self.machine_code_2 = self.app.config.get("MACHINE_CODE_2")

        # 心跳上报地址
        self.heartbeat_url = self.app.config.get("HEARTBEAT_URL")

        # 心跳上报间隔
        self.heartbeat_time_interval = self.app.config.get("HEARTBEAT_LOG_TIME_INTERVAL")

        # 心跳日志间隔
        self.heartbeat_log_time_interval = 10

        # 心跳上报地址 2
        self.heartbeat_url_2 = self.app.config.get("HEARTBEAT_URL_2")

        # 结果上传地址
        self.upload_url = self.app.config.get("UPLOAD_URL")
        # 工作站编码
        self.work_station_code = self.app.config.get("WORKSTATION_CODE")

        # 禁用的网卡名称列表
        self.disable_net_str = self.app.config.get("DISABLE_NET_INTERFACES", "")
        self.disable_net_interfaces =  [iface.strip() for iface in self.disable_net_str.split(",") if iface.strip()]

        # 用户名密码
        self.username = self.app.config.get("USERNAME")
        self.password = self.app.config.get("PASSWORD")
        
        self.robot_url = self.app.config.get("ROBOT_URL")
        self.robot_id = self.app.config.get("ROBOT_ID")
        self.robot_callback_url = self.app.config.get("ROBOT_CALLBACK_URL")
        self.websocket_url = self.app.config.get("WEB_SOCKET_URL")
        self.files_folder = self.app.config.get("FILES_FOLDER")

        """http回调地址"""
        if http_callback_enable:
            """http回调地址1"""
            self.http_callback_url = self.app.config.get("HTTP_CALLBACK_URL")

            """http回调地址2"""
            self.http_callback_url_2 = self.app.config.get("HTTP_CALLBACK_URL_2", "")

        if heartbeat_enable is True:
            threading.Thread(target=self.report_heartbeat, name="dryer-heartbeat-thread", daemon=True).start()

        if mqtt_enable is True:
            threading.Thread(target=self.on_mqtt_connect).start()

        if online_check_enable is True:
            threading.Thread(target=self.check_device_online, name="dryer-online-thread", daemon=True).start()
            
    def http_callback(self, task_id, code, data = None, msg = "", vars = None):
        if http_callback_enable is not True:
            return
        request = {
            "id":task_id,
            "code": code,
            "isRobot":False,
            "stamp":int(time.time() * 1000),
            "msg":msg,
            "vars":vars
        }
        if data is not None:
            request["data"] = data
        headers = {
            "Content-Type": "application/json"
        }
        retry_count = 10
        while retry_count > 0:
            try:
                if self.http_callback_url is None or self.http_callback_url == "":
                    break
                response = requests.post(url = self.http_callback_url, headers = headers, data = json.dumps(request))
                log.info(response.json())
                if response.json()["code"] == 200:
                    break
            except Exception as e:
                log.error(e)
            retry_count -= 1

        retry_count = 10
        while retry_count > 0:
            try:
                if self.http_callback_url_2 is None or self.http_callback_url_2 == "":
                    break
                response = requests.post(url = self.http_callback_url_2, headers = headers, data = json.dumps(request))
                log.info(response.json())
                if response.json()["code"] == 200:
                    break
            except Exception as e:
                log.error(e)
            retry_count -= 1

    def get_wireless_ip_address(self):
        ip_address = self.app.config.get('IP_ADDRESS')
        if ip_address and ip_address != '0.0.0.0':
            """优先使用指定的ip地址"""
            return ip_address

        names = self.app.config.get('NET_INTERFACES')
        for name in names:
            for interface, addrs in psutil.net_if_addrs().items():
                """按照配置的网卡顺序确定ip地址"""
                if name == 'eth':
                    name_ch = '以太网'
                    """过滤掉配置中指定名称的网卡"""
                    if len(self.disable_net_interfaces) != 0 and (interface in self.disable_net_interfaces
                                                                  or interface.lower() in self.disable_net_interfaces):
                        continue
                    if name.lower() in interface.lower() or name_ch in interface:
                        for addr in addrs:
                            if addr.family == socket.AF_INET:
                                return addr.address
                else:
                    if name.lower() in interface.lower():
                        for addr in addrs:
                            if addr.family == socket.AF_INET:
                                return addr.address
        return ""

    # 连接MQTT
    def on_mqtt_connect(self):
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                log.info("*** connect MQTT success ***")
            else:
                log.error("*** connect MQTT failed ***")
        try:
            # 设置连接回调函数
            self.mqtt_client.on_connect = on_connect
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
            self.mqtt_client.reconnect_delay_set(min_delay=3, max_delay=10)
        except Exception as e:
            log.error(e)
            log.error('mqtt connect failed', exc_info=True)
        self.mqtt_client.loop_start()

    def on_publish(self, topic, payload, qos):
        if mqtt_enable is not True:
            return
        result = self.mqtt_client.publish(topic, payload, qos)
        status = result[0]
        if status == 0:
            log.info(f'Send {payload} to topic {topic}')
        else:
            log.info(f'Failed to send message to topic {topic}')

    # 往mqtt发送指令发送结果消息
    def send_msg_to_mqtt(self, task_id, is_ok):
        if mqtt_enable is not True:
            return
        data = {
                    'id': task_id,
                    'stamp': int(time.time() * 1000),
                    'result': 'ok' if is_ok else 'error'
                }
        self.on_publish(self.mqtt_topic, json.dumps(data, indent=4, separators=(',', ':')), 1)

    # 上报心跳方法
    def report_heartbeat(self):
        interval = 0
        while True:
            if heartbeat_enable is not True:
                return
            if self.heart_beat_callback:
                self.heart_beat_callback()
            wireless_ip = self.get_wireless_ip_address()
            status_http = self.machine_status.get_machine_status()
            post_json = {
                'ip': wireless_ip,
                'port': self.port,
                'uri': self.url,
                'stamp': int(time.time() * 1000),
                'identifyingCode': self.machine_code,
                'status': status_http
            }
            try:
                if self.heartbeat_url is not None and self.heartbeat_url != "":
                    if interval == self.heartbeat_log_time_interval:
                        log.info('工作站状态为：%s; ip:%s; identifyingCode:%s; url:%s', status_http, wireless_ip, self.machine_code, self.heartbeat_url)
                    response = requests.post(self.heartbeat_url, data=json.dumps(post_json), headers={'Content-Type': 'application/json'})
                    # 检查响应状态码
                    response.raise_for_status()
            except Exception as e:
                log.error(e)
            try:
                if self.heartbeat_url_2 is not None and self.heartbeat_url_2 != "":
                    if self.machine_code_2 is not None:
                        post_json["identifyingCode"] = self.machine_code_2
                    if interval == self.heartbeat_log_time_interval:
                        log.info('工作站状态为：%s; ip:%s; identifyingCode:%s; url:%s', status_http, wireless_ip, self.machine_code, self.heartbeat_url)
                    response = requests.post(self.heartbeat_url_2, json.dumps(post_json), headers={'Content-Type': 'application/json'})
                    # 检查响应状态码
                    response.raise_for_status()
            except Exception as e:
                log.error(e)
            interval += 1
            if interval > self.heartbeat_log_time_interval:
                interval = 0
            time.sleep(self.heartbeat_time_interval)

    def upload_file(self, file_path, task_id, param_code, result_type):
        result_json = {
            "instructionId": task_id,
            "paramCode": param_code,
            "result": "",
            "resultType": result_type
        }

        # 准备文件数据
        with open(file_path, "rb") as f:
            files = {
                "file": f,
                "resultJson": (None, json.dumps(result_json), "application/json")
            }
            response = requests.post(url=self.upload_url, files=files)
            log.info(response)

    def check_device_online(self, timeout=2):
        """
        检测指定IP和端口的设备是否在线
        :param ip: 设备IP地址
        :param port: 端口号
        :param timeout: 连接超时时间（秒）
        :param retries: 失败重试次数
        :return: (bool, str) 是否在线 + 状态描述
        """
        temp_status = "OFFLINE"
        while True:
            try:
                # 创建TCP Socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                
                # 尝试建立连接
                result = sock.connect_ex((self.target_ip, self.target_port))
                sock.close()
                
                if result == 0:
                    temp_status = "ONLINE"
                else:
                    temp_status = "OFFLINE"  
                    
            except socket.timeout:
                temp_status = "TIMEOUT"
            except ConnectionRefusedError:
                temp_status = "CONNECTION_REFUSED"
            except socket.gaierror:
                temp_status = "HOST_NOT_FOUND"  
            except OSError as e:
                if e.errno == 113:  # No route to host
                    temp_status = "NO_ROUTE_TO_HOST"
                    return False, f"网络不可达 [{self.target_ip}]"
                temp_status = "UNKNOWN_ERROR"
            finally:
                with self.machine_status.lock_online:
                    self.machine_status.machine_online_status = temp_status
            time.sleep(60)

    def run(self):
        log.info('--- gateway start ---')
        server = pywsgi.WSGIServer(('0.0.0.0', self.port), self.app)
        server.serve_forever()
        log.info('--- gateway stop ---')
