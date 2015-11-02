__author__ = 'adi'
import temp_pb2


if __name__ == '__main__':
    tempMsg = temp_pb2.MapMessage()
    for k in ['a', 'b']:
        tempMsg.mapMsg[k] = 1
    for k in tempMsg.mapMsg:
        print k,tempMsg.mapMsg[k]
