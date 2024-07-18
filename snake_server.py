import random
import socket
import time
import select
import sys
import threading
import json
import tkinter as tk
from tkinter import messagebox

### CONSTANTS
SERVER_FPS = 60
UPDATE_INTERVAL = 1 / 8  # Update game state 8 times per second
GAME_LENGTH = 120 # time for a game in seconds
ENABLE_SERVER_GUI = True

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(('0.0.0.0', 5151))
server_socket.listen(4)  # Listen for up to 4 connections

print("Game Lobby created")
print("Waiting for clients to join... Press 'c' to start the game")

client_list = []
# very important list, this list maps all the ips of the clients to players to simply access player resources/modify them
# works like: [[0,"192.168.178.52"],...]
players_idlist = []
# sockets of active players / used for the server to send to all playing clients
client_sockets = {}
game_started = False
lock = threading.Lock()

# blocked ips from server gui
blocked_runtime_ips = []

# Shared game state variables
snakes_position = []
snake_bodies = []
directions = []
food_position = []
game_field = []
snakes_die = []
gameover = False
players_points = []
time_left = 0  # Initialize time_left
running = True


## this is normally no longer needed, because the function below is now introduced to dont longer allow id leaks between
def smallest_possible_clientid(lst):
    if not lst:
        return 0
    i = 0
    while True:
        if i not in lst:
            return i
        i += 1

## this function is used to remap the ids in the players_idlist to use all numbers from 0 and so on and dont have for example a index between 0 and the highest missing if someone disconnects
def remap_players_idlist(lst):
    # Extract and sort the current IDs
    current_ids = sorted([item[0] for item in lst])
    # Generate the new IDs
    new_ids = list(range(len(lst)))
    # Create a mapping from current IDs to new IDs
    id_map = {old_id: new_id for new_id, old_id in enumerate(current_ids)}
    # Create the new list with remapped IDs
    remapped_list = [[id_map[item[0]], item[1]] for item in lst]
    return remapped_list

def set_food_position():
    while True:
        x = random.randint(0, 19)
        y = random.randint(0, 19)
        for snake_body in snake_bodies:
            if [x, y] not in snake_body:
                return [x, y]

def move_snakes():
    global snakes_position
    for playerid, address in players_idlist:
        if address != '0':
            if directions[playerid] == 'UP':
                snakes_position[playerid][1] -= 1
            elif directions[playerid] == 'DOWN':
                snakes_position[playerid][1] += 1
            elif directions[playerid] == 'LEFT':
                snakes_position[playerid][0] -= 1
            elif directions[playerid] == 'RIGHT':
                snakes_position[playerid][0] += 1

            snakes_position[playerid][0] = snakes_position[playerid][0] % 20
            snakes_position[playerid][1] = snakes_position[playerid][1] % 20

def check_if_snakes_on_food_and_update_snakes():
    global food_position, snake_bodies
    need_food_to_be_set = False

    for playerid, address in players_idlist:
        if address != '0':
            snake_bodies[playerid].insert(0, list(snakes_position[playerid]))
            if snakes_position[playerid] == food_position:
                need_food_to_be_set = True
            else:
                snake_bodies[playerid].pop()

    if need_food_to_be_set:
        food_position = set_food_position()

def check_collisions():
    global snakes_die, snake_bodies
    for playerid, address in players_idlist:
        if address != '0':
            if snakes_position[playerid] in snake_bodies[playerid][1:]:
                snake_bodies[playerid].pop()
                if len(snake_bodies[playerid]) == 0:
                    snakes_die[playerid] = True

def checktime_over():
    global gameover
    if time_left < 0:
        gameover = True

def calculate_players_points():
    global players_points
    for playerid, address in players_idlist:
        if address != '0':
            players_points[playerid] = len(snake_bodies[playerid])


def server_gui():
    print("Server GUI starting... To disable server gui, set ENABLE_SERVER_GUI to False")

    def on_closing():
        print("Server GUI Window is closing...")
        window.destroy()  # Close the Tkinter window

    def sendmsg_to_all_clients():
        # Retrieve the content of the input field
        user_message = sendtoall_entry.get()
        print(f"Sending Message to all clients: {user_message}")
        for client_socket in client_sockets.values(): # sending message to all clients
            client_socket.sendall((json.dumps({'servermsg': user_message})+'\n').encode('utf-8'))

    def on_list_item_click_listbox_currentclients(event):
        selected_index = listbox_currentclients.curselection()
        if selected_index:
            selected_item = listbox_currentclients.get(selected_index)

            # Open a new dialog window
            dialog = tk.Toplevel(window)
            dialog.title("Client Options")
            dialog_client_options_body(dialog, selected_item)

    # kick / block client function
    def kick_block_client(client_ip, action): # action either kick or block ## block is same as kick, but with adding client ip to blocked_runtime_ips list
        if action not in ["kick", "block"]: # check first which action given, to dont do wrong things in this function
            return
        with lock:
            if game_started:
                print("Disconnecting client", client_ip)
                if client_ip in client_sockets:
                    client_socket = client_sockets[client_ip]
                    try:
                        # Send kick message to client
                        if action == "kick":
                            client_socket.sendall((json.dumps({'kick': client_ip})+'\n').encode('utf-8'))
                        # send block msg
                        elif action == "block":
                            client_socket.sendall((json.dumps({'block': client_ip})+'\n').encode('utf-8'))
                            blocked_runtime_ips.append(client_ip)

                        time.sleep(0.5)  # Ensure the message is processed
                        ### dont need to check for something else to continue, security check is at beginning of function

                        # Remove the client
                        client_socket.shutdown(socket.SHUT_WR)  # Shutdown the writing side to signal EOF
                        client_socket.close()
                    except Exception as e:
                        print(f"Error kicking client {client_ip}: {e}")
                    
                    # Update server-side lists
                    del client_sockets[client_ip]
                    client_list.remove(client_ip)
                    players_idlist[[i[1] for i in players_idlist].index(client_ip)][1] = '0'
                    
                    # Notify remaining clients
                    for cs in client_sockets.values():
                        cs.sendall((json.dumps({'disconnect': client_ip})+'\n').encode('utf-8'))
                        cs.sendall((json.dumps({"lobby": players_idlist})+'\n').encode('utf-8'))
                
                print("Players:", client_list)
                print("playeridlist:", players_idlist)
            else:
                # Handle kicking clients in the lobby
                print("Disconnecting client", client_ip)
                if client_ip in client_sockets:
                    client_socket = client_sockets[client_ip]
                    try:
                        # Send kick message to client
                        if action == "kick":
                            client_socket.sendall((json.dumps({'kick': client_ip})+'\n').encode('utf-8'))
                        # send block msg
                        elif action == "block":
                            client_socket.sendall((json.dumps({'block': client_ip})+'\n').encode('utf-8'))
                            blocked_runtime_ips.append(client_ip)

                        time.sleep(0.5)  # Ensure the message is processed

                        # Remove the client
                        client_socket.shutdown(socket.SHUT_WR)  # Shutdown the writing side to signal EOF
                        client_socket.close()
                    except Exception as e:
                        print(f"Error kicking client {client_ip}: {e}")

                    # Update server-side lists
                    del client_sockets[client_ip]
                    client_list.remove(client_ip)
                    del players_idlist[[i[1] for i in players_idlist].index(client_ip)]
                    
                    # Notify remaining clients
                    for cs in client_sockets.values():
                        cs.sendall((json.dumps({'disconnect': client_ip})+'\n').encode('utf-8'))
                        cs.sendall((json.dumps({"lobby": players_idlist})+'\n').encode('utf-8'))
                
                print("Players:", client_list)
                print("playeridlist:", players_idlist)

    def dialog_client_options_body(dialog, selected_client):
        dialog.geometry("300x150")
        label = tk.Label(dialog, text=f"Client: {selected_client}")
        label.pack(pady=10)

        def button_action(action):
            ############# [+] fixed!! ------------------  kick action need to be fixed!!!! client doesnt get notified about kick!!
                if action == "kick":
                    kick_block_client(selected_client, "kick")
                    messagebox.showinfo("Kick Action", f"Client '{selected_client}' has been kicked.")

                elif action == "block":
                    kick_block_client(selected_client, "block")
                    messagebox.showinfo("Block Action", f"Client '{selected_client}' has been blocked.")
                    
                    
                dialog.destroy()

        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=10)
        
        kick_client_btn = tk.Button(button_frame, text="Kick", command=lambda: button_action("kick"))
        kick_client_btn.grid(row=0, column=0, padx=5)
        
        block_client_btn = tk.Button(button_frame, text="Block", command=lambda: button_action("block"))
        block_client_btn.grid(row=0, column=1, padx=5)

    # Initialize the Tkinter window
    window = tk.Tk()
    window.title("Server GUI")
    window.geometry("400x400")

    # GUI components setup
    sendtoall_label = tk.Label(window, text="Send messages to all clients", font=("Helvetica", 14))
    sendtoall_label.pack(pady=5)  # Add vertical padding around the label

    # Create an Entry widget for input with full width and margins
    sendtoall_entry = tk.Entry(window, font=("Helvetica", 12))
    sendtoall_entry.pack(fill=tk.X, padx=15)  # Fill the width and add horizontal padding

    # Create a Button widget and bind it to the sendmsg_to_all_clients function
    sendtoall_btn = tk.Button(window, text="Send", command=sendmsg_to_all_clients, font=("Helvetica", 12))
    sendtoall_btn.pack(pady=5)  # Add vertical padding around the button

    player_label = tk.Label(window, text="Players in Lobby:", font=("Helvetica", 14))
    player_label.pack()  # Add vertical padding around the label

    listbox_currentclients = tk.Listbox(window)
    listbox_currentclients.pack(pady=5)
    listbox_currentclients.bind("<<ListboxSelect>>", on_list_item_click_listbox_currentclients) # listbox bind, to get listbox item click event associated with function

    # Bind the close event to the on_closing function
    window.protocol("WM_DELETE_WINDOW", on_closing)

    # Check if running=False, means that threads are finishing
    def exit_tkinter_check():
        if not running:
            window.destroy()
            return
        window.after(500, exit_tkinter_check)

    def updatelist_currentclients():
        listbox_currentclients.delete(0, tk.END)
        # get current clients
        for i in players_idlist:
            if i[1] != '0': # means disconnected inside game, server cant remove fully from the list, otherwise server wont work
                listbox_currentclients.insert(tk.END, i[1])
        window.after(1000, updatelist_currentclients)

    window.after(500, exit_tkinter_check)
    window.after(500, updatelist_currentclients)
    
    # Run the Tkinter event loop
    window.mainloop()


def handle_client_communication():
    global directions, client_sockets, client_list, players_idlist, running
    while running:
        sockets_to_check = list(client_sockets.values()) + [server_socket] # also include server socket to handle new clients connecting during game

        try:
            rlist, _, _ = select.select(sockets_to_check, [], [], 1 / SERVER_FPS)
        except ValueError:
            continue

        for sock in rlist:
            for client, client_socket in list(client_sockets.items()):
                
                if sock == client_socket:
                    try:
                        message = client_socket.recv(1024)
                        if not message:
                            raise ConnectionResetError()
                        
                        message = message.decode('utf-8')
                        print(str(client) + ": " + message)

                        if message == 'disconnect':
                            print("Disconnecting client", client)
                            client_socket.close()
                            del client_sockets[client]
                            client_list.remove(client)
                            players_idlist[[i[1] for i in players_idlist].index(client)][1] = '0'
                            for client_socket in client_sockets.values():
                                client_socket.sendall((json.dumps({'disconnect': client})+'\n').encode('utf-8'))
                                ## sending to all players in lobby new state:
                                client_socket.sendall((json.dumps({"lobby":players_idlist})+'\n').encode("utf-8")) # sending list of players with their ids to all
                            print("Players:", client_list)
                            break

                        ## handle client keys that are sent
                        player_index = players_idlist[[i[1] for i in players_idlist].index(client)][0]
                        if message == 'UP' and directions[player_index] != 'DOWN':
                            directions[player_index] = 'UP'
                        elif message == 'DOWN' and directions[player_index] != 'UP':
                            directions[player_index] = 'DOWN'
                        elif message == 'LEFT' and directions[player_index] != 'RIGHT':
                            directions[player_index] = 'LEFT'
                        elif message == 'RIGHT' and directions[player_index] != 'LEFT':
                            directions[player_index] = 'RIGHT'
                        
                    except (ConnectionResetError, BrokenPipeError):
                        print("Client disconnected unexpectedly:", client)
                        client_socket.close()
                        del client_sockets[client]
                        client_list.remove(client)
                        players_idlist[[i[1] for i in players_idlist].index(client)][1] = '0'
                        # remove snake from game and inform other players/clients
                        for client_socket in client_sockets.values():
                            client_socket.sendall((json.dumps({'disconnect': client})+'\n').encode('utf-8'))
                            ## sending to all players in lobby new state:
                            client_socket.sendall((json.dumps({"lobby":players_idlist})+'\n').encode("utf-8")) # sending list of players with their ids to all
                        print("Players:", client_list)
                        break
                elif sock == server_socket:
                    client_socket, address = server_socket.accept()
                    print("Connected by", address)
                    client_socket.sendall((json.dumps({'gamerunning': ''})+'\n').encode('utf-8'))
                    client_socket.close()
                    print(f"Disconnected",address[0],"because joined during a running game or at the end of a game")
                    continue

        time.sleep(1 / SERVER_FPS)
    

def update_game_state():
    global time_left, running
    while running:
        if game_started:
            print("Updating game state")
            
            # game logic
            move_snakes()
            check_if_snakes_on_food_and_update_snakes()
            check_collisions()
            checktime_over()
            calculate_players_points()

            if gameover:
                print("Gameover")
                # calc winners
                max_value = max([len(i) for i in snake_bodies])
                players_won = [index for index, value in enumerate([len(i) for i in snake_bodies]) if value == max_value] # Get indexes of the max value

                playerswithpoints = {}
                ### prepare sending points and winner to all clients
                for playerid, address in players_idlist:
                    if address != '0':
                        playerswithpoints.update({playerid : players_points[playerid]})

                for client_socket in client_sockets.values():
                    client_socket.sendall((json.dumps({'gameover': {'winner' : players_won, 'playerswithpoints' : playerswithpoints}})+'\n').encode('utf-8'))

                ## end everything
                user_input = ""
                while user_input != 'c':
                    user_input = input("Game finished, do you want to close the server? then press 'c' and enter, if not, you may choose to wait a while: ")
                if user_input == 'c':
                    ## notify all clients that will the server exit
                    for client_socket in client_sockets.values():
                        client_socket.sendall((json.dumps({'serverexit': ''})+'\n').encode('utf-8'))
                    running = False # stopping the while loop
                
                #print("Exit in 5 seconds ...") # exit, because nothing happen after gameover
                #time.sleep(5)
                #sys.exit(0)

            ### TODO: Need to implement time_left [+] and gameover states [+], to send gameover to client. Also need to implement player disconnect, to inform other clients [+]

            # Send the updated game state to all clients
            game_state = {
                'snake_bodies': snake_bodies,
                'food_position': food_position,
                'timeleft': time_left,
                'points': players_points
            }
            game_state = json.dumps(game_state) + '\n'
            for client_socket in client_sockets.values():
                client_socket.sendall(game_state.encode('utf-8'))

        time_left -= UPDATE_INTERVAL
        time.sleep(UPDATE_INTERVAL)

def start_server():
    global game_started, snakes_position, snake_bodies, directions, food_position, game_field, time_left, snakes_die, players_points, tkinterexit, players_idlist

    # Game Lobby loop
    while not game_started:
        ## need to be with lock, because if for example player get kicked then the client_sockets get modified
        with lock:
            rlist, _, _ = select.select([sys.stdin, server_socket] + list(client_sockets.values()), [], [], 0)
        for sock in rlist:
            if sock == sys.stdin:
                key = sys.stdin.read(1)
                if key == 'c':
                    print("Starting game with players:", client_list)
                    game_started = True
            elif sock == server_socket:
                client_socket, address = server_socket.accept()
                print("Connected by", address)
                ### check directly if ip banned, send a ban message and close the connection
                if address[0] in blocked_runtime_ips:
                    client_socket.sendall((json.dumps({'block': address[0]})+'\n').encode('utf-8'))
                    print(f"Rejected connection from {address[0]} due to ban")
                    client_socket.close()
                    continue

                if not address[0] in client_list: # check if not already connected from same ip
                    client_list.append(address[0])
                    client_sockets[address[0]] = client_socket
                    print("Client", address[0], "joined!")
                    ######### the smallest_possible_clientid function is no longer needed, because new remap function at top is introduced
                    players_idlist.append([smallest_possible_clientid([i[0] for i in players_idlist]), address[0]])
                    print("Players:", client_list)
                    print("playeridlist", players_idlist)
                    ## sending new state to all clients
                    for client_socket in client_sockets.values():
                        client_socket.sendall((json.dumps({'join': address[0]})+'\n').encode('utf-8'))
                        ## sending to all players in lobby new state:
                        client_socket.sendall((json.dumps({"lobby":players_idlist})+'\n').encode("utf-8")) # sending list of players with their ids to all
                else:
                    print("Client", address[0], "already connected...closing connection")
                    client_socket.close()
            else:
                for client, client_socket in list(client_sockets.items()):
                    if sock == client_socket:
                        try:
                            message = client_socket.recv(1024)
                            if not message:
                                raise ConnectionResetError()
                            
                            message = message.decode('utf-8')
                            print(str(client) + ": " + message)
                            
                            if message == 'disconnect':
                                client_socket.close()
                                print("Disconnecting client", client)
                                client_list.remove(client)
                                del client_sockets[client]
                                del players_idlist[[i[1] for i in players_idlist].index(client)]
                                ## remap list!
                                players_idlist = remap_players_idlist(players_idlist)
                                print("Players:", client_list)
                                print("playeridlist:", players_idlist)
                                ## sending new state to all clients
                                for client_socket in client_sockets.values():
                                    client_socket.sendall((json.dumps({'disconnect': client})+'\n').encode('utf-8'))
                                    ## sending to all players in lobby new state:
                                    client_socket.sendall((json.dumps({"lobby":players_idlist})+'\n').encode("utf-8")) # sending list of players with their ids to all
                                break
                            
                            client_socket.sendall((json.dumps({'servermsg':'hello'})+"\n").encode('utf-8'))
                        
                        except (ConnectionResetError, BrokenPipeError):
                            print("Client disconnected unexpectedly:", client)
                            client_socket.close()
                            del client_sockets[client]
                            client_list.remove(client)
                            del players_idlist[[i[1] for i in players_idlist].index(client)]
                            ## remap list!
                            players_idlist = remap_players_idlist(players_idlist)
                            print("Players:", client_list)
                            print("playeridlist:", players_idlist)
                            ## sending new state to all clients
                            for client_socket in client_sockets.values():
                                client_socket.sendall((json.dumps({'disconnect': client})+'\n').encode('utf-8'))
                                ## sending to all players in lobby new state:
                                client_socket.sendall((json.dumps({"lobby":players_idlist})+'\n').encode("utf-8")) # sending list of players with their ids to all
                            break

    if game_started:
        # Send "game_start" to all clients
        for client_socket in client_sockets.values():
            client_socket.sendall((json.dumps({"game_start":""})+'\n').encode("utf-8"))
            client_socket.sendall((json.dumps({"lobby":players_idlist})+'\n').encode("utf-8"))

        print("Game started!")

        client_list_map = {}
        print(client_sockets)
        for i, j in enumerate(client_list):
            print(i, j)
            client_list_map.update({i: j})

        print("client list:",client_list)
        
        
        time_to_play = float(GAME_LENGTH)
        time_left = time_to_play
        game_field = [[0 for _ in range(20)] for _ in range(20)]
        snakes_position = [[3, 3], [7, 7], [11, 11], [15, 15]]
        snake_bodies = [[[3, 3]], [[7, 7]], [[11, 11]], [[15, 15]]]  # Initialize with single segment per snake
        snake_bodies = snake_bodies[:len(client_list)]
        snakes_position = snakes_position[:len(client_list)]
        snakes_die = [False] * len(client_list)
        players_points = [1] * len(client_list)
        food_position = set_food_position()
        directions = ['RIGHT'] * len(client_list)


        # Start the client communication thread
        communication_thread = threading.Thread(target=handle_client_communication)
        communication_thread.start()

        # Start the game state update thread
        game_update_thread = threading.Thread(target=update_game_state)
        game_update_thread.start()


        # Wait for threads to complete before exiting
        communication_thread.join()
        game_update_thread.join()
        

        ### after threads are done, if running was set to False, stop all sockets  and socket connections
        for client_socket in client_sockets.values():
            client_socket.close()
        server_socket.close()
        print("Server sockets / Client sockets closed")

if __name__ == "__main__":
    startserver_thread = threading.Thread(target=start_server)
    startserver_thread.start()
    #start_server()
    if ENABLE_SERVER_GUI:
        server_gui()
    startserver_thread.join()
    print("Thread finsihed")

    print("SERVER EXIT")