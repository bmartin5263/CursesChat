import threading
import time
import getopt
import os
import sys
import select
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
    serverAddress = 'localhost'
    c = Client(serverAddress, debugger)
    c.run()

class ChatRoom:

    CHAT_PORT = 24601
    FILE_PORT = 24602

    def __init__(self, name, serverAddress):
        self.username = ""
        self.name = name
        self.serverAddress = serverAddress
        self.messageSock = None
        self.blocks = {}

        self.connected = False
        self.welcomed = False
        self.reader = None
        self.writer = None

        #self.users = []
        self.messageManager = None
        self.fileManager = None
        self.connectedToRoom = False

    def block(self, blockName):
        self.blocks[blockName] = True

    def unBlock(self, blockName):
        try:
            self.blocks[blockName] = False
        except KeyError:
            pass

    def waitForBlock(self, blockName, timeout=60):
        start = time.time()
        while self.blocks[blockName]:
            print("block")
            time.sleep(.1)
            elapsed = time.time() - start
            if elapsed > timeout:
                return False
        del self.blocks[blockName]
        return True

    def chat(self):
        pass

    def chatReader(self):
        while self.connected:
            inbox = self.messageManager.read()
            for isMessage, sock, message in inbox:
                if isMessage:
                    if message['type'] == 'room':
                        if message['action'] == 'welcome':
                            self.welcomed = True

    def chatWriter(self):
        pass

    def join(self):
        self.startChatManagers()
        self.messageSock = self.messageManager.connect(self.serverAddress)
        self.messageManager.write(Message.compile(Message.ROUTE_TO, canRoute=None, data=self.name),[self.messageSock])

        self.block('welcome')
        self.reader = threading.Thread(target=self.chatReader)
        self.reader.start()
        if self.waitForBlock('welcome', 5):
            pass #TODO

        self.messageManager.write(Message.compile(Message.GLOBAL_CHAT, data="HEYYY"), [self.messageSock])

    def startChatManagers(self):
        self.messageManager = SocketManager.actAsClient(port=ChatRoom.CHAT_PORT)

    def stopChatManagers(self):
        self.messageManager.terminateManager()

    def waitForConnection(self, reader, writer):
        try:
            reader.join()
            writer.join()
        except KeyboardInterrupt:
            self.talkingToServer = False
            reader.join()
            writer.join()


class Client:

    SERVER_PORT = 24600

    def __init__(self, serverAddress, debugger=None):
        self.debug = debugger
        self.serverAddress = serverAddress
        self.serverSocketManager = None
        self.messageSocketManager = None
        self.directory = "server"

        self.talkingToServer = False       # Connection to Server is Active
        self.connectionAborted = False      # Connection to Server Unexpectedly Cut Off
        self.inRoom = False                 # Connection to Chat Room is Active
        self.joinRoomName = ""
        self.chatRoom = None

        self.lock = threading.RLock()
        self.blocks = {}

    def block(self, blockName):
        self.blocks[blockName] = True

    def unBlock(self, blockName):
        try:
            self.blocks[blockName] = False
        except KeyError:
            pass

    def waitForBlock(self, blockName):
        while self.blocks[blockName]:
            #print("block")
            time.sleep(.1)
        del self.blocks[blockName]


    def connectToServer(self):
        serverSock = self.serverSocketManager.connect(self.serverAddress)
        self.talkingToServer = True
        reader = threading.Thread(target=self.serverReader)
        writer = threading.Thread(target=self.serverWriter, args=(serverSock,))
        reader.start()
        writer.start()
        return reader, writer

    def console(self, message, messageType=''):
        if self.debug:
            self.debug.console('[Client] '+message, messageType)

    def serverReader(self):
        while self.talkingToServer:
            inbox = self.serverSocketManager.read()
            for isMessage, sock, message in inbox:
                if isMessage:
                    try:
                        message = eval(message)
                        if message['type'] == 'room':
                            if message['action'] == 'get':
                                self.unBlock('getRooms')
                                if message['data']:
                                    print(message['data'])
                            elif message['action'] == 'join':
                                if message['canJoin']:
                                    print("Can Join Room")
                                    self.joinRoomName = message['data']
                                    self.directory = 'chatroom'
                                    self.talkingToServer = False
                                else:
                                    print("Cannot join room {}".format(message['data']))
                                self.unBlock('joinRoom')
                            elif message['action'] == 'new':
                                if message['canCreate']:
                                    print("Room Created")
                                    self.joinRoomName = message['data']
                                    self.directory = 'chatroom'
                                    self.talkingToServer = False
                                else:
                                    print("Couldn't Create Room {}".format(message['data']))
                                self.unBlock('newRoom')
                        elif message['type'] == 'chat':
                            print(message['data'])
                    except SyntaxError:
                        print('syntax error')
                        print(message)
                else:
                    resource = sock
                    self.console("Received Notification {}".format(message), 'message')
                    if message == Notification.SERVER_DISCONNECTED:
                        self.talkingToServer = False
                        break
            time.sleep(.1)
        self.console("Server Reader Ending.", "important")

    def serverWriter(self, serverSock):
        while self.talkingToServer:
            try:
                print("Enter a Command:")
                print("(G)et Rooms")
                print("(J)oin Room")
                print("(N)ew Room")
                print("(C)hat")
                print("(E)xit")
                while True:
                    if select.select([sys.stdin], [], [], 1.0)[0]:
                        command = sys.stdin.readline().strip().lower()
                        if command == 'g':
                            self.block('getRooms')
                            self.serverSocketManager.write(Message.GET_ROOMS.value, socks=[serverSock])
                            self.waitForBlock('getRooms')
                            break
                        elif command == 'n':
                            self.block('newRoom')
                            roomName = sys.stdin.readline().strip()
                            message = Message.compile(Message.NEW_ROOM, data=roomName, canCreate=None)
                            self.serverSocketManager.write(message, socks=[serverSock])
                            self.waitForBlock('newRoom')
                            break
                        elif command == 'c':
                            content = sys.stdin.readline().strip()
                            message = Message.GLOBAL_CHAT.value.format(data=content)
                            self.serverSocketManager.write(message, socks=[serverSock])
                            break
                        elif command == 'e':
                            self.talkingToServer = False
                            self.directory = None
                            raise KeyboardInterrupt
                        elif command == 'j':
                            self.block('joinRoom')
                            roomName = sys.stdin.readline().strip()
                            message = Message.compile(Message.JOIN_ROOM, canJoin=None, data=roomName)
                            self.serverSocketManager.write(message, socks=[serverSock])
                            self.waitForBlock('joinRoom')
                            break
                    else:
                        if not self.talkingToServer:
                            raise KeyboardInterrupt

            except KeyboardInterrupt:
                self.directory = None
                break

    def run(self):
        self.console("Client Started. Attempting Initial Connection...", "important")

        while True:
            if self.directory == 'server':
                self.startServerManager()
                reader, writer = self.connectToServer()
                self.waitForConnection(reader, writer)
                self.stopServerManager()
            elif self.directory == 'chatroom':
                print("Joining Chat Room...")
                c = ChatRoom(self.joinRoomName, self.serverAddress)
                c.join()
                #c.chat()
                break
            else:
                break

        self.console("Exiting client.", "important")

    def startServerManager(self):
        self.serverSocketManager = SocketManager.actAsClient(port=Client.SERVER_PORT, debugger=self.debug)
        self.console("Server Manager Started.", "important")

    def stopServerManager(self):
        self.serverSocketManager.terminateManager()
        self.console("Server Manager Terminated.", "important")

    def waitForConnection(self, reader, writer):
        try:
            reader.join()
            writer.join()
        except KeyboardInterrupt:
            self.talkingToServer = False
            reader.join()
            writer.join()

if __name__ == '__main__':
    os.system('clear')
    main()