from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, join_room, leave_room
import random
import time
import eventlet

# Initialize Flask and Flask-SocketIO
app = Flask(__name__)
socketio = SocketIO(app)

# Game data
games = {}  # Store multiple games by game code

def assign_roles(players, num_mafia):
    """Randomly assign Mafia and the rest Residents."""
    player_ids = list(players.keys())
    mafia_ids = random.sample(player_ids, num_mafia)
    for pid in player_ids:
        if pid in mafia_ids:
            players[pid]['role'] = 'Mafia'
        else:
            players[pid]['role'] = 'Resident'

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('index.html')

@app.route('/create_game', methods=['POST'])
def create_game():
    """API endpoint to create a new game with a unique game code."""
    game_code = request.json['game_code']
    if game_code in games:
        return jsonify({"error": "Game with this code already exists!"}), 400
    games[game_code] = {'players': {}, 'started': False}
    return jsonify({"message": f"Game {game_code} created successfully!"}), 200

@socketio.on('join_game')
def join_game(data):
    """Handle a player joining a game."""
    game_code = data['game_code']
    username = data['username']
    sid = request.sid

    if game_code not in games:
        socketio.emit('error', {'message': 'Invalid game code'}, room=sid)
        return

    game = games[game_code]
    if game['started']:
        socketio.emit('error', {'message': 'Game already started'}, room=sid)
        return

    # Add player to the game
    game['players'][sid] = {'username': username, 'role': None}
    join_room(game_code)

    # Notify all players in the room
    socketio.emit('player_joined', {'username': username, 'total_players': len(game['players'])}, room=game_code)

@socketio.on('start_game')
def start_game(data):
    """Start the game when the host clicks 'Start Game'."""
    game_code = data['game_code']
    num_mafia = data['num_mafia']
    game = games[game_code]

    if game['started']:
        return

    # Only proceed if there are enough players
    if len(game['players']) < 4:
        socketio.emit('error', {'message': 'At least 4 players are required to start the game.'}, room=request.sid)
        return

    socketio.emit('countdown', {'message': 'Game starting in 5 seconds...'}, room=game_code)
    time.sleep(5)

    # Assign roles
    assign_roles(game['players'], num_mafia)

    # Notify each player of their role
    for sid, player_data in game['players'].items():
        role = player_data['role']
        socketio.emit('role_assignment', {'role': role}, room=sid)

    game['started'] = True
    socketio.emit('game_started', {'message': 'The game has started!'}, room=game_code)

@socketio.on('disconnect')
def handle_disconnect():
    """Handle player disconnection."""
    sid = request.sid
    for game_code, game_data in games.items():
        if sid in game_data['players']:
            del game_data['players'][sid]
            leave_room(game_code)
            socketio.emit('player_left', {'player_id': sid}, room=game_code)
            break

# Run the Flask app
if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
