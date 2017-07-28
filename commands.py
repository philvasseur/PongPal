""" Commands handled by the slack bot """
from datetime import datetime
from init import Message, BOT_ID
import os,logging,sqlite3,elo
from beautifultable import BeautifulTable
from elo import elo
from sets import Set

conn = sqlite3.connect('pingpong.db')
c = conn.cursor()
try:
	import picamera
	camera = picamera.PiCamera()
except ImportError:
	logging.warning(' Failing to import picamera. DO NOT USE STATUS COMMAND.')

#message object has: channel to repond to, text of the command, user who sent the command
def handleMatchInput(message):
	correctFormat = "match [myScore] [@opponent] [opponentScore]"
	commandArgs = message.text.split()
	if len(commandArgs) != 4:
		return "text", "Invalid input! Format the match command as follows:\n\t" + correctFormat + "\nType 'help' for more information."
	playerOneId = message.sender_id
	playerOneScore = commandArgs[1]
	playerTwoId = commandArgs[2]
	if (playerTwoId[:2] != '<@'):
		return "text", "Invalid command. Please tag your opponent using the '@' symbol."
	playerTwoId = playerTwoId.strip('<@>')
	playerTwoScore = commandArgs[3]

	if (playerOneId == playerTwoId):
		return "text", "You can't play against yourself, silly goose!"
	elif (playerTwoId == message.receiver_id):
		return "text", "You can't play against me! I might know a lot about pong, but I have no limbs."
	
	if (not playerOneScore.isdigit() or not playerTwoScore.isdigit()):
		return "text", "Invalid input! The scores must be numbers."
	else:
		playerOneScore = int(playerOneScore)
		playerTwoScore = int(playerTwoScore)
	if (playerOneScore == playerTwoScore):
		return "text", "KEEP PLAYING. No ties allowed."
	timeStamp = datetime.now()

	c.execute('SELECT name, ELO FROM players WHERE user_id=?;', [playerOneId])
	playerOneRow = c.fetchone()
	playerOneName = playerOneRow[0]
	playerOneElo = playerOneRow[1]

	if playerOneElo == None:
		playerOneRank = None
		playerOneElo = 1200
	else: 
		playerOneRank = calculatePlayerRank(playerOneName)

	c.execute('SELECT name, ELO FROM players WHERE user_id=?;', [playerTwoId])
	playerTwoRow = c.fetchone()
	if (playerTwoRow == None):
		return "text", "The opponent you entered isn't a valid player."
	playerTwoName = playerTwoRow[0]
	playerTwoElo = playerTwoRow[1]

	if (playerTwoElo == None):
		playerTwoElo = 1200
		playerTwoRank = None
	else:
		playerTwoRank = calculatePlayerRank(playerTwoName)

	c.execute('INSERT INTO matches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', [timeStamp, playerOneName, playerOneScore, playerOneRank, playerOneElo, playerTwoName, playerTwoScore, playerTwoRank, playerTwoElo])
	newEloOne, newEloTwo = elo(playerOneElo, playerTwoElo, playerOneScore, playerTwoScore)
	c.execute('UPDATE players SET ELO=? WHERE user_id=?;', [newEloOne, playerOneId])
	c.execute('UPDATE players SET ELO=? WHERE user_id=?;', [newEloTwo, playerTwoId])
	conn.commit()

	if (playerTwoScore > playerOneScore):
		winnerName = playerTwoName
		winnerScore = playerTwoScore
		loserScore = playerOneScore
	else:
		winnerName = playerOneName
		winnerScore = playerOneScore
		loserScore = playerTwoScore

	return "text", "<@" + winnerName + ">" + " won! The score was *" + str(winnerScore) + "-" + str(loserScore) + "*. Your score has been recorded for posterity."

def calculatePlayerRank(playerName):
	c.execute('SELECT COUNT(name) FROM players WHERE ELO > (SELECT ELO FROM players where name = ?);', [playerName])
	rank = c.fetchone()[0] 
	return rank + 1

def calculatePlayerRankInGroup(playerName, groupName):
	members = getGroupMembers(groupName)
	question_marks = ','.join(['?'] * len(members))
	c.execute('SELECT COUNT(name) FROM players WHERE ELO > (SELECT ELO FROM players where name = ?) AND name IN ('+question_marks+');', [playerName] + members)
	rank = c.fetchone()[0] 
	return rank + 1

def getGroupMembers(groupName):
	c.execute('SELECT username FROM groups WHERE groupname=?', [groupName])
	rows = c.fetchall()
	memberlist = []
	for row in rows:
		memberlist.append(row[0])
	return memberlist

def sendHelpOptions(message):
	helpInfo = "Commands:\n*_help_* - Lists these commands here :table_tennis_paddle_and_ball:\n"
	statusInfo = "*_status_* - Sends you a picture of the current status of the ping-pong room\n"
	matchInfo = "*_match_* - Records your match and updates your overall ranking\n\t`match [myScore] [@opponent] [opponentScore]`\n\t_Example usage_: match 21 @pongpal 5\n"
	historyInfo = "*_history_* - Lists your match history, defaults to a list of 10. Takes an optional limit parameter as an integer or 'all'\n\t`history [limit?]`\n"
	statsInfo = "*_stats_* - Shows a player's stats, defaults to your stats. Can show a player's stats within a group, defaults to the entire company. Takes an optional player username parameter and an optional group parameter. \n\t`stats [@player?] [group?]`\n\t_Example usage_: stats @keyvan customer-ops\n"
	newgroupInfo = "*_newgroup_* - Create a new group, which will allow you to view match history, stats, and rankings within the context of your group. Must add at least one group member\n\t`newgroup [groupname] [@member1] [@member2?] [@member3?] ...`\n\t _Example usage_: newgroup pongpalz @pongpal @katya @phil @stephen @christian @jacob\n"
	addmembersInfo = "*_addmembers_* - Add members to an existing group\n\t`addmembers [groupname] [@member1] [@member2?] [@member3?] ...`\n"
	viewmembersInfo = "*_viewmembers_* - View the members of a group\n\t`viewmembers [groupname]`"
	return 'text', helpInfo + statusInfo + matchInfo + historyInfo + statsInfo + newgroupInfo + addmembersInfo + viewmembersInfo

def sendRoomStatus(message):
	camera.capture('status.jpg')
	f = open('status.jpg','rb')
	return "file", {"comment":"Current status of the ping pong room:","filename":"Room Status","file":f}

def getMatchHistory(message):
	limit = 10
	textArray = message.text.split()
	c.execute("SELECT * FROM players WHERE user_id=?",(message.sender_id,))
	username = c.fetchone()[1]
	if len(textArray) > 2:
		return "text", "Invalid format. Format the history command as follows:\n\t`history [limit?]`\nType 'help' for more information."
	elif len(textArray) == 2:
		try:
			limit = int(textArray[1])
			if limit < 1:
				return "text", "'" + textArray[1] + "' is not a valid limit. Format the history command as follows:\n\t`history [limit?]`\nType 'help' for more information."
		except ValueError:
			if(textArray[1] == 'all'):
				limit = -1
			else:
				return "text", "'" + textArray[1] + "' is not a valid limit. Format the history command as follows:\n\t`history [limit?]`\nType 'help' for more information."
	c.execute("SELECT * FROM matches WHERE playerOne=? OR playerTwo=? ORDER BY date DESC LIMIT ?",(username,username,limit))
	results = c.fetchall()
	if results == []:
		return "text","Sorry, you have no previous matches!"
	table = BeautifulTable()
	table.column_headers = ["Date", "Match", "Score", "Winner"]
	wins = 0
	for result in results:
		winner = result[1] if int(result[2]) > int(result[6]) else result[5]
		table.append_row([datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S.%f').strftime('%Y-%m-%d'),result[1] + " vs " + result[5], str(result[2]) + " - " + str(result[6]), winner])
		if winner == username:
			wins +=1
	title = str(int(float(wins)/float(len(results)) * 100)) + "% Win-Rate Over " + str(len(results)) + " Games\n"
	return "text", title+"```"+str(table)+"```"

def getPlayerStats(message):
	commandArgs = message.text.split()
	groupId = None
	if len(commandArgs) > 3:
		return "text", "Invalid format.\n Type 'help' for more information."
	elif len(commandArgs) == 3:
		playerId = commandArgs[1]
		if (not isValidUserName(playerId)):
			return "text", "Invalid command. Please tag a player using the '@' symbol.\nType 'help' for more information."
		playerId = playerId.strip('<@>')
		print(playerId)
		c.execute("SELECT name,ELO FROM players WHERE user_id=?",(playerId,))
		playerInfo = c.fetchone()
		print(playerInfo)
		groupId = commandArgs[2]
		c.execute('SELECT groupname FROM groups WHERE groupname=?', (groupId,))
		result = c.fetchone()
		if (result == None):
			return "text", "The group you entered doesn't exist!"
	elif len(commandArgs) == 2:
		optionalArg = commandArgs[1]
		if (not isValidUserName(optionalArg)):
			c.execute('SELECT groupname FROM groups WHERE groupname=?', (optionalArg,))
			result = c.fetchone()
			if (result == None):
				return "text", "The optional argument you entered is neither a valid user nor a valid group.\nType 'help' for more information."
			else:
				groupId = optionalArg
				c.execute("SELECT name,ELO FROM players WHERE user_id=?",(message.sender_id,))
				playerInfo = c.fetchone()
		else:
			playerId = optionalArg.strip('<@>')
			c.execute("SELECT name,ELO FROM players WHERE user_id=?",(playerId,))
			playerInfo = c.fetchone()
			if playerInfo == None:
				return "text", "The opponent you entered isn't a valid player."			
	else:
		c.execute("SELECT name,ELO FROM players WHERE user_id=?",(message.sender_id,))
		playerInfo = c.fetchone()

	username = playerInfo[0]
	ELO = playerInfo[1]
	if groupId:
		rank = calculatePlayerRankInGroup(username, groupId)
		groupmembers = getGroupMembers(groupId)
		question_marks = ','.join(['?'] * len(groupmembers))
		c.execute('SELECT playerOne,scoreOne,playerTwo,scoreTwo FROM matches WHERE playerOne=? AND playerTWO IN ('+ question_marks +') OR playerTwo=? AND playerOne IN (' + question_marks + ')',[username] + groupmembers + [username] + groupmembers)
	else:
		rank = calculatePlayerRank(username)
		c.execute("SELECT playerOne,scoreOne,playerTwo,scoreTwo FROM matches WHERE playerOne=? OR playerTwo=?",(username,username))
	results = c.fetchall()
	wins, losses, ptDiff = calcStats(results, username)
	table = BeautifulTable()
	table.column_headers = ["ELO","Rank","Wins","Losses","Win-Rate","Point Diff", "Avg. Point Diff"]
	table.append_row([ELO,rank,wins,losses,float(wins)/float(wins+losses),ptDiff,float(ptDiff)/float(wins+losses)])
	messageHeader = "Stats for <@" + username + ">"
	if groupId:
		messageHeader = messageHeader + " in group *" + groupId + "*"
	return "text", messageHeader + "\n```"+str(table)+"```"

def calcStats(results, username):
	if results == []:
		return "text", "Sorry, you have no previous matches!"
	wins = 0
	losses = 0
	ptDiff = 0
	for result in results:
		playerOne = result[0]
		scoreOne = result[1]
		playerTwo = result[2]
		scoreTwo = result[3]
		winner = playerOne if scoreOne > scoreTwo else playerTwo
		if(winner == username):
			wins+=1
		else:
			losses+=1

		if(playerOne == username):
			ptDiff += scoreOne - scoreTwo
		else:
			ptDiff += scoreTwo - scoreOne
	return wins, losses, ptDiff


def isValidUserName(str):
	if (str[:2] != '<@'):
		return False
	return True

"""must add at least one player when you add a new group """
def createGroup(message):
	commandArgs = message.text.split()
	if len(commandArgs) < 3:
		return "text", "Invalid format. Type 'help' for more information."
	groupName = commandArgs[1]
	c.execute("SELECT groupname FROM groups WHERE groupname=?", [groupName])
	results = c.fetchone()
	if (results != None):
		return "text", "Sorry, a group with this name already exists!"
	memberlist = getMembersFromCommand(commandArgs[2:])
	for m in memberlist:
		print(m + " " + groupName)
		c.execute("INSERT INTO groups VALUES (?, ?)", [m, groupname])
		conn.commit()
	return "text", "Congrats, you have created a new group called " + groupName + "!"

def getMembersFromCommand(inputtedMembers):
	memberlist = []
	i = 0
	while i < len(inputtedMembers):
		m = inputtedMembers[i]
		if (not isValidUserName(m)):
			return "text", m + " is not a valid user."
		c.execute("SELECT name FROM players WHERE user_id=?", [m.strip('<@>')])
		membername = c.fetchone()[0]
		memberlist.append(membername)
		i += 1
	return memberlist

def viewGroupMembers(message):
	commandArgs = message.text.split()
	if(len(commandArgs) != 2):
		return "text", "Invalid format. Type 'help' for more information."
	groupname = commandArgs[1]
	c.execute("SELECT username FROM groups WHERE groupname=?", [groupname])
	members = c.fetchall()
	resultText = "Here are the members of group " + groupname + ":\n"
	for row in members:
		resultText = resultText + str(row[0]) + "\n"
	return "text", resultText

def addMembersToGroup(message):
	commandArgs = message.text.split()
	if len(commandArgs) < 3:
		return "text", "Invalid format. Type 'help' for more information."
	groupName = commandArgs[1]
	c.execute("SELECT groupname FROM groups WHERE groupname=?", [groupName])
	results = c.fetchone()
	if (results == None):
		return "text", "This group doesn't exist!"
	memberlist = getMembersFromCommand(commandArgs[2:])
	for m in memberlist:
		c.execute("SELECT groupname FROM groups WHERE username=?", [groupName])
		groups = c.fetchall()
		alreadyInGroup = False
		for g in groups:
			if g[0] == groupName:
				alreadyInGroup = True
				print("don't add duplicate")
		if (not alreadyInGroup):
			c.execute("INSERT INTO groups VALUES (?, ?)", [m, groupName])
			conn.commit()
	return "text", "Members succesfully added to group " + groupName + "!"
