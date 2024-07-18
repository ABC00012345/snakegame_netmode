from collections import Counter
import json
import os
import socket
import subprocess
import sys
import pygame
import random
from tkinter import *
from tkinter import messagebox

class Game:
    def __init__(self, server_ip):
        pygame.init()
        self.screen_width = 600
        self.screen_height = 600
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption('Snake Game')
        self.small_font = pygame.font.Font(None, 24)
        self.font = pygame.font.Font(None, 36)
        self.large_font = pygame.font.Font(None, 45)
        self.gameover = True
        self.firstgamestart = True
        self.BACKGROUND_COLOR = (0, 0, 0)
        self.TEXT_COLOR = (255, 255, 255)
        self.OVERLAP_COLOR = (150,75,0)
        self.time_left = 30 # changes later by server time
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        addr = (server_ip, 5151)
        try:
            self.client_socket.settimeout(2.5)
            self.client_socket.connect(addr)
            self.client_socket.settimeout(None)
        except (ConnectionRefusedError, OSError) as e:
            Tk().wm_withdraw() #to hide the main window
            messagebox.showinfo('Connection Error','Click OK to restart. Error Message:\n' + str(e))
            pygame.quit()
            script_name = sys.argv[0]
            subprocess.Popen([sys.executable, script_name])
            sys.exit(0)

        message = b'hello' # testmsg
        self.client_socket.sendall(message)
        self.buffer = ""
        self.players = []
        self.players_idlist = []
        self.snake_colors = []
        self.messages = {}
        self.MESSAGE_TIMOUT = 5

        # stop client from hanging up, if no data received
        self.client_socket.setblocking(False)

        # Initialize empty state variables
        self.snake_bodies = []
        self.food_position = []
        self.points = []

        ### init the snake colors
        self.snake_colors = [
            (0, 255, 0),  # Green
            (0, 0, 255),  # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (255, 165, 0),  # Orange
        ]
        self.snake_color_names = ["green","blue","yellow","magenta","cyan","orange"]


    def init_game(self):
        self.clock = pygame.time.Clock()
        self.game_loop()

    def process_buffer(self):
        while "\n" in self.buffer:
            message, self.buffer = self.buffer.split("\n", 1)
            try:
                server_data = json.loads(message)
                ### warning: if more data types added, client may cant handle them
                #print(server_data) # uncomment to enable debug messages
                if type(server_data) == dict:
                    if "game_start" in server_data.keys():
                        print("Server started game")
                        self.gameover = False
                    elif "servermsg" in server_data.keys():
                        print("Server sent message:", server_data["servermsg"])
                        self.messages.update({"Server message: "+server_data["servermsg"]:self.MESSAGE_TIMOUT}) # sending message to screen for MESSAGE_TIMOUT seconds
                    elif "snake_bodies" in server_data.keys():
                        self.snake_bodies = server_data["snake_bodies"]
                        self.food_position = server_data["food_position"]
                        self.time_left = server_data["timeleft"]
                        self.points = server_data["points"]
                    elif "gameover" in server_data.keys(): # gameover dict will look like: {'gameover': {'winner': [0], 'playerswithpoints': {'1'/*playerid*/: 10/*points*/,...}}}
                        print("Game over, winners:", server_data["gameover"]["winner"])
                        self.display_winners(server_data["gameover"]["winner"], server_data["gameover"]["playerswithpoints"])
                        self.gameover = True
                    elif "disconnect" in server_data.keys():
                        print("Player disconnected:", server_data["disconnect"])
                        self.messages.update({"Player disconnected: "+server_data["disconnect"]:self.MESSAGE_TIMOUT}) # sending message to screen for MESSAGE_TIMOUT seconds
                    elif "lobby" in server_data.keys():
                        self.players_idlist = server_data["lobby"]
                        print("Updated player id list")
                    elif "join" in server_data.keys():
                        print("Player joined:",server_data["join"])
                        self.messages.update({"Player joined: "+server_data["join"]:self.MESSAGE_TIMOUT}) # sending message to screen for MESSAGE_TIMOUT seconds
                    elif "serverexit" in server_data.keys():
                        self.messages.update({"Server will shutdown":self.MESSAGE_TIMOUT}) # sending message to screen for MESSAGE_TIMOUT seconds
                        Tk().wm_withdraw() #to hide the main window
                        messagebox.showinfo('Server message','Server will shutdown. Click OK to restart the client')
                        pygame.quit()
                        script_name = sys.argv[0]
                        subprocess.Popen([sys.executable, script_name])
                        sys.exit(0)
                    elif "kick" in server_data.keys():
                        Tk().wm_withdraw() #to hide the main window
                        messagebox.showinfo('Server message','You have been kicked out of the server. Click OK to restart the client')
                        pygame.quit()
                        script_name = sys.argv[0]
                        subprocess.Popen([sys.executable, script_name])
                        sys.exit(0)
                    elif "block" in server_data.keys():
                        Tk().wm_withdraw() #to hide the main window
                        messagebox.showinfo('Server message','You have been blocked out of the server. You cannot rejoin into this server!! Click OK to restart the client')
                        pygame.quit()
                        script_name = sys.argv[0]
                        subprocess.Popen([sys.executable, script_name])
                        sys.exit(0)
                    elif "gamerunning" in server_data.keys():
                        Tk().wm_withdraw() #to hide the main window
                        messagebox.showinfo('Server message','The server is currently running a game, you can only join in lobby. Click OK to restart the client')
                        pygame.quit()
                        script_name = sys.argv[0]
                        subprocess.Popen([sys.executable, script_name])
                        sys.exit(0)
                    

            except json.JSONDecodeError:
                print("Received malformed JSON message:", message)

    def show_messages(self): # function to show messages from server on the screen bottom right
        for i,msg in enumerate(list(self.messages.keys())[::-1]):
            message_text = self.small_font.render(msg, True, self.TEXT_COLOR)
            message_text_rect = message_text.get_rect(center=(self.screen_width - len(msg)*5, self.screen_height - 10 - i * 20))
            self.screen.blit(message_text, message_text_rect)
            self.messages[msg] -= 1/8 # update screen time
            if self.messages[msg] < 0:
                del self.messages[msg]

    def game_loop(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    pygame.quit()
                    self.client_socket.sendall(b'disconnect')
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE: pygame.quit();script_name = sys.argv[0];subprocess.Popen([sys.executable, script_name]);sys.exit(0) # restart program
                elif event.type == pygame.KEYDOWN and not self.gameover:
                    if event.key == pygame.K_UP:
                        self.client_socket.sendall(b'UP')
                    elif event.key == pygame.K_DOWN:
                        self.client_socket.sendall(b'DOWN')
                    elif event.key == pygame.K_LEFT:
                        self.client_socket.sendall(b'LEFT')
                    elif event.key == pygame.K_RIGHT:
                        self.client_socket.sendall(b'RIGHT')

            try:
                buff = self.client_socket.recv(4096)
                if buff:
                    self.buffer += buff.decode("utf-8")
                    self.process_buffer()
            ### noticed that blockingioerror is caused all time, so removed disconnection exception handling
            except (BlockingIOError) as e: #,ConnectionResetError) as e: # recv data error or issue with server ### connectionreseterror/blockingioerror handling removed, because it cause the client not able to hold the connection
                #Tk().wm_withdraw() # to hide the main window
                #messagebox.showinfo('Connection Error','Click OK to restart. Error Message:\n' + str(e))
                #pygame.quit()
                #script_name = sys.argv[0]
                #subprocess.Popen([sys.executable, script_name])
                #sys.exit(0)
                pass

            if self.gameover:
                self.draw_main_menu()
            else:
                self.draw_game_field()

            self.show_messages()

            pygame.display.flip()
            self.clock.tick(8)

        pygame.quit()

    def draw_game_field(self):
        self.screen.fill((0, 0, 0))
        for idx, snake_body in enumerate(self.snake_bodies):
            for pos in snake_body:
                pygame.draw.rect(self.screen, self.snake_colors[idx], (pos[0] * 30, pos[1] * 30, 30, 30))


        ##### handling overlapped fields
        # Flatten the list and convert sublists to tuples of coordinates
        flattened_fields = [tuple(coordinate) for body in self.snake_bodies for coordinate in body]
        # Count occurrences of each field
        field_counts = Counter(flattened_fields)
        # Find fields with more than one occurrence
        fields_more_than_one = [field for field, count in field_counts.items() if count > 1]
        #print("Fields occupied by more than one snake:")
        for field in fields_more_than_one:
            pygame.draw.rect(self.screen, self.OVERLAP_COLOR, (field[0] * 30, field[1] * 30, 30, 30))
            #print(field, end=" ")
        #print("")
        #######

        if self.food_position:
            pygame.draw.rect(self.screen, (255, 0, 0), (self.food_position[0] * 30, self.food_position[1] * 30, 30, 30))
        
        self.draw_points()

    def draw_points(self):
        # draw players points
        for i, points in enumerate(self.points):
            player_ip = self.players_idlist[i][1]
            color_name = self.snake_color_names[i]
            points_text = self.small_font.render(f"{color_name} ({player_ip}): {points}", True, self.TEXT_COLOR)
            points_text_rect = points_text.get_rect(center=(self.screen_width - 100, 15 + i * 18))
            self.screen.blit(points_text, points_text_rect)

        timeleft_text = self.font.render("Time Left: " + str(round(self.time_left)), True, self.TEXT_COLOR) # timeleft is rounded for better user experience
        timeleft_text_rect = timeleft_text.get_rect(center=(self.screen_width - 76, 100))
        self.screen.blit(timeleft_text, timeleft_text_rect)

    def draw_main_menu(self):
        self.screen.fill(self.BACKGROUND_COLOR)
        title = self.large_font.render("SNAKE Game", True, self.TEXT_COLOR)
        title_rect = title.get_rect(center=(self.screen_width / 2, self.screen_height / 2 - 60))

        try:
            serverip_text = self.font.render("Connected to Server: "+self.client_socket.getpeername()[0], True, self.TEXT_COLOR)
            serverip_text_rect = serverip_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 - 32))
        except OSError: # oserror exception may occur sometimes if client is banned and the block message is received to late and client_socket.getpeername() is called
            return

        text = self.font.render("Waiting for server to start...", True, self.TEXT_COLOR)
        text_rect = text.get_rect(center=(self.screen_width / 2, self.screen_height / 2))

        restart_info = self.font.render("Click SPACE to restart client", True, self.TEXT_COLOR)
        restart_info_rect = restart_info.get_rect(center=(self.screen_width / 2, self.screen_height / 2 + 25))

        if self.players_idlist:  ## if player list isnt empty draw it with its conatining players to the main menu, but the check is normally unnecessary
            player_text = self.font.render(f"Players:", True, self.TEXT_COLOR)
            player_text_rect = player_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 + 55))
            self.screen.blit(player_text, player_text_rect)
            for i, (playerid, playerip) in enumerate(self.players_idlist):
                if playerip != "0": # the server sets the ip to 0, if a client disconnects instead to remove it fully, here is it handled
                    color_name = self.snake_color_names[playerid]
                    playerentry_text = self.font.render(f"{color_name} ({playerip})", True, self.TEXT_COLOR)
                    playerentry_text_rect = playerentry_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 + 85 + i * 25))
                    self.screen.blit(playerentry_text, playerentry_text_rect)

        ## draw lobby chat info
        lobby_chat_info = self.small_font.render("Enter a mesage to send to all clients:", True, self.TEXT_COLOR)
        lobby_chat_info_rect = lobby_chat_info.get_rect(center=(148, self.screen_height / 2 + 120))

        ##### need to be implemented ####

        # draw players points
        for i, points in enumerate(self.points):
            player_ip = self.players_idlist[i][1]
            color_name = self.snake_color_names[i]
            points_text = self.small_font.render(f"{color_name} ({player_ip}): {points}", True, self.TEXT_COLOR)
            points_text_rect = points_text.get_rect(center=(self.screen_width - 100, 15 + i * 18))
            self.screen.blit(points_text, points_text_rect)



        self.screen.blit(title, title_rect)
        self.screen.blit(serverip_text, serverip_text_rect)
        self.screen.blit(text, text_rect)
        self.screen.blit(restart_info, restart_info_rect)
        self.screen.blit(lobby_chat_info, lobby_chat_info_rect)
        pygame.display.flip()

    def display_winners(self, winners, playerswithpoints):
        self.screen.fill(self.BACKGROUND_COLOR)
        winner_ips = [self.players_idlist[int(winner)][1] for winner in winners]
        winner_texts = [self.font.render(f"Winner: {self.snake_color_names[winner]} ({winner_ips[i]})", True, self.TEXT_COLOR)
                        for i, winner in enumerate(winners)]
        
        all_players_text = self.font.render(f"All Players:", True, self.TEXT_COLOR)
        

        #print("Players id list:",self.players_idlist)
        #print("Playerswithpoints:",playerswithpoints)
        # display all players beside the winners, including also the winners
        ############################################################################################## || get ip of id from players_idlist ||
        all_players_stats_texts = [self.font.render(f"{self.snake_color_names[int(playerid)]} ({self.players_idlist[[i[0] for i in self.players_idlist].index(int(playerid))][1]}), Points: {playerswithpoints[playerid]}", True, self.TEXT_COLOR)
                        for playerid in playerswithpoints]
        

        for i, winner_text in enumerate(winner_texts):
            winner_text_rect = winner_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 + i * 30))
            self.screen.blit(winner_text, winner_text_rect)

        all_players_text_rect = all_players_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 + 30 * len(winner_texts) + 10))
        self.screen.blit(all_players_text, all_players_text_rect)

        for i, player_stat_text in enumerate(all_players_stats_texts):
            player_stat_text_rect = player_stat_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 + 30 * len(winner_texts) + 40 + i * 30))
            self.screen.blit(player_stat_text, player_stat_text_rect)
        

        pygame.display.flip()
        pygame.time.wait(5000) # waiting a bit on player won screen

if __name__ == "__main__":
    pygame.init()

    # Set up display
    WIDTH, HEIGHT = 640, 480
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Snake Game - Server IP Input')

    # Colors
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)

    # Font
    font = pygame.font.Font(None, 40)  # Larger font for the title

    # Input field state
    entered_ip = ''
    active = True  # Directly active, no need to click to activate

    # Run the game loop
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            
            if event.type == pygame.KEYDOWN:
                if active:
                    if event.key == pygame.K_RETURN:
                        # Finish input
                        print(f'IP entered: {entered_ip}')
                        running = False  # Exit the loop
                    elif event.key == pygame.K_BACKSPACE:
                        entered_ip = entered_ip[:-1]
                    else:
                        # Add character to entered_ip
                        if event.unicode.isprintable():  # Ensure that the character is printable
                            entered_ip += event.unicode

        # Draw everything
        screen.fill(BLACK)
        
        # Render title
        title_text = "Enter server IP:"
        title_surface = font.render(title_text, True, WHITE)
        screen.blit(title_surface, (100, 200))  # Positioning the title

        # Render entered text
        entered_text_surface = font.render(entered_ip, True, WHITE)
        screen.blit(entered_text_surface, (100, 240))  # Position the text below the title

        pygame.display.flip()

    # Initialize and start the game after the loop ends
    pygame.quit()
    game = Game(entered_ip)
    game.init_game()