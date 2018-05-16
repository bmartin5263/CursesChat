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

class ChatRoom:

    def __init__(self, name, messageManager, debugger=None):
        self.name = name
        self.messageManager = messageManager
        self.active = False
        self.debug = debugger
        #self.fileManager = fileManager

        self.reader = None
        self.writer = None

        # {'name': string, 'messageSock' : socket, 'fileSock' : socket}
        # index 0 = host
        self.hostSock = None
        self.numUsers = 0
        #self.nextID = 0
        #self.users = [None, None, None, None, None, None, None, None, None, None]

    def console(self, message, messageType=''):
        if self.debug:
            self.debug.console('[Server] ' + message, messageType)

    def closeRoom(self):
        self.active = False
        self.messageManager.terminateGroup(self.name)

    def openRoom(self):
        self.messageManager.addGroup(self.name)
        self.active = True
        self.reader = threading.Thread(target=self.messageReader)
        #self.writer = threading.Thread(target=None)
        self.reader.start()

    def messageReader(self):
        while self.active:
            inbox = self.messageManager.read(self.name)
            for isMessage, sock, message in inbox:
                if isMessage:
                    message = eval(message)
                    if message['type'] == 'chat':
                        print(message['data'])
                else:
                    resource = sock
                    if message == Notification.SOCKET_MOVED:
                        self.console("Socket Moved In".format(message), 'message')
                        if self.hostSock is None:
                            self.hostSock = resource
                            response = Message.compile(Message.ROOM_WELCOME, isHost=True)
                        else:
                            response = Message.compile(Message.ROOM_WELCOME, isHost=False)
                        self.messageManager.write(response, [resource])
                    if message == Notification.CLIENT_DISCONNECTED:
                        self.console("DISCONNECT", "important")

            time.sleep(.1)
        #self.console("Server Reader Ending.", "important")

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
        self.debug.console('[Server] '+message, messageType)

    def createRoom(self, roomName):
        if roomName not in self.rooms:
            self.rooms[roomName] = ChatRoom(roomName, self.messageSocketManager)
            self.rooms[roomName].openRoom()
            self.console("Client made room {}".format(roomName), 'room')
            return True
        else:
            return False

    def messageSocketRouter(self):
        while self.active:
            inbox = self.messageSocketManager.read()
            for isMessage, sock, message in inbox:
                if isMessage:
                    message = eval(message)
                    if message['type'] == 'room':
                        if message['action'] == 'route':
                            if self.rooms[message['data']].numUsers < 10:
                                self.console("Routing Socket to {}".format(message['data']))
                                self.messageSocketManager.moveSocket(sock, message['data'])
                            else:
                                self.console("CANNOT ROUTE SOCK TO {}".format(message['data']), "important")

    def serverReader(self, manager):
        while self.active:
            inbox = manager.read()
            for isMessage, sock, message in inbox:
                if isMessage:
                    message = eval(message)
                    if message['type'] == 'room':
                        if message['action'] == 'get':
                            self.console("Client is requesting rooms", 'room')
                            response = Message.compile(Message.SEND_ROOMS, data=list(self.rooms.keys()))
                            self.serverSocketManager.write(response, [sock])

                        elif message['action'] == 'new':
                            roomName = message['data']
                            success = self.createRoom(roomName)
                            if success:
                                response = Message.compile(Message.NEW_ROOM, canCreate=True, data=message['data'])
                            else:
                                response = Message.compile(Message.NEW_ROOM, canCreate=False, data=message['data'])
                            self.serverSocketManager.write(response, [sock])

                        elif message['action'] == 'join':
                            self.console("Client wants to join room {}".format(message['data']), 'room')
                            roomName = message['data']
                            if roomName in self.rooms:
                                response = Message.compile(Message.JOIN_ROOM, data=roomName, canJoin=True)
                            else:
                                response = Message.compile(Message.JOIN_ROOM, data=roomName, canJoin=False)
                            self.serverSocketManager.write(response, [sock])

                    elif message['type'] == 'chat':
                        self.console("Received Chat Message", "message")
                        response = Message.compile(Message.GLOBAL_CHAT, data=message['data'])
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
        messageRouter = threading.Thread(target=self.messageSocketRouter)
        inboxReader.start()
        messageRouter.start()
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