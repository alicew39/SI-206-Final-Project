# Your name: Alice Wou
# Your student id: 10428403
# Your email: awou@umich.edu
# List who you worked with on this homework: Somin An

from bs4 import BeautifulSoup
import requests
import re
import os
import csv
import unittest
import sqlite3
import json
import plotly.graph_objects as go
import time

# API key needs to be regenerated every 24 hours. Go to https://developer.riotgames.com/ and create an account to get a free developer api key.
API_KEY = 'RGAPI-678dee60-b6f7-4e3d-ae6c-ce2ad8ea380c'
# File to write calculation results
OUTPUT_FNAME = 'results.txt'
# Cache file. Used to keep API requests limited
CACHE_FNAME = 'cache_player_levels.json'
try:
    cache_file = open(CACHE_FNAME, 'r')
    cache_contents = cache_file.read()
    CACHE_DICT = json.loads(cache_contents)
    cache_file.close()
except:
    CACHE_DICT = {}

def setUpDatabase(name):
    path = os.path.dirname(os.path.abspath(__file__))
    conn = sqlite3.connect(path+'/'+name)
    cur = conn.cursor()
    return cur, conn

def get_champion_info():
    """
        Write a function that creates a BeautifulSoup object after retrieving content from 
        "https://na.op.gg/statistics/champion/". Parse through the object and return a dictionary of the base HP
        and base AD of all champions in alphabetical order. 

        [ Aatrox: [580, 60], Ahri: [526, 53.04], ... ]
    """

    url = "https://leagueoflegends.fandom.com/wiki/List_of_champions/Base_statistics"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'html.parser')

    champ_table = soup.find('table')
    info = champ_table.find('tbody')
    td = info.find_all('td')
    champ_dict = {}
    att_list = []

    for x in td:
        att_list.append(x.text)

    count = 0
    while count < len(att_list):
        name = att_list[count].strip()
        count += 1
        hp = att_list[count]
        count += 8
        ad = att_list[count]
        count += 10

        stats  = []
        stats.append(hp)
        stats.append(ad)

        champ_dict[name] = stats

    return champ_dict

def setUpChampionBaseStats(data, cur, conn):
    cur.execute("DROP TABLE IF EXISTS BaseStats")
    cur.execute("CREATE TABLE BaseStats (name TEXT PRIMARY KEY, health REAL, damage REAL)")

    for champ in data:
        cur.execute("INSERT INTO BaseStats (name, health, damage) VALUES (?,?,?)", (champ, data[champ][0], data[champ][1]))

    conn.commit()

def calculateAverageHealth(cur, conn):
    cur.execute("SELECT BaseStats.health FROM BaseStats")
    health_list = cur.fetchall()

    total_health = 0
    count = 0
    for health in health_list:
        total_health += health[0]
        count += 1

    avgHealth = round(total_health / count, 2)

    return avgHealth

def calculateAverageDamage(cur, conn):
    cur.execute("SELECT BaseStats.damage FROM BaseStats")
    damage_list = cur.fetchall()

    total_damage = 0
    count = 0
    for damage in damage_list:
        total_damage += damage[0]
        count += 1

    avgDamage = round(total_damage / count, 2)

    return avgDamage

def get_challenger_players():
    url = 'https://na1.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/RANKED_SOLO_5x5?api_key=' + API_KEY
    data = requests.get(url)

    response_body = json.loads(data.text)
    
    player_list = response_body['entries']

    player_dict = {}
    for player in player_list:
        info_list = []
        info_list.append(player['leaguePoints'])
        info_list.append(player['wins'])
        info_list.append(player['losses'])
        info_list.append(player['summonerId'])

        player_dict[player['summonerName'].strip()] = info_list

    return player_dict

def setUpChallengerPlayers(data, cur, conn):
    cur.execute("DROP TABLE IF EXISTS ChallengerStats")
    cur.execute("CREATE TABLE ChallengerStats (name TEXT UNIQUE, points INTEGER, wins INTEGER, losses INTEGER, id TEXT PRIMARY KEY)")

    for player in data:
        cur.execute("INSERT INTO ChallengerStats (name, points, wins, losses, id) VALUES (?,?,?,?,?)", (player, data[player][0], data[player][1], data[player][2], data[player][3]))

    conn.commit()

def get_challenger_levels(cur, conn):
    cur.execute("SELECT ChallengerStats.id FROM ChallengerStats")
    player_list = cur.fetchall()

    player_dict = {}
    for player in player_list:
        if player[0] in CACHE_DICT:
            player_dict[player[0]] = CACHE_DICT[player[0]]
        else:
            url = 'https://na1.api.riotgames.com/lol/summoner/v4/summoners/' + player[0] +'?api_key=' + API_KEY
            data = requests.get(url)
            try:
                response_body = json.loads(data.text)
                CACHE_DICT[player[0]] = response_body['summonerLevel']
                json_cache = json.dumps(CACHE_DICT)
                filewrite = open(CACHE_FNAME, 'w')
                filewrite.write(json_cache)
                filewrite.close()
                player_dict[player[0]] = response_body['summonerLevel']
            except:
                player_dict[player[0]] = 1
            time.sleep(.1)

    return player_dict

def setUpPlayerLevels(data, cur, conn):
    cur.execute("SELECT id FROM PlayerLevels")
    check = cur.fetchall()
    if len(check) >= 300:
        answer = input("Would you like to restart your database? y/n :")
        if answer == 'y':
            cur.execute("DROP TABLE IF EXISTS PlayerLevels")
    
    cur.execute("CREATE TABLE IF NOT EXISTS PlayerLevels (id TEXT PRIMARY KEY, level INTEGER)")

    count = 0
    for level in data:
        cur.execute("SELECT id FROM PlayerLevels")
        id_tuple = cur.fetchall()

        id_list = []
        for i in id_tuple:
            id_list.append(i[0])

        if level in id_list:
            continue

        cur.execute("INSERT OR IGNORE INTO PlayerLevels (id, level) VALUES (?,?)", (level, data[level]))

        cur.execute("SELECT COUNT(*) FROM PlayerLevels")
        count = cur.fetchone()[0]
        conn.commit()

        if count == 25 or count == 50 or count == 75 or count == 100:
            cur.execute("SELECT id FROM PlayerLevels")
            total = cur.fetchall()
            print("PlayerLevels contains " + str(len(total)) + " items total. Breaking.")
            return 0
            
    return 1

def calculateAverageLevelAbovePoints(points, cur, conn):
    cur.execute("SELECT PlayerLevels.level FROM PlayerLevels JOIN ChallengerStats ON PlayerLevels.id=ChallengerStats.id WHERE ChallengerStats.points>=" + str(points))
    levels_list = cur.fetchall()

    if len(levels_list) == 0:
        print("No one has a higher number of lp than " + points + ". Please enter a lower number next time. (e.g. 1000)")
        return None

    total_level = 0
    count = 0
    for level in levels_list:
        total_level += level[0]
        count += 1
    
    avgLevel = round(total_level / count, 2)

    return avgLevel

def calculateAverageWinRatioAbovePoints(points, cur, conn):
    cur.execute("SELECT wins, losses FROM ChallengerStats WHERE points>=" + str(points))
    stats_list = cur.fetchall()

    if len(stats_list) == 0:
        return None

    total_winrate = 0
    count = 0
    for stats in stats_list:
        total_games = stats[0] + stats[1]
        winrate = (stats[0] / total_games) * 100
        total_winrate += winrate
        count += 1

    avgWinrate = round(total_winrate / count, 2)

    return avgWinrate

def writeToFile(health, damage, level, winrate, points):
    fh = open(OUTPUT_FNAME, 'w')
    fh.write('The average health for all champions in League of Legends is ' + str(health) + '\n')
    fh.write('The average attack damage for all champions in League of Legends is ' + str(damage) + '\n')
    fh.write('The average level for Challenger players in League of Legends above ' + points + ' points is ' + str(level) + '\n')
    fh.write('The average winrate for Challenger players in League of Legends above ' + points + ' points is ' + str(winrate) + '%' + '\n')
    fh.close()

def websiteVisualization(cur, conn):
    cur.execute("SELECT health FROM BaseStats")
    health_tuples = cur.fetchall()
    cur.execute("SELECT name FROM BaseStats")
    name_tuples = cur.fetchall()

    health_list = []
    for health in health_tuples:
        health_list.append(health[0])
    
    name_list = []
    for name in name_tuples:
        name_list.append(name[0])

    #barGraph = go.FigureWidget(data=go.Bar(y=[2, 3, 1]))
    avgHealth = []
    avgHealth.append(round(calculateAverageHealth(cur, conn)))
    average = ["Average"]
    barGraph = go.Figure(data = [
        go.Bar(name = "Health", x = name_list, y = health_list, marker_color = 'rgb(147, 112, 219)'),
        go.Bar(name = "Average Health", x = average, y = avgHealth, marker_color = 'rgb(225, 0, 225)')])

    title1 = "Base Health (HP) of Champions"
    barGraph.update_layout(title = title1, xaxis_tickangle = -45)
    path = os.path.dirname(os.path.abspath(__file__))
    barGraph.write_image(os.path.join(path, 'avgHealth.png'))
    barGraph.show()

def apiVisualization(cur, conn):
    cur.execute("SELECT PlayerLevels.level FROM PlayerLevels JOIN ChallengerStats ON PlayerLevels.id=ChallengerStats.id LIMIT 100")
    level_tuples = cur.fetchall()

    cur.execute("SELECT name FROM ChallengerStats LIMIT 100")
    name_tuples = cur.fetchall()

    level_list = []
    for level in level_tuples:
        level_list.append(level[0])
    
    name_list = []
    for name in name_tuples:
        name_list.append(name[0])
    
    avgLevel = []
    total_level = 0
    count = 0
    for level in level_list:
        total_level += level
        count += 1
    
    avg = round(total_level / count, 2)
    avgLevel.append(avg)

    average = ["Average"]
    graph = go.Figure(data = [
        go.Bar(name = "Level", x = name_list, y = level_list, marker_color = 'rgb(225, 225, 0)'),
        go.Bar(name = "Average Level", x = average, y = avgLevel, marker_color = 'rgb(100, 100, 100)')
    ])

    title1 = "Account Level of Top 100 Challenger Players"
    graph.update_layout(title = title1, xaxis_tickangle = -45)
    path = os.path.dirname(os.path.abspath(__file__))
    graph.write_image(os.path.join(path, 'avgLevel.png'))
    graph.show()
    

    

if __name__ == '__main__':
    cur, conn = setUpDatabase('league_database.db')

    base_stats = get_champion_info()
    setUpChampionBaseStats(base_stats, cur, conn)

    challenger_players = get_challenger_players()
    setUpChallengerPlayers(challenger_players, cur, conn)

    player_levels = get_challenger_levels(cur, conn)
    stopOrGO = setUpPlayerLevels(player_levels, cur, conn)

    if stopOrGO == 1:
        print("Finished adding items to database.")
        minimumPoints = input("Enter minimum Challenger LP for average calculations (e.g. 1000): ")
        writeToFile(calculateAverageHealth(cur, conn), calculateAverageDamage(cur, conn), calculateAverageLevelAbovePoints(minimumPoints, cur, conn), calculateAverageWinRatioAbovePoints(minimumPoints ,cur, conn), minimumPoints)
        print("Check results.txt for your calculations!")
        websiteVisualization(cur, conn)
        apiVisualization(cur, conn)
    else:
        print("Run code again to add 25 more items to database.")

    

