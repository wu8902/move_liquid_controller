import json
import threading
import time
from flask import jsonify

from getway_base import GetwayBase
from logger_handler import create_logger

import traceback


log = create_logger("INFO", "OperateWrapper")
class CommonTask:
    common_task_id = -1
def _wrap_task(gateway:GetwayBase, task_id, param, func):
    try:
        gateway.machine_status.increase()
        ret, msg, data = func(task_id, param)
        log.info(f"执行结果 ret:{ret}")
        if ret is True:
            gateway.http_callback(task_id, 200, data=data, msg="操作成功")
        else:
            gateway.http_callback(task_id=task_id, code=500, data=data, msg=msg)
    except Exception as e:
        log.error(f"操作失败:{str(e)}")
        gateway.http_callback(task_id=task_id, code=500, data=None, msg=f"{str(e)}")
        stack_str = traceback.format_exc()
        log.error(stack_str)
    finally:
        gateway.machine_status.decrease()

def _wrap_task_context(gateway:GetwayBase, task_id, param, context, func):
    try:
        gateway.machine_status.increase()
        ret, msg, data = func(task_id, param, context)
        log.info(f"执行结果 ret:{ret}")
        if ret is True:
            gateway.http_callback(task_id, 200, data=data, msg="操作成功")
        else:
            gateway.http_callback(task_id=task_id, code=500, data=data, msg=msg)
    except Exception as e:
        log.error(f"操作失败:{str(e)}")
        gateway.http_callback(task_id=task_id, code=500, data=None, msg=f"{str(e)}")
        stack_str = traceback.format_exc()
        log.error(stack_str)
    finally:
        gateway.machine_status.decrease()

def _wrap_task_sync(gateway:GetwayBase, task_id, param, func):
    try:
        gateway.machine_status.increase()
        ret, msg, data = func(task_id, param)
        log.info(f"执行结果 ret:{ret}")
        if ret:
            return 200, msg, data
        else:
            return 500, msg, data
    except Exception as e:
        log.error(f"操作失败:{str(e)}")
        return 500, str(e), data
    finally:
        gateway.machine_status.decrease()

def _wrap_task_var(gateway:GetwayBase, task_id, param, func):
    try:
        gateway.machine_status.increase()
        ret, msg, data, vars = func(task_id, param)
        log.info(f"执行结果 ret:{ret}")
        if ret is True:
            gateway.http_callback(task_id, 200, data=data, msg="操作成功", vars=vars)
        else:
            gateway.http_callback(task_id=task_id, code=500, data=data, msg=msg, vars=vars)
    except Exception as e:
        log.error(f"操作失败:{str(e)}")
        gateway.http_callback(task_id=task_id, code=500, data=None, msg=f"{str(e)}")
    finally:
        gateway.machine_status.decrease()

def _warp_task_not_lock(gateway:GetwayBase, task_id, param, func):
    try:
        ret, msg, data = func(task_id, param)
        log.info(f"执行结果 ret:{ret}")
        if ret is True:
            gateway.http_callback(task_id, 200, data=data, msg="操作成功")
        else:
            gateway.http_callback(task_id=task_id, code=500, data=data, msg=msg)
    except Exception as e:
        log.error(f"操作失败:{str(e)}")
        gateway.http_callback(task_id=task_id, code=500, data=None, msg=f"{str(e)}")
    finally:
        gateway.machine_status.reset()

def operate_not_lock(gateway:GetwayBase, data, function):
    if isinstance(data, bytes):
        json_str = data.decode('utf-8')  # 字节 → 字符串
    else:
        json_str = data  # 直接使用字符串
    json_data = json.loads(json_str)
    task_id = json_data.get('id', 10001)
    param = json_data.get('param', {})
    if "settings" in param:
        settings = param["settings"]
        param = settings[0]
    response = {
        'id': task_id,
        'msg': round(time.time() * 1000),
        'code': 200
    }
    threading.Thread(target=_warp_task_not_lock, args=(gateway, task_id, param, function)).start()
    return jsonify(response), 200

def operate(gateway:GetwayBase, data, function, have_vars=False, use_context=False): 
    if isinstance(data, bytes):
        json_str = data.decode('utf-8')  # 字节 → 字符串
    else:
        json_str = data  # 直接使用字符串
    json_data = json.loads(json_str)
    task_id = json_data['id']
    param = json_data.get('param', {})
    if param and "settings" in param:
        settings = param["settings"]
        param = settings[0]

    context = json_data.get("context", None)
    if context is not None:
        gateway.pipeline_id = context["pipelineId"]
        gateway.instance_id = context["instanceId"]

    response = {
        'id': task_id,
        'stamp': round(time.time() * 1000),
        'message': '操作成功',
        'msg':'操作成功',
        'code': 200
    }
    if gateway.machine_status.get_machine_status() != "IDLE":
        response["code"] = 500
        response['message'] = f"DEVICE {gateway.machine_status.get_machine_status()}"
        response['msg'] = f"DEVICE {gateway.machine_status.get_machine_status()}"
        return jsonify(response), 200
    
    if not have_vars:
        if use_context:
            threading.Thread(target=_wrap_task_context, args=(gateway, task_id, param, context, function)).start()
        else:
            threading.Thread(target=_wrap_task, args=(gateway, task_id, param, function)).start()
    else:
        threading.Thread(target=_wrap_task_var, args=(gateway, task_id, param, function)).start()
    return jsonify(response), 200

def operate_sync(gateway:GetwayBase, data, function, have_vars=False, have_lock=True): 
    if isinstance(data, bytes):
        json_str = data.decode('utf-8')  # 字节 → 字符串
    else:
        json_str = data  # 直接使用字符串
    json_data = json.loads(json_str)
    task_id = json_data['id']
    param = json_data.get('param', {})
    if param and "settings" in param:
        settings = param["settings"]
        param = settings[0]

    context = json_data.get("context", None)
    if context is not None:
        gateway.pipeline_id = context["pipelineId"]
        gateway.instance_id = context["instanceId"]

    response = {
        'id': task_id,
        'stamp': round(time.time() * 1000),
        'message': '操作成功',
        'msg':'操作成功',
        'code': 200
    }
    if have_lock and gateway.machine_status.get_machine_status() != "IDLE":
        response["code"] = 500
        response['message'] = f"DEVICE {gateway.machine_status.get_machine_status()}"
        response['msg'] = f"DEVICE {gateway.machine_status.get_machine_status()}"
        return jsonify(response), 200
    
    code, msg, data = _wrap_task_sync(gateway, task_id, param, function)
    response["code"] = code
    response['message'] = msg
    response['msg'] = msg
    response['data'] = data
    return jsonify(response), 200

def add_package(request_data, key, value):
    if isinstance(request_data, bytes):
        json_str = request_data.decode('utf-8')  # 字节 → 字符串
    else:
        json_str = request_data  # 直接使用字符串
    data_dict = json.loads(json_str)
    data_dict["param"][key] = value
    return json.dumps(data_dict)
