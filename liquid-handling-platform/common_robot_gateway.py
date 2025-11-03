"""
机械臂通用调用网关
"""

import json
import time
import requests
from logger_handler import create_logger
from query_instance_status import QueryInstanceStatus
log = create_logger("INFO", "CommonRobotGateway")

is_debug = False

class CommonRobotGateway():
    def __init__(self, robot_command_url, robot_callback_url, robot_id, machine_code):
        self.robot_command_url = robot_command_url
        self.robot_callback_url = robot_callback_url
        self.robot_id = robot_id
        self.machine_code = machine_code

    """
    生成机器人move指令
    """
    def create_move_command(self, target_name, source_name, target_no, source_no, container_type, slot_type):
        """
        移动指令
        将源工作站中的指定编号的容器移动到目标工作站指定的
        source_name: 源工作站名称
        target_name: 目标工作站名称
        instance_id: 实例编号
        pipline_id: 流水线编号
        """
        source = {
            slot_type : source_no,
            "workstation": source_name
        }
        target = {
            slot_type : target_no,
            "workstation": target_name
        }
        operation = {
            "operation": "move",
            "containerTypeCode": container_type,
            "source": source,
            "target": target
        }
        return operation

    def execute_robot_command(self, command, instance_id, pipeline_id):
        return self.execute_robot_command_debug(command, instance_id, pipeline_id) if is_debug else self.execute_robot_command_release(command, instance_id, pipeline_id)

    def execute_robot_command_debug(self, command, instance_id, pipeline_id):
        log.info("调试拆分命令:")
        for param in command:
            log.info(param)
            log.info("开始执行机械臂命令")
            ret = self.execute_robot_command_release([param], instance_id, pipeline_id)
            if ret is False:
                log.error("执行机械臂命令失败")
                return False
    def execute_robot_command_release(self, command, instance_id, pipeline_id):
        log.info("执行机械臂命令:")
        log.info(command)
        data = {
            "identifyingCode": self.machine_code,
            "instanceId": instance_id,
            "param": command,
            "pipelineId": pipeline_id,
            "robotId": self.robot_id,
        }
        headers = { "Content-Type": "application/json" }
        retry_count = 20
        while retry_count > 0:
            try:
                response = requests.post(url=self.robot_command_url, headers=headers, data=json.dumps(data))
                log.info(f"调用机器人指定返回: {response}")
                instruction_id = response.json().get("data", None)
                if response.status_code != 200 or instruction_id is None:
                    log.error("调用机器人接口失败,5秒后重试")
                    time.sleep(5)
                    continue
                else:
                    break
            except Exception as e:
                log.error(f"调用机器人接口异常: {e}, 5秒后重试")
                time.sleep(5)
            finally:
                retry_count -= 1

        if retry_count == 0:
            log.error(f"机器人接口调用失败, 已达重试次数上限{retry_count}次")
            return False
        
        if instruction_id is None:
            log.info("调用机器人接口失败")
            return False

        while True:
            result = QueryInstanceStatus.check_instance_status(instance_id)
            if result == 260:
                log.info("当前实例已经强制失败")
                return False

            try:
                response = requests.get(url=(self.robot_callback_url + str(instruction_id)))
                """判断机器人是否完成动作"""
                json_data = response.json()
                rsp_data = json_data.get("data", None)

                if rsp_data is not None:
                    callback_data = rsp_data.get("callbackData", "")
                    log.info(f"等待机器人回调{callback_data}")
                    if callback_data == "" or callback_data is None:
                        time.sleep(10)
                        continue
                    callback_json = json.loads(callback_data)
                    code = callback_json.get("code", 500)
                    if code == 200:
                        log.info("当前指令执行完成")
                    else:
                        log.info("机器人执行失败,等待指令列表中指令重试")
                        time.sleep(10)
                        continue
                else:
                    log.info("查询机器人是否完成接口失败")
                    time.sleep(5)
                    continue
                break
            except Exception as e:
                log.info("查询异常,5秒后重新查询")
                time.sleep(5)
                log.error(e)
        return True