import threading
import time
from flask import Flask, json, jsonify, request, send_from_directory
import json

from liquid_handling_platform import LiquidHandlingGateway
from logger_handler import create_logger
from operate_wrapper import operate, operate_not_lock, operate_sync
from gevent import pywsgi

app = Flask(__name__)
log = create_logger("INFO", "Main")

def run():
    log.info('--- liquid handling gateway start ---')
    server = pywsgi.WSGIServer(('0.0.0.0', liquid_handling_gateway.port), app)
    server.serve_forever()
    log.info('--- liquid handling gateway stop ---')

@app.route('/setLiquidHandlingInfo', methods=['POST'])
def setLiquidHandlingInfo():
    return operate(liquid_handling_gateway, request.data, liquid_handling_gateway.set_liquid_handling_info_operate, use_context=True)

@app.route('/setSolutionExchengeInfo', methods=['POST'])
def setSolutionExchengeInfo():
    return operate(liquid_handling_gateway, request.data, liquid_handling_gateway.set_solution_exchenge_info, use_context=True)

@app.route('/resetTipBoxs', methods=['POST'])
def reset_tip_boxs():
    return operate(liquid_handling_gateway, request.data, liquid_handling_gateway.reset_tips_operate)

@app.route('/getTipsCount', methods=['POST'])
def get_tips_state():
    return operate_sync(liquid_handling_gateway, request.data, liquid_handling_gateway.get_tips_count_operate, have_lock=False)

@app.route('/getStockSolutionInfo', methods=["POST"])
def get_stock_solution_info():
    return operate_sync(liquid_handling_gateway, request.data, liquid_handling_gateway.get_stock_solution_info_operate, have_lock=False)

@app.route("/setStockSolutionInfo", methods=["POST"])
def set_stock_solution_info():
    return operate_sync(liquid_handling_gateway, request.data, liquid_handling_gateway.set_stock_solution_info_operate, have_lock=False)

if __name__ == "__main__": 
    liquid_handling_gateway = LiquidHandlingGateway()
    run()
    