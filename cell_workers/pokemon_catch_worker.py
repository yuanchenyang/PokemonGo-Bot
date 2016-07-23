import time
from sets import Set
from pgoapi.utilities import f2i, h2f, distance
from itertools import groupby

class PokemonCatchWorker(object):

    def __init__(self, pokemon, bot):
        self.pokemon = pokemon
        self.api = bot.api
        self.position = bot.position
        self.config = bot.config
        self.pokemon_list = bot.pokemon_list
        self.item_list = bot.item_list
        self.inventory = bot.inventory
        self.ballstock = bot.ballstock
        self.noballs = bot.noballs

    def pokemon_name_from_id(self, pokemon_id):
        pokemon_num=int(pokemon_id)-1
        return self.pokemon_list[int(pokemon_num)]['Name']

    def work(self):
        encounter_id = self.pokemon['encounter_id']
        spawnpoint_id = self.pokemon['spawnpoint_id']
        player_latitude = self.pokemon['latitude']
        player_longitude = self.pokemon['longitude']

        dist = distance(self.position[0], self.position[1], player_latitude, player_longitude)

        print('[x] Found pokemon at distance {}m'.format(dist))
        if dist > 10:
            position = (player_latitude, player_longitude, 0.0)
            if self.config.walk > 0:
                self.api.walk(self.config.walk, *position,walking_hook=None)
                print('[x] Walked to Pokemon')
            else:
                self.api.set_position(*position)
                print('[x] Teleported to Pokemon')
            self.api.player_update(latitude=player_latitude,longitude=player_longitude)
            response_dict = self.api.call()
            time.sleep(1.2)

        self.api.encounter(encounter_id=encounter_id,spawnpoint_id=spawnpoint_id,player_latitude=player_latitude,player_longitude=player_longitude)
        response_dict = self.api.call()

        if response_dict and 'responses' in response_dict:
            if 'ENCOUNTER' in response_dict['responses']:
                if 'status' in response_dict['responses']['ENCOUNTER']:
                    if response_dict['responses']['ENCOUNTER']['status'] is 1:
                        cp=0
                        if 'wild_pokemon' in response_dict['responses']['ENCOUNTER']:
                            pokemon=response_dict['responses']['ENCOUNTER']['wild_pokemon']
                            if 'pokemon_data' in pokemon and 'cp' in pokemon['pokemon_data']:
                                cp=pokemon['pokemon_data']['cp']
                                pokemon_name=self.pokemon_name_from_id(pokemon['pokemon_data']['pokemon_id'])
                                print('[#] A Wild ' + str(pokemon_name) + ' appeared! [CP' + str(cp) + ']')
                        while(True):
                            id_list1 = self.count_pokemon_inventory()

                            if self.ballstock[1] > 0:
                                #DEBUG - Hide
                                #print 'use Poke Ball'
                                pokeball = 1
                            else:
                                #DEBUG - Hide
                                #print 'no Poke Ball'
                                pokeball = 0

                            if cp > 200 and self.ballstock[2] > 0:
                                #DEBUG - Hide
                                #print 'use Great Ball'
                                pokeball = 2

                            if cp > 400 and self.ballstock[3] > 0:
                                #DEBUG - Hide
                                #print 'use Utra Ball'
                                pokeball = 3

                            if pokeball is 0:
                                print('[x] Out of pokeballs...')
                                # TODO: Begin searching for pokestops.
                                print('[x] Farming pokeballs...')
                                self.noballs = True
                                break

                            print('[x] Using ' + self.item_list[str(pokeball)] + '...')
                            self.api.catch_pokemon(encounter_id = encounter_id,
                                pokeball = pokeball,
                                normalized_reticle_size = 1.950,
                                spawn_point_guid = spawnpoint_id,
                                hit_pokemon = 1,
                                spin_modifier = 1,
                                NormalizedHitPosition = 1)
                            response_dict = self.api.call()

                            #DEBUG - Hide
                            #print ('used ' + self.item_list[str(pokeball)] + '> [-1]')
                            self.ballstock[pokeball] -= 1

                            if response_dict and \
                                'responses' in response_dict and \
                                'CATCH_POKEMON' in response_dict['responses'] and \
                                'status' in response_dict['responses']['CATCH_POKEMON']:
                                status = response_dict['responses']['CATCH_POKEMON']['status']
                                if status is 2:
                                    print('[-] Attempted to capture ' + str(pokemon_name) + ' - failed.. trying again!')
                                    time.sleep(1.25)
                                    continue
                                if status is 3:
                                    print('[x] Oh no! ' + str(pokemon_name) + ' vanished! :(')
                                if status is 1:
                                    print('[x] Captured {}! [CP {}]'.format(pokemon_name, cp))

                                    if self.config.pokelimit is not None:
                                        self.transfer_all_but_k(self.config.pokelimit)

                                    if cp < self.config.cp:
                                        id_list2 = self.count_pokemon_inventory()
                                        try:
                                            # Transfering Pokemon
                                            self.transfer_pokemon(list(Set(id_list2) - Set(id_list1))[0])
                                        except:
                                            print('[###] Your inventory is full! Please manually delete some items.')
                                            break
                            break
        time.sleep(5)

    def _transfer_low_cp_pokemon(self, value):
    	self.api.get_inventory()
    	response_dict = self.api.call()
    	self._transfer_all_low_cp_pokemon(value, response_dict)

    def _transfer_all_low_cp_pokemon(self, value, response_dict):
    	if 'responses' in response_dict:
    		if 'GET_INVENTORY' in response_dict['responses']:
    			if 'inventory_delta' in response_dict['responses']['GET_INVENTORY']:
    				if 'inventory_items' in response_dict['responses']['GET_INVENTORY']['inventory_delta']:
    					for item in response_dict['responses']['GET_INVENTORY']['inventory_delta']['inventory_items']:
    						if 'inventory_item_data' in item:
    							if 'pokemon' in item['inventory_item_data']:
    								pokemon = item['inventory_item_data']['pokemon']
    								self._execute_pokemon_transfer(value, pokemon)
    								time.sleep(1.2)

    def _execute_pokemon_transfer(self, value, pokemon):
    	if 'cp' in pokemon and pokemon['cp'] < value:
    		self.api.release_pokemon(pokemon_id=pokemon['id'])
    		response_dict = self.api.call()
    		print('[x] Exchanged successfully!')

    def transfer_pokemon(self, pid):
        pokemon_name = self.pokemon_name_from_id(pid)
        print('[x] Exchanging {} for candy'.format(pokemon_name))
        self.api.release_pokemon(pokemon_id=pid)
        response_dict = self.api.call()
        time.sleep(2)
        print('[x] Exchanged successfully!')

    def count_pokemon_inventory(self):
        self.api.get_inventory()
        response_dict = self.api.call()
        return self.counting_pokemon(response_dict)

    def counting_pokemon(self, response_dict):
        id_list = []
        if 'responses' in response_dict:
            if 'GET_INVENTORY' in response_dict['responses']:
                if 'inventory_delta' in response_dict['responses']['GET_INVENTORY']:
                    if 'inventory_items' in response_dict['responses']['GET_INVENTORY']['inventory_delta']:
                        for item in response_dict['responses']['GET_INVENTORY']['inventory_delta']['inventory_items']:
                            if 'inventory_item_data' in item:
                                if 'pokemon' in item['inventory_item_data']:
                                    pokemon = item['inventory_item_data']['pokemon']
                                    id_list.append(pokemon['id'])
        return id_list

    def get_pokemons(self):
        self.api.get_inventory()
        res = self.api.call()
        try:
            pokemons = [item['inventory_item_data']['pokemon']
                for item in res['responses']['GET_INVENTORY']['inventory_delta']['inventory_items']
                if 'pokemon'    in item['inventory_item_data'] and
                   'is_egg' not in item['inventory_item_data']['pokemon']]
            return pokemons
        except KeyError:
            print 'Error getting pokemon list'
            return []

    def transfer_all_but_k(self, k):
        pokemons = self.get_pokemons()
        to_transfer = []

        for pid, group in groupby(pokemons, lambda x: x['pokemon_id']):
            g = list(group)
            if len(g) > k:
                for obj in sorted(g, key=lambda x: x['cp'], reverse=True)[:k]:
                    to_transfer.append(obj['id'])

        for pid in to_transfer:
            self.transfer_pokemon(pid)
