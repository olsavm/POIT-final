from threading import Lock
from flask import Flask, render_template, session, request, jsonify, url_for
from flask_socketio import SocketIO, emit, disconnect
import MySQLdb       
import math
import time
import configparser as ConfigParser
import random
import serial

async_mode = None

app = Flask(__name__)


config = ConfigParser.ConfigParser()
config.read('config.cfg')
myhost = config.get('mysqlDB', 'host')
myuser = config.get('mysqlDB', 'user')
mypasswd = config.get('mysqlDB', 'passwd')
mydb = config.get('mysqlDB', 'db')
print(myhost)


app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode=async_mode)
thread = None
thread_lock = Lock() 

ser = serial.Serial("/dev/ttyUSB0", 9600)
ser.baudrate=9600

def background_thread(args):
    ser.readline()
    count = 0  
    dataCounter = 0 
    dataList = []
    db = MySQLdb.connect(host=myhost,user=myuser,passwd=mypasswd,db=mydb)          
    while True:
        if args:
          A = dict(args).get('A')
          dbV = dict(args).get('btn_value')
        else:
          A = 1
          dbV = 'nieco'  
        #print A
        print(dbV) 
        print(args)  
        socketio.sleep(2)
        count += 1
        dataCounter +=1
        lux = ser.readline().decode().split(':')[1]
        temp = ser.readline().decode().split(':')[1]
        if dbV == 1:
          dataDict = {
            "x": dataCounter,
            "y": float(lux),
            "temp": float(temp)
            }
          dataList.append(dataDict)
        else:
          if len(dataList)>0:
            print(str(dataList))
            fuj = str(dataList).replace("'", "\"")
            print(fuj)
            cursor = db.cursor()
            cursor.execute("SELECT MAX(ID) FROM LightSensorTable")
            maxid = cursor.fetchone()
            if maxid[0] == None:
                maxid = '1'
            else:
                maxid = int(maxid[0]) + 1
            print('MAXID:', maxid)
            cursor.execute("INSERT INTO LightSensorTable (ID, Measurement) VALUES (%s, %s)", (str(maxid), fuj))
            db.commit()
            with open("static/files/test.txt","a") as fo:
                fo.write("%s\r\n" %fuj)
          dataList = []
          dataCounter = 0
        socketio.emit('my_response',
            {'data': lux, 'temp': temp, 'count': count},
            namespace='/test')
    db.close()

@app.route('/')
def index():
    return render_template('index.html', async_mode=socketio.async_mode)

@app.route('/read/<string:num>', methods=['GET', 'POST'])
def readmyfile(num):
    with open("static/files/test.txt","r") as fo:
        rows = fo.readlines()
    return rows[int(num)-1]
    
@app.route('/dbdata/<string:num>', methods=['GET', 'POST'])
def dbdata(num):
  db = MySQLdb.connect(host=myhost,user=myuser,passwd=mypasswd,db=mydb)
  cursor = db.cursor()
  cursor.execute("SELECT Measurement FROM  LightSensorTable WHERE id=%s", num)
  rv = cursor.fetchone()
  return str(rv[0])
    
@socketio.on('my_event', namespace='/test')
def test_message(message):   
    session['receive_count'] = session.get('receive_count', 0) + 1 
    session['A'] = message['value']    
    emit('my_response',
         {'data': message['value'], 'count': session['receive_count']})

@socketio.on('disconnect_request', namespace='/test')
def disconnect_request():
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response',
         {'data': 'Disconnected!', 'count': session['receive_count']})
    disconnect()

@socketio.on('click_eventStart', namespace='/test')
def db_message(message):   
    session['btn_value'] = 1
    #print('BUTTON_VAL=', session['btn_value'])
    #print(session)

@socketio.on('click_eventStop', namespace='/test')
def db_message(message):   
    session['btn_value'] = 0
    #print('BUTTON_VAL=', session['btn_value'])
    #print(session)

@socketio.on('connect', namespace='/test')
def test_connect():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=background_thread, args=session._get_current_object())
   # emit('my_response', {'data': 'Connected', 'count': 0})


@socketio.on('disconnect', namespace='/test')
def test_disconnect():
    print('Client disconnected', request.sid)


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=80, debug=True)
