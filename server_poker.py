import socket
from poker_data import *
import random
import itertools
from copy import deepcopy
import time

_SUITS = [1 << (i + 12) for i in range(4)]
_RANKS = [(1 << (i + 16)) | (i << 8) for i in range(13)]
_PRIMES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41]
_DECK = [_RANKS[rank] | _SUITS[suit] | _PRIMES[rank] for rank, suit in 
    itertools.product(range(13), range(4))]

global deck
SUITS = 'CDHS'
RANKS = '23456789TJQKA'
DECK = [''.join(s) for s in itertools.product(RANKS, SUITS)]
LOOKUP = dict(zip(DECK, _DECK))
deck=list(DECK)

port=12000
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(('',port))

#pre-game
def broadcast_players(players):
	#broadcasting player names
	temp_players = players.copy()
	for i in range(len(players)):
		reply='create_players,'
		for j in range(len(players)):
			reply=reply+temp_players[j][0]+','       #list of player_names
		server_socket.sendto(reply.encode(), players[i][1])
		temp_players = temp_players[1:] + temp_players[:1]  #rotating list so that each player will get their own name first

def give_cards(players_game):
	#giving players cards
	player_cards=[]
	random.shuffle(deck)
	x=0
	for i in range(len(players_game)):
		reply='give_cards,'
		player_cards.append(deck[x:x+2])
		reply+=player_cards[i][0]+','+player_cards[i][1]
		server_socket.sendto(reply.encode(), players_game[i][1])  #players_game because this list should not be rotated
		x+=2	
	return player_cards,x  #for future cards		

def players_turn(players_round,score_cards):
	#for i in range(len(players_round)):
	i=0
	while(i<len(players_round)):
		msg = 'turn,'+players_round[i][0]
		server_socket.sendto(msg.encode(), players_round[i][1])

		#reply
		reply, clientAddress = server_socket.recvfrom(2048)
		reply=reply.decode().split(',')
		if(reply[0]=='call'):
			for j in range(len(players)): #players because sent to everyone
				msg = 'other_call,'+reply[1]+','+reply[2]
				server_socket.sendto(msg.encode(), players[j][1])
		elif(reply[0]=='fold'):
			for j in range(len(players)):
				msg = 'other_fold,'+reply[1]
				server_socket.sendto(msg.encode(), players[j][1])
			for j in range(len(players_round)):
				if(reply[1] == players_round[j][0]):
					players_round.remove(players_round[j])
					score_cards.remove(score_cards[j])
					break
			if(len(players_round)==1):  #end of round
				return players_round,score_cards
			i-=1
		else:  #all-in
			pass
		i+=1
	return players_round,score_cards #modified by removing players who have folded

#adds cards to the table
def update_table(x,t,round_in_progress,table_cards):
	if(t==1): #theflop
		flop = deck[x:x+3]
		table_cards.extend(flop)
		flop = ','.join(flop)
		msg = 'theflop'+','+flop
		x+=3
	elif(t==2): #theturn
		turn = deck[x]
		table_cards.append(turn)
		msg = 'theturn'+','+turn
		x+=1
	elif(t==3): #theriver
		river = deck[x]
		table_cards.append(river)
		msg = 'theriver'+','+river	
		x+=1
	else:
		msg = 'randomstring'
	for i in range(len(players)):
		server_socket.sendto(msg.encode(), players[i][1])	
	if(t>3): #round_over
		round_in_progress=False
	return x,round_in_progress,table_cards

def winner(player,table):
    scores=[]
    hands=deepcopy(player)
    table1=deepcopy(table)
    for i in range(len(hands)):
        hands[i].extend(table1)
        score=eval7(hands[i])
        scores.append(score)
    return scores.index(min(scores)) #winning hand

def hash_function(x):
    x += 0xe91aaa35
    x ^= x >> 16
    x += x << 8
    x &= 0xffffffff
    x ^= x >> 4
    b = (x >> 8) & 0x1ff
    a = (x + (x << 2)) >> 19
    r = (a ^ HASH_ADJUST[b]) & 0x1fff
    return HASH_VALUES[r]

def eval5(hand):
    c1, c2, c3, c4, c5 = (LOOKUP[x] for x in hand)
    q = (c1 | c2 | c3 | c4 | c5) >> 16
    if (0xf000 & c1 & c2 & c3 & c4 & c5):
        return FLUSHES[q]
    s = UNIQUE_5[q]
    if s:
        return s
    p = (c1 & 0xff) * (c2 & 0xff) * (c3 & 0xff) * (c4 & 0xff) * (c5 & 0xff)
    return hash_function(p)

def eval7(hand):
    return min(eval5(x) for x in itertools.combinations(hand, 5))

#players joining room
global players
players = [] #list of tuples of the form - (playerName,clientAddress)
print("Waiting....")
while(len(players)!=5):
	msg, clientAddress = server_socket.recvfrom(2048)
	msg=msg.decode()
	msg=str(msg).split(',')
	if(msg[0]=='join'):
		players.append((msg[1],clientAddress))

'''
	players - initial list of people who connected
	players_game - players in the game, get game-specific information, reduced when people eliminated
	players_round - players in a round, reduced when people fold.

	Client messages
		join
		eliminated
		call
		fold
		not eliminated
'''
game_in_progress=True
players_game = players.copy() #players in the game
broadcast_players(players)
while(game_in_progress):
	player_cards, x = give_cards(players_game) 
	score_cards = player_cards.copy()   #variable which will be modified when people fold, used to decide winner
	table_cards = []
	round_in_progress=True
	t=1
	players_round = players_game.copy()   #active players in a round

	while(round_in_progress):
		players_round, score_cards = players_turn(players_round,score_cards)
		if(len(players_round) == 1):
			break
		x,round_in_progress,table_cards=update_table(x,t,round_in_progress,table_cards)  #displayed to all players
		t+=1

	for i in range(len(players)):
		card_str = ''
		for j in range(len(player_cards)):
			card_str+=','.join(player_cards[j]) + ','
		if(len(players_round) == 1):
			msg = 'round_over' + ',' + players_round[0][0] + ',' + card_str
		else:
			x = winner(score_cards,table_cards)
			msg = 'round_over' + ',' + players_round[x][0] + ',' + card_str
		server_socket.sendto(msg.encode(), players[i][1])
		player_cards = player_cards[1:] + player_cards[:1]   #rotating list

	i=0
	while(i<len(players_game)):
		msg, clientAddress = server_socket.recvfrom(2048)
		msg = msg.decode().split(',')
		print(msg)
		if(msg[0]=='eliminated'):
			reply = 'player_elim,' + msg[1]
			for x in range(len(players_game)):
				if(players_game[x][0] == msg[1]):
					break
			if(players_game[x][0] == msg[1]):
				players_game.remove(players_game[x])
			print(players_game)
			for j in range(len(players)):
				server_socket.sendto(reply.encode(), players[j][1])
			i-=1
		i+=1			


	if(len(players_game) == 1):
		game_in_progress = False
		msg = 'game_over,'+players_game[0][0]
		for i in range(len(players)):
			server_socket.sendto(msg.encode(), players[i][1])

	time.sleep(3)