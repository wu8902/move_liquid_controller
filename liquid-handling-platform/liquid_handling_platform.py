import os
import re
import threading
import time
import queue
import json


from common_robot_gateway import CommonRobotGateway
from common_util import cacheInfoUtil, load_cache, save_cache, split_array
from getway_base import GateWayError, GetwayBase
from logger_handler import create_logger
from datetime import datetime

log = create_logger("INFO", "LiquidHandlingGateway")


TIPBOX_INFO_CACHE = "./.tip_box_info.json"

# 原液瓶信息缓存
SOLUTION_INFO_CACHE = "./.solution_info.json"

# 阈值信息缓存
WARNING_VALUE_CACHE = "./.warning_value.json"

class warningValue():
    def __init__(self):
        self.default_warning_value = {
            "solutionInfo4ml":0.1,
            "solutionInfo50ml":0.1,
            "solutionInfo100ml":0.1
        }
        self.warning_value_dict = cacheInfoUtil.init_cache(WARNING_VALUE_CACHE, self.default_warning_value)

    def reset(self):
        cacheInfoUtil.reset_cache_info(SOLUTION_INFO_CACHE, self.warning_value_dict, self.default_warning_value)

    def get_warning_value(self, solution_type):
        if solution_type in self.warning_value_dict:
            return self.warning_value_dict[solution_type]
        return 0.0
    
    def set_waring_value(self, solution_type, value):
        if solution_type in self.warning_value_dict:
            self.warning_value_dict[solution_type] = value
        else:
            log.error("未知的溶液类型")

class solutionInfo():
    def __init__(self):
        self.default_solution_info = {
            "solutionInfo4ml":[
                4.0, 4.0
            ],
            "solutionInfo50ml":[
                50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0
            ],
            "solutionInfo100ml":[
                100.0, 100.0
            ]
        }

        self.warning_value = warningValue()

        self.default_volumn_map = {
            "solutionInfo4ml" : 4.0,
            "solutionInfo50ml" : 50.0,
            "solutionInfo100ml" : 100.0
        }

        self.solution_info_dict = cacheInfoUtil.init_cache(SOLUTION_INFO_CACHE, self.default_solution_info)

    def reset(self):
        cacheInfoUtil.reset_cache_info(SOLUTION_INFO_CACHE, self.solution_info_dict, self.default_solution_info)

    # 计算预警阈值
    def get_warning_value(self, solution_type):
        if solution_type == "solutionInfo4ml":
            return 4.0 * self.warning_value.get_warning_value(solution_type)
        elif solution_type == "solutionInfo50ml":
            return 50.0 * self.warning_value.get_warning_value(solution_type)
        elif solution_type == "solutionInfo100ml":
            return 100.0 * self.warning_value.get_warning_value(solution_type)

    # 减少指令类型，指定瓶位的溶液数量
    def decrase_solution_info(self, solution_type, location, value):
        """
        0 为减少成功
        1 溶液容量不足
        -1 未知的溶液类型
        """
        solution_type_enum = {
            0 : "solutionInfo4ml",
            1 : "solutionInfo50ml",
            2 : "solutionInfo100ml"
        }
        stock_type = solution_type_enum[solution_type]

        if stock_type not in self.default_solution_info:
            return -1
        self.solution_info_dict[stock_type][location] -= value
        if self.solution_info_dict[stock_type][location] < self.get_warning_value(stock_type):
            log.info(f"{stock_type}中编号为{location} 剩余量小于阈值，请及时补充")
            return 1
        else:
            return 0
        
    def reset_all(self):
        """
        将所有溶液瓶恢复到默认容量-默认状态所有溶剂瓶为满状态
        """
        cacheInfoUtil.reset_cache_info(SOLUTION_INFO_CACHE, self.solution_info_dict, self.default_solution_info)

    def reset_solution_info(self, solution_type, location):
        """
        重置一个溶液瓶为默认容量
        """
        self.solution_info_dict[solution_type][location] = self.default_volumn_map(solution_type)
        save_cache(json.dumps(self.solution_info_dict), SOLUTION_INFO_CACHE)

    def set_solution_info(self, solution_type, location, value):
        """
        设置一个溶液瓶的容量
        """
        solution_type_enum = {
            0 : "solutionInfo4ml",
            1 : "solutionInfo50ml",
            2 : "solutionInfo100ml"
        }
        stock_type = solution_type_enum[solution_type]
        self.solution_info_dict = json.loads(load_cache(SOLUTION_INFO_CACHE))
        self.solution_info_dict[stock_type][location] = value
        save_cache(json.dumps(self.solution_info_dict), SOLUTION_INFO_CACHE)
    
    def get_solution_info(self):
        """
        获取所有溶液瓶信息
        """
        self.solution_info_dict = json.loads(load_cache(SOLUTION_INFO_CACHE))
        percentage_solution_info = {}
        for key, values in self.solution_info_dict.items():
            total = 4 if key == "solutionInfo4ml" else 50 if key == "solutionInfo50ml" else 100 
            percentage_solution_info[key] = [(value / total) for value in values]
        return percentage_solution_info


class tipBoxs():
    def __init__(self):
        self.tip_boxs = []

        for id in range(0, 192):
            self.tip_boxs.append({"id":id, "isEmpty":False})
        self.default_tip_boxs = {
            "tipBoxs": self.tip_boxs
        }
        self.tip_boxs_dict = cacheInfoUtil.init_cache(TIPBOX_INFO_CACHE, self.default_tip_boxs)

    def reset_tip_boxs(self):
        cacheInfoUtil.reset_cache_info(TIPBOX_INFO_CACHE, self.tip_boxs_dict, self.default_tip_boxs)
    
    def get_one_tips(self):
        """
        获取一个非空的Tip头
        """
        self.tip_boxs_dict = json.loads(load_cache(TIPBOX_INFO_CACHE))
        finally_tips_info = None
        for tips_info in self.tip_boxs_dict["tipBoxs"]:
            if not tips_info["isEmpty"]:
                tips_info["isEmpty"] = True
                finally_tips_info = tips_info
                break
        save_cache(json.dumps(self.tip_boxs_dict), TIPBOX_INFO_CACHE)
        return finally_tips_info
    
    def get_tip_count(self):
        """
        获取当前Tip头总数量
        """
        return len(self.tip_boxs_dict["tipBoxs"])
    
    def get_tip_useful_count(self):
        """
        获取当前剩余tip头数量
        """
        self.tip_boxs_dict = json.loads(load_cache(TIPBOX_INFO_CACHE))
        count = 0
        for tips_info in self.tip_boxs_dict["tipBoxs"]:
            if not tips_info["isEmpty"]:
                count += 1
        return count
    
class LiquidHandlingGateway(GetwayBase):
    def __init__(self):
        super().__init__()
        settings_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'settings.json'))
        self.load_config(settings_path)
        self.robot = LiquidHandlingRobot(self.robot_url, self.robot_callback_url, self.robot_id, self.machine_code)

        # 物料站
        self.material_station = "material_station"
        # 开关盖工作站
        self.lid_operation_station = "lid_operation_station"
        # 样品工作站
        self.sample_station = "sample_station"
        # 回收工作站
        self.reclycle_station = "recycle_station"
        
        # 样品架上4ml的容器类型
        self.sample_container_4ml = "container_4ml"
        self.sample_container_20ml = "container_20ml"
        self.sample_container_20ml_no_lid = "container_20ml_nocap"

        self.sample_slot_4ml = "slot_4ml_position"
        self.sample_slot_20ml = "slot_20ml_position"
        self.sample_open_command_20ml = "open_slot_20ml"
        self.sample_close_command_20ml = "close_slot_20ml"
        self.sample_open_command_4ml = "open_slot_4ml"
        self.sample_close_command_4ml = "close_slot_4ml"
        self.sample_open_command_4ml_start = "open_slot_4ml_start"
        self.sample_close_command_4ml_start = "close_slot_4ml_start"


        self.drop_20ml = "drip_to_slot_20ml"
        self.drop_4ml = "drip_to_slot_4ml"
        self.suck_20ml = "suck_from_20ml"
        self.suck_4ml = "suck_from_4ml"

        self.reclycle = "drip_to_recycle"

        self.tip_box = tipBoxs()
        self.solution_manager = solutionInfo()

        self.rack_type_collection = {
            "container_sample_3_4ml":[],
            "container_sample_2_4ml":[],
            "container_sample_1_4ml":[],
            "container_bottle_20ml":[]
        }

        # 滴液指令到容器类型映射
        self.drop_2_command = {
            "container_sample_1_4ml":"drip_to_slot_4ml",
            "container_sample_2_4ml":"drip_to_slot_4ml",
            "container_sample_3_4ml":"drip_to_slot_4ml",
            "container_bottle_20ml":"drip_to_slot_20ml"
        }

        # 样品架开盖容器类型到指令映射
        self.lid_open_2_command = {
            "container_sample_1_4ml":"open_slot_4ml",
            "container_sample_2_4ml":"open_slot_4ml",
            "container_sample_3_4ml":"open_slot_4ml",
            "container_bottle_20ml":"open_slot_20ml"
        }

        # 样品架关盖容器类型到指令映射
        self.lid_close_2_command = {
            "container_sample_1_4ml":"close_slot_4ml",
            "container_sample_2_4ml":"close_slot_4ml",
            "container_sample_3_4ml":"close_slot_4ml",
            "container_bottle_20ml":"close_slot_20ml"
        }

        self.container_type_code_map = {
            "container_sample_1_4ml":"container_4ml",
            "container_sample_2_4ml":"container_4ml",
            "container_sample_3_4ml":"container_4ml",
            "container_bottle_20ml":"container_20ml"
        }

        self.slot_type_map = {
            "container_sample_1_4ml":"slot_4ml",
            "container_sample_2_4ml":"slot_4ml",
            "container_sample_3_4ml":"slot_4ml",
            "container_bottle_20ml":"slot_20ml"
        }

    def get_volume_by_location(self, specified_list, location, default_volume):
        try:
            for item in specified_list:
                if item.get("location") == location:
                    volume = item.get("volume")
                    log.info(f"找到location {location}对应的volume: {volume}")
                    return volume 
            return default_volume
        except Exception as e:
            log.error(f"处理JSON数据时发生错误: {str(e)}")
            return default_volume

    def parse_all_bottle_volume_info(self, param, exchange_volume_list_4ml:list, exchange_volume_list_20ml:list):
        try:
            solution_exchange_rack_4 = param["solutionExchangeInfoRack4"]
            solution_exchange_rack_3 = param["solutionExchangeInfoRack3"]
            solution_exchange_rack_2 = param["solutionExchangeInfoRack2"]
            solution_exchange_rack_1 = param["solutionExchangeInfoRack1"]

            default_volume_1 = solution_exchange_rack_1["defalut_rack_info"]
            default_volume_2 = solution_exchange_rack_2["defalut_rack_info"]
            default_volume_3 = solution_exchange_rack_3["defalut_rack_info"]
            default_volume_4 = solution_exchange_rack_4["defalut_rack_info"]

            specified_volume_1 = solution_exchange_rack_1.get("specified_volume", [])
            specified_volume_2 = solution_exchange_rack_2.get("specified_volume", [])
            specified_volume_3 = solution_exchange_rack_3.get("specified_volume", [])
            specified_volume_4 = solution_exchange_rack_4.get("specified_volume", [])

            for i in range(1, 15):
                exchange_volume_list_4ml.append(self.get_volume_by_location(specified_volume_1, i, default_volume_1))

            for i in range(1, 15):
                exchange_volume_list_4ml.append(self.get_volume_by_location(specified_volume_2, i, default_volume_2))
            
            for i in range(1, 15):
                exchange_volume_list_4ml.append(self.get_volume_by_location(specified_volume_3, i, default_volume_3))
            
            for i in range(1, 9):
                exchange_volume_list_20ml.append(self.get_volume_by_location(specified_volume_4, i, default_volume_4))

            log.info(exchange_volume_list_4ml)
            log.info(exchange_volume_list_20ml)

        except Exception as e:
            raise GateWayError(e)
        
    def reset_rack_type_collection(self):
        self.rack_type_collection = {
            "container_sample_3_4ml":[],
            "container_sample_2_4ml":[],
            "container_sample_1_4ml":[],
            "container_bottle_20ml":[]
        }
    
    def reset_tips_operate(self, _task_id, param):
        self.tip_box.reset_tip_boxs()
        return True, "操作成功", None

    # 设置溶液交换信息
    def set_solution_exchenge_info(self, _task_id, param, context):
        log.info(context)
        log.info(param)
        # 循环次数
        cycle_count = param.get("cycleCount")
        # 休眠时间
        sleep_time = param.get("time")

        while cycle_count > 0:
            cycle_count -= 1
            ret, msg = self.discharge_liquid_operate(_task_id, param, context)
            if ret is False:
                return False, msg, None
            ret, msg, data = self.set_liquid_handling_info_operate(_task_id, param, context)
            if ret is False:
                return False, msg, data
            time.sleep(sleep_time)
        return True, "操作成功", None

    # 排液流程
    def discharge_liquid_operate(self, _task_id, param, context):
        """
        排液指令生成
        """
        self.reset_rack_type_collection()
        containers = context.get("containers", None)
        if containers is None:
            log.error("containers is None")
            return False, "上下文信息中缺少容器信息"
        
        finally_container = []
        for container in containers:
            finally_container.extend(container.get("containers"))

        for container in finally_container:
            container_type_code = container.get("containerTypeCode", None)
            if container_type_code is None:
                log.error("container_type_code is None")
                return False, "上下文信息中缺少容器类型"
            logic_no = container.get("logicNo", None)
            if logic_no is None:
                log.error("logic_no is None")
                log.error("缺少容器逻辑编号，跳过当前容器")
                continue
            if container_type_code == "container_sample_2_4ml":
                logic_no += 14
            if container_type_code == "container_sample_3_4ml":
                logic_no += 28

            container_info = {
                "containerLogicNo": logic_no, 
                "containerTypeCode": container_type_code
            }
            self.rack_type_collection[container_type_code].append(container_info)

        # 4ml容器规格排液量列表
        volume_list_4ml = []

        # 20ml容器规格排液量列表
        volume_list_20ml = []

        self.parse_all_bottle_volume_info(param, volume_list_4ml, volume_list_20ml)

        # 4ml瓶盖最大数量
        max_value_4ml = 12
        # 20ml瓶盖最大数量
        max_value_20ml = 8

        container_list_all = []
        for container_list in self.rack_type_collection.values():
            container_list_all.extend(container_list)
        
        params = []
        suck_params = []
        close_params = []
        lid_index_4ml = 0
        lid_index_20ml = 0
        while len(container_list_all) > 0:
            container = container_list_all.pop()
            container_logic_no = container.get("containerLogicNo") - 1  
            temp_container_type_code = container.get("containerTypeCode")
            temp_open_command = self.sample_open_command_4ml if temp_container_type_code != "container_bottle_20ml" else self.sample_open_command_20ml
            temp_close_command = self.sample_close_command_4ml if temp_container_type_code != "container_bottle_20ml" else self.sample_close_command_20ml
            temp_suck_command = self.suck_4ml if temp_container_type_code != "container_bottle_20ml" else self.suck_20ml
            temp_slot_type = self.sample_slot_4ml if temp_container_type_code != "container_bottle_20ml" else self.sample_slot_20ml
            temp_container_type = self.sample_container_4ml if temp_container_type_code != "container_bottle_20ml" else self.sample_container_20ml
            temp_container_type_no_lid = self.sample_container_4ml if temp_container_type_code != "container_bottle_20ml" else self.sample_container_20ml_no_lid

            # 开盖
            lid_index = lid_index_4ml if temp_container_type_code != "container_bottle_20ml" else lid_index_20ml
            params.append(self.robot.create_move_command(self.lid_operation_station, self.sample_station, 0, container_logic_no, temp_container_type, temp_slot_type))
            params.append(self.robot.open_lid_command(self.lid_operation_station, temp_open_command, lid_index))
            params.append(self.robot.create_move_command(self.sample_station, self.lid_operation_station, container_logic_no, 0, temp_container_type_no_lid, temp_slot_type))
            
            if temp_container_type_code != "container_bottle_20ml":
                lid_index_4ml += 1
            else:
                lid_index_20ml += 1
            volume_value = volume_list_4ml[container_logic_no] if temp_container_type_code != "container_bottle_20ml" else volume_list_20ml[container_logic_no]
            
            while volume_value > 1000:
                volume_value -= 1000 
                suck_params.append(self.robot.suck_command(self.sample_station, temp_suck_command, container_logic_no, 1000))
                suck_params.append(self.robot.dispense_command(self.reclycle_station, 0))
            suck_params.append(self.robot.suck_command(self.sample_station, temp_suck_command, container_logic_no, volume_value))
            suck_params.append(self.robot.dispense_command(self.reclycle_station, 0))

            close_params.insert(0, self.robot.create_move_command(self.lid_operation_station, self.sample_station, 0, container_logic_no, temp_container_type_no_lid, temp_slot_type))     
            close_params.insert(0, self.robot.close_lid_command(self.lid_operation_station, temp_close_command, lid_index))
            close_params.insert(0, self.robot.create_move_command(self.sample_station, self.lid_operation_station, container_logic_no, 0, temp_container_type, temp_slot_type))

            if lid_index_4ml >= max_value_4ml - 1 or lid_index_20ml > max_value_20ml - 1 or len(container_list_all) == 0:
                # 安装tip头并且吸液
                tips_info = self.tip_box.get_one_tips()
                if tips_info is None:
                    return False, "Tip头余量不足", None
                params.append(self.robot.install_tip_command(self.material_station, tips_info.get("id")))  
                params.extend(suck_params)

                # 卸载tip头
                params.append(self.robot.uninstall_tip_command(self.reclycle_station))
                # 关闭瓶盖
                params.extend(close_params)

                suck_params.clear()
                close_params.clear()
                lid_index_4ml = 0
                lid_index_20ml = 0

        if self.robot.execute_robot_command(params, self.instance_id, self.pipeline_id) is False:
            log.error("执行机械臂命令失败")
            return False, "执行机械臂命令失败"
        log.info("执行机械臂命令成功")   
        return True, "执行成功"     
    
    # 设置移液信息
    def set_liquid_handling_info_operate(self, _task_id, param, context):
        log.info(context)
        self.reset_rack_type_collection()
        containers = context.get("containers", None)
        if containers is None:
            log.error("containers is None")
            return False, "上下文信息中缺少容器信息"
        
        finally_container = []
        for container in containers:
            finally_container.extend(container.get("containers"))

        for container in finally_container:
            container_type_code = container.get("containerTypeCode", None)
            if container_type_code is None:
                log.error("container_type_code is None")
                return False, "上下文信息中缺少容器类型"
            
            # if container_type_code in self.rack_type_collection:
            logic_no = container.get("logicNo", None)

            # 对机器化学家上定义的容器类型和槽位类型做一层映射，使其对应到机器人底层定义的容器类型和槽位类型
            # container_robot_type_code = self.container_type_code_map.get(container_type_code)
            # slot_type_code = self.slot_type_map.get(container_type_code)

            if logic_no is None:
                log.error("logic_no is None")
                log.error("缺少容器逻辑编号，跳过当前容器")
                continue
            if container_type_code == "container_sample_2_4ml":
                logic_no += 14
            if container_type_code == "container_sample_3_4ml":
                logic_no += 28

            container_info = {
                "containerLogicNo": logic_no, 
                "containerTypeCode": container_type_code
            }
            self.rack_type_collection[container_type_code].append(container_info)

        # 操作集合，按原液瓶排序
        operation_dict = {}
        for i in range(1, 13):
            operation_dict[i] = []

        self.parse_operation(param.get("param4mlRack1"), operation_dict, "container_sample_1_4ml")        
        self.parse_operation(param.get("param4mlRack2"), operation_dict, "container_sample_2_4ml")
        self.parse_operation(param.get("param4mlRack3"), operation_dict, "container_sample_3_4ml")
        self.parse_operation(param.get("param20mlRack1"), operation_dict, "container_bottle_20ml")

        # 迭代所有原液瓶
        for i in range(1,13):
            if len(operation_dict[i]) == 0:
                continue

            bottle_lid_is_open = False

            params = []
            # 开原液瓶盖
            open_source_params = []
            # 关原液瓶盖
            close_source_params = []

            operations = operation_dict[i]
            # 开盖 原液瓶
            source_id = self.robot.get_bottle_location(i)
            open_command_type_put = self.robot.get_open_lid_command_string(i, "put")
            open_command_type_take = self.robot.get_open_lid_command_string(i, "take")
            close_command_type_put = self.robot.get_close_lid_command_string(i, "put")
            close_command_type_take = self.robot.get_close_lid_command_string(i, "take")

            if i > 0 and i <= 2:
                # 4ml两个固定位置放瓶盖 12 和 13
                solution_4ml = i - 1
                open_source_params.append(self.robot.create_move_command(self.lid_operation_station, self.material_station, 0, i - 1, self.sample_container_4ml, self.sample_slot_4ml))
                open_source_params.append(self.robot.open_lid_command(self.lid_operation_station, self.sample_open_command_4ml_start, solution_4ml))
                open_source_params.append(self.robot.create_move_command(self.material_station, self.lid_operation_station, i - 1, 0, self.sample_container_4ml, self.sample_slot_4ml))
                # 关盖
                close_source_params.append(self.robot.create_move_command(self.lid_operation_station, self.material_station, 0, i - 1, self.sample_container_4ml, self.sample_slot_4ml))
                close_source_params.append(self.robot.close_lid_command(self.lid_operation_station, self.sample_close_command_4ml_start, solution_4ml))
                close_source_params.append(self.robot.create_move_command(self.material_station, self.lid_operation_station, i - 1, 0, self.sample_container_4ml, self.sample_slot_4ml))
            else:
                # 开原液瓶盖
                open_source_params.append(self.robot.open_lid_command(self.material_station, open_command_type_put, source_id))
                open_source_params.append(self.robot.open_lid_command(self.material_station, open_command_type_take, 0))
                # 关闭当前原液瓶盖子
                close_source_params.append(self.robot.close_lid_command(self.material_station, close_command_type_put, 0))
                close_source_params.append(self.robot.close_lid_command(self.material_station, close_command_type_take, source_id))

            # if i > 0 and i <= 2: 
            #     solution_4ml = i - 1
            #     params.append(self.robot.create_move_command(self.lid_operation_station, self.material_station, 0, i - 1, self.sample_container_4ml, self.sample_slot_4ml))
            #     params.append(self.robot.close_lid_command(self.lid_operation_station, self.sample_close_command_4ml_start, solution_4ml))
            #     params.append(self.robot.create_move_command(self.material_station, self.lid_operation_station, i - 1, 0, self.sample_container_4ml, self.sample_slot_4ml))
            # else:
            #     params.append(self.robot.close_lid_command(self.material_station, close_command_type_put, 0))
            #     params.append(self.robot.close_lid_command(self.material_station, close_command_type_take, source_id))

            operations_4ml = []
            operations_20ml = []

            volumn_dict = {}

            for operation in operations:
                # 整理当前所有瓶子
                operate_bottles = operation["operate_bottles"]
                container_type_code = operation["container_type_code"]
                os_bottle_volumn = operation["os_bottle_volumn"]
                volumn_dict[container_type_code] = os_bottle_volumn
                if container_type_code == "container_sample_1_4ml" or container_type_code == "container_sample_2_4ml" or container_type_code == "container_sample_3_4ml":
                    operations_4ml.extend(operate_bottles)
                if container_type_code == "container_bottle_20ml":
                    operations_20ml.extend(operate_bottles)

            if len(operations_20ml) > 0:
                # 开20ml的盖子
                lid_20ml_index = 0
                for operation_20ml in operations_20ml:
                    params.append(self.robot.create_move_command(self.lid_operation_station, self.sample_station, 0, operation_20ml, self.sample_container_20ml, self.sample_slot_20ml))
                    params.append(self.robot.open_lid_command(self.lid_operation_station, self.sample_open_command_20ml, lid_20ml_index))
                    params.append(self.robot.create_move_command(self.sample_station, self.lid_operation_station, operation_20ml, 0, self.sample_container_20ml_no_lid, self.sample_slot_20ml))
                    lid_20ml_index += 1
                
                if not bottle_lid_is_open:
                    params.extend(open_source_params)
                    bottle_lid_is_open = True

                # 安装tip头
                tips_info = self.tip_box.get_one_tips()
                if tips_info is None:
                    return False, "Tip头余量不足", None
                params.append(self.robot.install_tip_command(self.material_station, tips_info.get("id")))

                #吸液和滴液 
                for operation_20ml in operations_20ml:
                    params.append(self.robot.suck_command(self.material_station, self.robot.get_suck_command_string(i), self.robot.get_bottle_location(i), volumn_dict["container_bottle_20ml"]))
                    params.append(self.robot.drop_command(self.sample_station, self.drop_20ml, operation_20ml))
                
                params.append(self.robot.uninstall_tip_command(self.reclycle_station))

                # 关闭20ml盖子
                for operation_20ml in operations_20ml:
                    
                    lid_20ml_index -= 1
                    params.append(self.robot.create_move_command(self.lid_operation_station, self.sample_station, 0, operation_20ml, self.sample_container_20ml_no_lid, self.sample_slot_20ml))
                    params.append(self.robot.close_lid_command(self.lid_operation_station, self.sample_close_command_20ml, lid_20ml_index))
                    params.append(self.robot.create_move_command(self.sample_station, self.lid_operation_station, operation_20ml, 0, self.sample_container_20ml, self.sample_slot_20ml))

            sub_operations_4ml = split_array(operations_4ml)
            while len(sub_operations_4ml) != 0:
                lid_4ml_index = 0
                operation_4ml_head = sub_operations_4ml.pop(0)


                for operation_4ml in operation_4ml_head:
                    # 开4ml的盖子
                    params.append(self.robot.create_move_command(self.lid_operation_station, self.sample_station, 0, operation_4ml,self.sample_container_4ml, self.sample_slot_4ml))
                    params.append(self.robot.open_lid_command(self.lid_operation_station, self.sample_open_command_4ml, lid_4ml_index))
                    params.append(self.robot.create_move_command(self.sample_station, self.lid_operation_station, operation_4ml, 0, self.sample_container_4ml, self.sample_slot_4ml))
                    lid_4ml_index += 1

                if not bottle_lid_is_open:
                    params.extend(open_source_params)
                    bottle_lid_is_open = True

                
                tips_info = self.tip_box.get_one_tips()
                if tips_info is None:
                    return False, "Tip头余量不足", None
                params.append(self.robot.install_tip_command(self.material_station, tips_info.get("id")))
                
                for operation_4ml in operation_4ml_head:
                    # 滴液当前批次
                    current_contianer_type_code = self.logic_no_to_sample_id(operation_4ml)
                    params.append(self.robot.suck_command(self.material_station, self.robot.get_suck_command_string(i), self.robot.get_bottle_location(i), volumn_dict[current_contianer_type_code]))
                    params.append(self.robot.drop_command(self.sample_station, self.drop_4ml, operation_4ml))

                # 卸载tip头
                params.append(self.robot.uninstall_tip_command(self.reclycle_station))
                if len(sub_operations_4ml) == 0:
                    params.extend(close_source_params)

                for operation_4ml in operation_4ml_head:
                    # 关4ml盖子
                    lid_4ml_index -= 1
                    params.append(self.robot.create_move_command(self.lid_operation_station, self.sample_station, operation_4ml, 0, self.sample_container_4ml, self.sample_slot_4ml))
                    params.append(self.robot.close_lid_command(self.lid_operation_station, self.sample_close_command_4ml, lid_4ml_index))
                    params.append(self.robot.create_move_command(self.sample_station, self.lid_operation_station, 0, operation_4ml, self.sample_container_4ml, self.sample_slot_4ml))
            
            log.info(params)
            if self.robot.execute_robot_command(params, self.instance_id, self.pipeline_id) is False:
                log.error("执行机械臂命令失败")
                return False, "执行机械臂命令失败", None
            log.info("执行机械臂命令成功")   
        return True, "执行成功", None     

    def logic_no_to_sample_id(self, logic_no):
        no = int(logic_no / 14) 
        if no == 0:
            return "container_sample_1_4ml"
        elif no == 1:
            return "container_sample_2_4ml"
        elif no == 2:
            return "container_sample_3_4ml"

    def parse_operation(self, operation_list, operation_dict, container_type_code):
        """
        解析原液瓶列表
        """
        for data in operation_list.get("operateList"):
            os_bottle_no = data["originalSolutionBottle"]
            os_bottle_volumn = data["originalSolutionVolume"]
            bottles = []
            for bottle_info in self.rack_type_collection[container_type_code]:
                logic_no = bottle_info.get("containerLogicNo") - 1
                if logic_no in bottles:
                    log.error("逻辑编号重复")
                    continue
                bottles.append(logic_no)
                
            operation_dict[os_bottle_no].append({
                "os_bottle_volumn": os_bottle_volumn,
                "container_type_code": container_type_code,
                "operate_bottles": bottles
            })

    def get_tips_count_operate(self, task_id, param):
        data = {
            "tipsCount": self.tip_box.get_tip_useful_count(),
            "tipsTotal": self.tip_box.get_tip_count()
        }
        return True, "获取成功", data
    
    def get_stock_solution_info_operate(self, task_id, param):
        data = self.solution_manager.get_solution_info()
        return True, "获取成功", data
    
    def set_stock_solution_info_operate(self, task_id, param):
        location = param["location"]
        stock_type = param["stock_solution_type"]
        value_precent = param["value"]
        if value_precent < 0 or value_precent > 1.0:
            return False, "比例值错误", None
        total = 4.0 if stock_type == 0 else 50.0 if stock_type == 1 else 100.0 
        value = value_precent * total
        self.solution_manager.set_solution_info(stock_type,location, value)
        return True, "设置成功", None 
        
        
class LiquidHandlingRobot(CommonRobotGateway):

    def __init__(self, robot_command_url, robot_callback_url, robot_id, machine_code):
        super().__init__(robot_command_url, robot_callback_url, robot_id, machine_code)
        self.sourec_workstation = ""
        self.target_workstation = ""

        self.lid_workstation = ""

    # 根据原液瓶容器位置获取开盖指令类型
    def get_open_lid_command_string(self, location, move_type = "put"):
        if location > 0 and location <= 2:
            return "open_slot_4ml"
        elif location > 2 and location <= 10:
            return "open_slot_50ml" + f"_{move_type}"
        elif location > 10 and location <= 12:
            return "open_slot_100ml" + f"_{move_type}"
        else:
            return ""
        
    
    # 根据原液瓶容器位置获取关盖指令类型
    def get_close_lid_command_string(self, location, move_type = "put"):
        if location > 0 and location <= 2:
            return "close_slot_4ml" 
        elif location > 2 and location <= 10:
            return "close_slot_50ml" + f"_{move_type}"
        elif location > 10 and location <= 12:
            return "close_slot_100ml" + f"_{move_type}"
        else:
            return ""
        
    # 根据原液瓶容器位置获取吸液指令类型
    def get_suck_command_string(self, location):
        if location > 0 and location <= 2:
            return "suck_from_4ml"
        elif location > 2 and location <= 10:
            return "suck_from_50ml"
        elif location > 10 and location <= 12:
            return "suck_from_100ml"
        else:
            return ""
        
    # 根据原液瓶编号获取指令中的位置
    def get_bottle_location(self, bottle_id):
        if bottle_id > 0 and bottle_id <= 2:
            return bottle_id - 1 
        elif bottle_id > 2 and bottle_id <= 10:
            return bottle_id - 3
        elif bottle_id > 10 and bottle_id <= 12:
            return bottle_id - 11
        else:
            return -1
        
    """
    生成机器人开盖指令
    """
    def open_lid_command(self, source_name, command, bottle_id):
        """
        开盖子指令
        会生成三条机器人指令, 源工作站到开/关盖工作站, 关盖动作指令, 开关/盖工作站到源工作站
        source_name: 源工作站名称
        bottle_id: 待开盖原液瓶编号
        """
        operation = {
            "operation":command,
            "source":{
                "slot_4ml_position":bottle_id,
                "workstation":source_name
            },
            "target":{
                "workstation":source_name
            }
        }
        return operation

    """
    生成机器人关盖指令
    """
    def close_lid_command(self, source_name, command, bottle_id):
        """
        关盖子指令
        source_name: 源工作站名称
        bottle_id: 待关盖原液瓶编号
        """
        operation = {
            "operation": command,
            "source":{
                "slot_4ml_position":bottle_id,
                "workstation":source_name
            },
            "target":{
                "workstation":source_name
            }
        }
        return operation
    
    """
    生成机器人滴液指令
    """
    def drop_command(self, source_name, command, location_no):
        """
        滴液指令
        source_name: 源工作站名称
        """
        operation = {
            "operation" : command,
            "source":{
                "slot_4ml_position": location_no,
                "workstation":source_name
            },
            "target":{
                "workstation":source_name
            }
        }
        return operation
    
    """
    生成机器人排液指令
    """
    def dispense_command(self, source_name, location_no):
        """
        排液指令
        source_name: 源工作站名称
        location_no: 目标容器编号
        volumn: 滴液/吸液量 to_arg
        """
        operation = {
            "operation" : "drip_to_recycle",
            "source":{
                "slot_4ml_position": location_no,
                "workstation":source_name
            },
            "target":{
                "workstation":source_name
            }
        }
        return operation

    def suck_command(self, source_name, command, location_no, volumn):
        """
        吸液指令
        source_name: 源工作站名称
        location_no: 目标容器编号
        volumn: 滴液/吸液量 to_arg
        """
        operation = {
            "operation" : command,
            "source":{
                "slot_4ml_position": location_no,
                "workstation":source_name
            },
            "target":{
                "workstation": source_name
            },
            "tool_arg":volumn
        }    
        return operation
    
    def install_tip_command(self, source_name, location_no):
        """
        安装吸液头指令
        """
        operation = {
            "operation" : "move_from_drip",
            "source":{
                "slot_4ml_position": location_no,
                "workstation":source_name
            },
            "target":{
                "workstation": source_name
            }
        } 
        return operation
    
    def uninstall_tip_command(self, workstation):
        """
        卸下吸液头指令
        """
        operation = {
            "operation" : "move_to_drip",
            "source":{
                "slot_4ml_position": 0,
                "workstation": workstation
            },
            "target":{
                "workstation": workstation
            }
        }
        return operation
