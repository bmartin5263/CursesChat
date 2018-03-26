import getopt
import threading
import sys
import os
import time
from utilities import SocketManager, Debug, Notification, Message

def getArguments():
    willDebug = False
    options, arguments = getopt.getopt(sys.argv[1:], "d")
    for opt in options:
        if opt[0] == '-d':
            willDebug = True
    return willDebug

def main():
    isDebug = getArguments()
    debugger = Debug(isDebug)
    s = Server(debugger)
    s.run()

class ChatClient:

    def __init__(self):
        self.id = None
        self.name = 'Anonymous'
        self.messageSocket = None
        self.fileSocket = None
        self.auxSocket = None

class ChatRoom:

    def __init__(self, name, ):
        self.name = name
        self.messageSockets = {}            # name : socket
        self.fileSockets = {}               # name : socket

    def closeRoom(self):
        pass

    def openRoom(self):
        pass

class Server:

    SERVER_PORT = 24600
    CHAT_PORT = 24601
    FILE_PORT = 24602

    def __init__(self, debugger):
        self.debug = debugger
        self.serverSocketManager = None
        self.messageSocketManager = None
        self.fileSocketManager = None
        self.active = True
        self.rooms = {}
        self.lock = threading.RLock()

    def console(self, message, messageType=''):
        self.debug.console(message, messageType)

    def serverReader(self, manager):
        while self.active:
            inbox = manager.read()
            for isMessage, sock, message in inbox:
                if isMessage:
                    message = eval(message)
                    if message['type'] == 'room':
                        if message['action'] == 'get':
                            self.console("Client wants rooms", 'room')
                            response = Message.SEND_ROOMS.value.format(list(self.rooms.keys()))
                            self.serverSocketManager.write(response, [sock])
                        elif message['action'] == 'new':
                            roomName = message['data']
                            if roomName not in self.rooms:
                                self.rooms[roomName] = None
                                self.console("Client made room {}".format(roomName), 'room')
                    elif message['type'] == 'chat':
                        self.console("Received Chat Message", "message")
                        response = Message.CHAT.value.format(message['data'])
                        self.serverSocketManager.writeAll(response, exclude=[sock])
                else:
                    resource = sock
                    self.console("Got a notification!", "message")
            time.sleep(.1)
        self.console("Server Reader Ending.", "important")

    def run(self):
        self.console("Server Started.", "important")
        self.startSocketManagers()
        inboxReader = threading.Thread(target=self.serverReader, args=(self.serverSocketManager,))
        inboxReader.start()
        while True:
            try:
                time.sleep(.1)
            except KeyboardInterrupt:
                self.active = False
                self.stopSocketManagers()
                break

        inboxReader.join()
        self.console("Allowing Threads to End...", "important")
        time.sleep(2)
        self.console("Remaining Server Sockets: {}".format(len(self.serverSocketManager.socketMap)), "important")
        self.console("Remaining Chat Sockets: {}".format(len(self.messageSocketManager.socketMap)), "important")
        self.console("Remaining Threads: {}".format(threading.active_count()), "important")
        self.console("Exiting Server.", "important")

    def startSocketManagers(self):
        self.serverSocketManager = SocketManager.actAsServer(port=Server.SERVER_PORT, debugger=self.debug)
        self.messageSocketManager = SocketManager.actAsServer(port=Server.CHAT_PORT, debugger=self.debug)
        self.serverSocketManager.startListener()
        self.messageSocketManager.startListener()
        self.console("Socket Managers Started.", "important")

    def stopSocketManagers(self):
        self.serverSocketManager.terminateManager()
        self.messageSocketManager.terminateManager()
        self.console("Socket Managers Terminated.", "important")

if __name__ == '__main__':
    os.system('clear')
    main()