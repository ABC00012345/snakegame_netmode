import json
import socket
import threading
import time
import pygame
import random

# netmode


class Game:
    def __init__(self,server_ip):
        pygame.init()
        self.screen_width = 600
        self.screen_height = 600
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption('Snake Game')
        self.font = pygame.font.Font(None, 36)
        self.large_font = pygame.font.Font(None, 45)
        self.TIMEREVENT = pygame.USEREVENT + 1
        self.gameover = True
        self.firstgamestart = True
        self.time_to_play = 60
        self.BACKGROUND_COLOR = (0, 0, 0)
        self.TEXT_COLOR = (255, 255, 255)

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        addr = (server_ip, 5151)
        self.client_socket.connect(addr)
        message = b'hello'
        self.client_socket.sendall(message)
        self.buffer = ""
        self.players_idlist : list



    def set_food_position(self):
        while True:
            x = random.randint(0, 19)
            y = random.randint(0, 19)
            if [x, y] not in self.snake_body:
                return [x, y]

    def init_game(self):
        self.clock = pygame.time.Clock()
        self.game_field = [[0 for _ in range(20)] for _ in range(20)]
        self.snake_position = [5, 5]
        self.snake_body = [[5, 5]]
        self.snake2_position = [10, 10]
        self.snake2_body = [[10, 10]]
        self.food_position = self.set_food_position()
        self.direction = 'RIGHT'
        self.direction2 = 'RIGHT'
        self.snake1die = False
        self.snake2die = False
        self.time_left = self.time_to_play
        pygame.time.set_timer(self.TIMEREVENT, 1000)

        # TODO: Complete client implementation


        sendkeys_thread = threading.Thread(target=self.send_keys)
        sendkeys_thread.start()

        # Start the game state update thread
        game_update_thread = threading.Thread(target=self.update_game_state)
        game_update_thread.start()



        self.game_loop()

    def send_keys(self):
        while not self.gameover:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    pygame.quit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        self.client_socket.sendall(b'UP')
                    elif event.key == pygame.K_DOWN:
                        self.client_socket.sendall(b'DOWN')
                    elif event.key == pygame.K_LEFT:
                        self.client_socket.sendall(b'LEFT')
                    elif event.key == pygame.K_RIGHT:
                        self.client_socket.sendall(b'RIGHT')
            self.clock.tick(8)


    def update_game_state(self):
        while True:
            buff = self.client_socket.recv(4096)
            if not buff:
                break
            self.buffer += buff.decode("utf-8")
            self.process_buffer()

    def process_buffer(self):
        global gameover
        while "\n" in self.buffer:
            # Split the buffer on newline character
            message, self.buffer = self.buffer.split("\n", 1)
            # Parse JSON message
            try:
                game_state = json.loads(message)
                if type(game_state) == list:
                    self.players_idlist = game_state
                else:
                    if "game_start" in game_state.keys():
                        print("Server started game")
                        self.gameover = False
                        self.init_game()
                    elif "servermsg" in game_state.keys():
                        print("Server send message:",game_state["servermsg"])
                    elif "snake_bodies" in game_state.keys():
                        for i in range(len(game_state["snake_bodies"])):
                            for j in game_state["snake_bodies"][i]:
                                print("Snake",i,"Parts:",j)
                    elif "disconnect" in game_state.keys():
                        print("Player disconnected:", game_state["disconnect"])
                print(game_state)
                #self.handle_message(game_state)
            except json.JSONDecodeError:
                print("Received malformed JSON message:", message)


    def game_loop(self):
        running = True
        while running:
            self.active_mainmenu = 0
            if self.gameover:
                self.draw_main_menu()
            while self.gameover:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                        pygame.quit()
                    #elif event.type == pygame.KEYDOWN:
                    #    if event.key == pygame.K_SPACE:
                    #        self.gameover = False
                    #        self.init_game()

            while not self.gameover:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                        pygame.quit()
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_UP and self.direction != 'DOWN':
                            self.direction = 'UP'
                        elif event.key == pygame.K_DOWN and self.direction != 'UP':
                            self.direction = 'DOWN'
                        elif event.key == pygame.K_LEFT and self.direction != 'RIGHT':
                            self.direction = 'LEFT'
                        elif event.key == pygame.K_RIGHT and self.direction != 'LEFT':
                            self.direction = 'RIGHT'
                        if event.key == pygame.K_w and self.direction2 != 'DOWN':
                            self.direction2 = 'UP'
                        elif event.key == pygame.K_s and self.direction2 != 'UP':
                            self.direction2 = 'DOWN'
                        elif event.key == pygame.K_a and self.direction2 != 'RIGHT':
                            self.direction2 = 'LEFT'
                        elif event.key == pygame.K_d and self.direction2 != 'LEFT':
                            self.direction2 = 'RIGHT'
                    elif event.type == self.TIMEREVENT:
                        self.time_left -= 1

                self.draw_game_field()
                self.checktime_over()

                pygame.display.flip()
                self.clock.tick(8)

        pygame.quit()


    def check_collision(self):
        if self.snake_position in self.snake_body[1:]:
            self.snake_body.pop()
            if len(self.snake_body) == 0:
                self.snake1die = True
                self.gameover = True

    def check_collision2(self):
        if self.snake2_position in self.snake2_body[1:]:
            self.snake2_body.pop()
            if len(self.snake2_body) == 0:
                self.snake2die = True
                self.gameover = True

    def checktime_over(self):
        if self.time_left < 1:
            self.gameover = True

    def draw_game_field(self):
        self.screen.fill((0, 0, 0))
        for pos in self.snake_body:
            pygame.draw.rect(self.screen, (0, 255, 0), (pos[0] * 30, pos[1] * 30, 30, 30))
        for pos in self.snake2_body:
            pygame.draw.rect(self.screen, (0, 0, 255), (pos[0] * 30, pos[1] * 30, 30, 30))

        overlapped_fields = [sublist for sublist in self.snake_body if sublist in self.snake2_body]
        for field in overlapped_fields:
            pygame.draw.rect(self.screen, (0, 150, 150), (field[0] * 30, field[1] * 30, 30, 30))

        pygame.draw.rect(self.screen, (255, 0, 0), (self.food_position[0] * 30, self.food_position[1] * 30, 30, 30))
        self.draw_points()

    def draw_points(self):
        points_text = self.font.render("SG-Points: " + str(len(self.snake_body)), True, self.TEXT_COLOR)
        points2_text = self.font.render("SB-Points: " + str(len(self.snake2_body)), True, self.TEXT_COLOR)
        if self.time_to_play < 9999:
            timeleft_text = self.font.render("Time Left: " + str(self.time_left), True, self.TEXT_COLOR)
            timeleft_text_rect = timeleft_text.get_rect(center=(self.screen_width - 80, 70))
            self.screen.blit(timeleft_text, timeleft_text_rect)

        points_text_rect = points_text.get_rect(center=(self.screen_width - 80, 20))
        points2_text_rect = points2_text.get_rect(center=(self.screen_width - 80, 45))
        self.screen.blit(points_text, points_text_rect)
        self.screen.blit(points2_text, points2_text_rect)

    def draw_main_menu(self, collision):
        self.screen.fill(self.BACKGROUND_COLOR)
        title = self.large_font.render("SNAKE Game", True, self.TEXT_COLOR)
        title_rect = title.get_rect(center=(self.screen_width / 2, self.screen_height / 2 - 40))

        if self.time_to_play < 9999:
            text_30sinfo = self.font.render(str(self.time_to_play) + "s Mode", True, self.TEXT_COLOR)
        else:
            text_30sinfo = self.font.render("Unlimited Time Mode", True, self.TEXT_COLOR)
        text30sinfo_rect = text_30sinfo.get_rect(center=(self.screen_width / 2, self.screen_height / 2 - 10))
        self.screen.blit(text_30sinfo, text30sinfo_rect)

        text = self.font.render("Press SPACE to start", True, self.TEXT_COLOR)
        text_rect = text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 + 20))

        points_text = self.font.render("Snake Green Points: " + str(len(self.snake_body)), True, self.TEXT_COLOR)
        points2_text = self.font.render("Snake Blue Points: " + str(len(self.snake2_body)), True, self.TEXT_COLOR)

        who_win = ""
        if collision == -1:
            if len(self.snake2_body) < len(self.snake_body):
                who_win = "green"
            elif len(self.snake_body) < len(self.snake2_body):
                who_win = "blue"
            else:
                who_win = "tie"
        else:
            if collision == 1:
                who_win = "blue"
            elif collision == 2:
                who_win = "green"

        if who_win == "tie":
            player_won_text = self.font.render("Nobody won: Tie", True, self.TEXT_COLOR)
        else:
            player_won_text = self.font.render("Player " + who_win + " won", True, self.TEXT_COLOR)

        points_text_rect = points_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 + 50))
        points2_text_rect = points2_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 + 75))

        if collision != -2:
            player_won_text_rect = player_won_text.get_rect(center=(self.screen_width / 2, self.screen_height / 2 + 100))
            self.screen.blit(player_won_text, player_won_text_rect)

        self.screen.blit(title, title_rect)
        self.screen.blit(text, text_rect)
        self.screen.blit(points_text, points_text_rect)
        self.screen.blit(points2_text, points2_text_rect)
        pygame.display.flip()


if __name__ == "__main__":
    server_ip = input("Enter server ip: ")
    game = Game(server_ip)
    game.init_game()
