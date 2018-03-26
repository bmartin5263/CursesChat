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

class Client:

    SERVER_PORT = 24600
    CHAT_PORT = 24601
    FILE_PORT = 24602

    def __init__(self, serverAddress, debugger=None):
        self.debug = debugger
        self.serverAddress = serverAddress
        self.serverSocketManager = None
        self.messageSocketManager = None

        self.connectionActive = False       # Connection to Server is Active
        self.connectionAborted = False      # Connection to Server Unexpectedly Cut Off
        self.inRoom = False                 # Connection to Chat Room is Active
        self.joinRoom = False               # Client is Going to Join a Chat Room
        self.joinRoomName = ""
        self.chatRoom = None

        self.lock = threading.RLock()

    def connectToRoom(self):
        pass

    def connectToServer(self):
        serverSock = self.serverSocketManager.connect(self.serverAddress)
        self.connectionActive = True
        reader = threading.Thread(target=self.serverReader)
        writer = threading.Thread(target=self.serverWriter, args=(serverSock,))
        reader.start()
        writer.start()
        return reader, writer

    def console(self, message, messageType=''):
        if self.debug:
            self.debug.console(message, messageType)

    def serverReader(self):
        while self.connectionActive:
            inbox = self.serverSocketManager.read()
            for isMessage, sock, message in inbox:
                if isMessage:
                    try:
                        message = eval(message)
                        if message['type'] == 'room':
                            if message['action'] == 'get':
                                if message['data']:
                                    print(message['data'])
                        elif message['type'] == 'chat':
                            print(message['data'])
                    except SyntaxError:
                        print('syntax error')
                        print(message)
                else:
                    resource = sock
                    self.console("Received Notification {}".format(message), 'message')
                    if message == Notification.SERVER_DISCONNECTED:
                        self.connectionActive = False
                        break
            time.sleep(.1)
        self.console("Server Reader Ending.", "important")

    def serverWriter(self, serverSock):
        while self.connectionActive:
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
                            self.serverSocketManager.write(Message.GET_ROOMS.value, socks=[serverSock])
                            break
                        elif command == 'n':
                            roomName = sys.stdin.readline().strip()
                            message = Message.NEW_ROOM.value.format(roomName)
                            self.serverSocketManager.write(message, socks=[serverSock])
                            break
                        elif command == 'c':
                            content = sys.stdin.readline().strip()
                            message = Message.CHAT.value.format(content)
                            self.serverSocketManager.write(message, socks=[serverSock])
                            break
                        elif command == 'e':
                            self.connectionActive = False
                            raise KeyboardInterrupt
                        elif command == 'j':
                            # TODO get valid room name and set 'joinRoom' flag to true
                            pass
                    else:
                        if not self.connectionActive:
                            raise KeyboardInterrupt

            except KeyboardInterrupt:
                break

    def run(self):
        self.console("Client Started. Attempting Initial Connection...", "important")
        self.startServerManager()

        while True:
            reader, writer = self.connectToServer()
            self.waitForConnection(reader, writer)
            if self.connectionAborted:
                pass
            else:
                if self.joinRoom:
                    pass
                else:
                    break

        self.stopServerManager()
        self.console("Exiting client.", "important")

    def startChatManagers(self):
        self.serverSocketManager = SocketManager.actAsClient(port=Client.CHAT_PORT, debugger=self.debug)
        self.console("Chat Manager Started.", "important")

    def stopChatManagers(self):
        self.serverSocketManager.terminateManager()
        self.console("Chat Manager Terminated.", "important")

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
            self.connectionActive = False
            reader.join()
            writer.join()

if __name__ == '__main__':
    os.system('clear')
    main()