import os
import yaml 
import logging
import threading
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime, timedelta
from server_interface import serverInterface

class MQTTInterface:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        module_dir = os.path.dirname(__file__)
        with open(os.path.join(module_dir,'../config/mqtt_params.yaml')) as yaml_file:
            try :
                config = yaml.safe_load(yaml_file)
            except yaml.YAMLError as exc:
                print(exc)

        self.broker_address = config['broker_address']
        self.port = config['port']
        self.sub_topic_payment = config['topic_payment']
        self.sub_topic_item = config['topic_item']
        self.username = config['username']
        self.password = config['password']
        self.magic_carpet_1_id = config['magic_carpet_1_id']
        self.magic_carpet_2_id = config['magic_carpet_2_id']
        self.sub_topic_payment_magic_carpet_1 = self.sub_topic_payment + "/" + self.magic_carpet_1_id
        self.sub_topic_payment_magic_carpet_2 = self.sub_topic_payment + "/" + self.magic_carpet_2_id
        self.sub_topic_item_magic_carpet_1 = self.sub_topic_item + "/" + self.magic_carpet_1_id
        self.sub_topic_item_magic_carpet_2 = self.sub_topic_item + "/" + self.magic_carpet_2_id
        print("MQTT Subscriber start with params :")
        print(f"broker_address : {self.broker_address}")
        print(f"port : {self.port}")
        print(f"topic_payment_1 : {self.sub_topic_payment_magic_carpet_1}")
        print(f"topic_payment_2 : {self.sub_topic_payment_magic_carpet_2}")
        print(f"topic_item_1 : {self.sub_topic_item_magic_carpet_1}")
        print(f"topic_item_2 : {self.sub_topic_item_magic_carpet_2}")
        print(f"username : {self.username}")
        print(f"password : {self.password}")
        self.client = mqtt.Client()
        
        # Assignation des callbacks
        self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.transactions_list_1 = []
        self.item_list_1 = []
        self.linked_list_1 = []

        self.transactions_list_2 = []
        self.item_list_2 = []
        self.linked_list_2 = []

        self.server_interface = serverInterface()

        self.main_loop_enable = False

        self.lock_item_1 = threading.Lock()
        self.lock_transaction_1 = threading.Lock()

        self.lock_item_2 = threading.Lock()
        self.lock_transaction_2 = threading.Lock()

    def on_connect(self, client, userdata, flags, rc):
        """Callback pour la connexion au broker."""
        print(f"Connecté au broker avec le code de retour {rc}")
        # Souscrire au topic avec QoS 1
        if rc == 0:
            client.subscribe(self.sub_topic_payment_magic_carpet_1)
            client.subscribe(self.sub_topic_item_magic_carpet_1)
            client.subscribe(self.sub_topic_payment_magic_carpet_2)
            client.subscribe(self.sub_topic_item_magic_carpet_2)
        else:
            self.logger.error(f"Échec de la connexion, code de résultat : {rc}")

    def on_message(self, client, userdata, msg):
        """Callback pour les messages reçus."""
        try : 
            payload = json.loads(msg.payload.decode('utf-8'))
            if msg.topic == self.sub_topic_item_magic_carpet_1 :
                items = {
                    'item_list': payload['item_list'],
                    'time_stamp': payload['time_stamp']
                }
                print(f"Items reçu: {items}")
                with self.lock_item_1:
                    self.item_list_1.append(items)
            elif msg.topic == self.sub_topic_item_magic_carpet_2 :
                items = {
                    'item_list': payload['item_list'],
                    'time_stamp': payload['time_stamp']
                }
                print(f"Items reçu: {items}")
                with self.lock_item_2:
                    self.item_list_2.append(items)
            elif msg.topic == self.sub_topic_payment_magic_carpet_1 :
                payment = {
                    'transactionId': payload['transactionId'],
                    'quantity': payload['count'],
                    'time_stamp': payload['createdAt']
                }
                payment['time_stamp'] = datetime.strptime(payment['time_stamp'], "%Y-%m-%d %H:%M:%S")
                payment['time_stamp'] = payment['time_stamp'] + timedelta(hours=2)
                payment['time_stamp'] = payment['time_stamp'].strftime("%Y-%m-%d %H:%M:%S")
                print(f"Paiement reçu: {payment}")
                with self.lock_transaction_1:
                    self.transactions_list_1.append(payment)
            elif msg.topic == self.sub_topic_payment_magic_carpet_2 :
                payment = {
                    'transactionId': payload['transactionId'],
                    'quantity': payload['count'],
                    'time_stamp': payload['createdAt']
                }
                payment['time_stamp'] = datetime.strptime(payment['time_stamp'], "%Y-%m-%d %H:%M:%S")
                payment['time_stamp'] = payment['time_stamp'] + timedelta(hours=2)
                payment['time_stamp'] = payment['time_stamp'].strftime("%Y-%m-%d %H:%M:%S")
                print(f"Paiement reçu: {payment}")
                with self.lock_transaction_2:
                    self.transactions_list_2.append(payment)
        except json.JSONDecodeError:
            print("Erreur lors du décodage du message JSON")

    def start(self):
        """Démarrer la boucle réseau MQTT dans un thread séparé."""
        self.client.connect(self.broker_address, self.port)
        thread = threading.Thread(target=self.client.loop_forever)
        thread.daemon = True  # Assurez-vous que le thread se termine avec le programme principal
        thread.start()
        self.main_loop_enable = True
        self.process_data()

    def stop(self):
        self.main_loop_enable
        time.sleep(1)
        """Arrêter la souscription MQTT."""
        self.client.disconnect()
        print("Déconnexion du client MQTT.")

    def process_data(self):
        while (self.main_loop_enable) :
            if len(self.transactions_list_1) != 0 and len(self.item_list_1) != 0 :
                # 1. On trie les liste par date de la plus ancienne à la plus récente
                with self.lock_item_1 and self.lock_transaction_1 :
                    self.item_list_1.sort(key=lambda item: datetime.strptime(item['time_stamp'], "%Y-%m-%d %H:%M:%S"))
                    self.transactions_list_1.sort(key=lambda item: datetime.strptime(item['time_stamp'], "%Y-%m-%d %H:%M:%S"))
                    # 2. On parcourt la transaction liste
                    for transaction_index in range(len(self.transactions_list_1)) :
                        #a. on parcourt l'item liste 
                        for item_index in range(len(self.item_list_1)):
                            #b. si la date de la transaction est anterieur à la date de lecture
                            if self.transactions_list_1[transaction_index]['time_stamp'] < self.item_list_1[item_index]['time_stamp'] :
                                #c. et si la quantitée acheté est égale à la quantité scannée
                                if self.transactions_list_1[transaction_index]['quantity'] == len(self.item_list_1[item_index]['item_list']) :
                                    print(f"transaction : {self.transactions_list_1[transaction_index]} will be associated with {self.item_list_1[item_index]}")
                                    linked = {
                                        'transaction' : self.transactions_list_1[transaction_index],
                                        'items' : self.item_list_1[item_index],
                                        'sending_done' : False
                                    }
                                    self.linked_list_1.append(linked)
                                    self.item_list_1.pop(item_index)
                                    break
                    print(f'linked list {self.linked_list_1}')
                    # 3. Pour chaque élément linké, on les POST sur le serveur 
                    for link in self.linked_list_1.copy() :
                        transaction_id = link['transaction']['transactionId']
                        items = link['items']['item_list']
                        data =  {
                            'id' : transaction_id,
                            'items' : items
                        }
                        print(f'data that will be send {data}')
                        return_value = self.server_interface.itemTransactionAssociation(data)
                        return_value = 1
                        if return_value == 1 :
                            link['sending_done'] = True
                            self.transactions_list_1.remove(link['transaction'])
                            self.linked_list_1.remove(link)
                        else :
                            pass

            if len(self.transactions_list_2) != 0 and len(self.item_list_2) != 0 :
                # 1. On trie les liste par date de la plus ancienne à la plus récente
                with self.lock_item_2 and self.lock_transaction_2 :
                    self.item_list_2.sort(key=lambda item: datetime.strptime(item['time_stamp'], "%Y-%m-%d %H:%M:%S"))
                    self.transactions_list_2.sort(key=lambda item: datetime.strptime(item['time_stamp'], "%Y-%m-%d %H:%M:%S"))
                    # 2. On parcourt la transaction liste
                    for transaction_index in range(len(self.transactions_list_2)) :
                        #a. on parcourt l'item liste 
                        for item_index in range(len(self.item_list_2)):
                            #b. si la date de la transaction est anterieur à la date de lecture
                            if self.transactions_list_2[transaction_index]['time_stamp'] < self.item_list_2[item_index]['time_stamp'] :
                                #c. et si la quantitée acheté est égale à la quantité scannée
                                if self.transactions_list_2[transaction_index]['quantity'] == len(self.item_list_2[item_index]['item_list']) :
                                    print(f"transaction : {self.transactions_list_2[transaction_index]} will be associated with {self.item_list_2[item_index]}")
                                    linked = {
                                        'transaction' : self.transactions_list_2[transaction_index],
                                        'items' : self.item_list_2[item_index],
                                        'sending_done' : False
                                    }
                                    self.linked_list_2.append(linked)
                                    self.item_list_2.pop(item_index)
                                    break
                    print(f'linked list {self.linked_list_2}')
                    # 3. Pour chaque élément linké, on les POST sur le serveur 
                    for link in self.linked_list_2.copy() :
                        transaction_id = link['transaction']['transactionId']
                        items = link['items']['item_list']
                        data =  {
                            'id' : transaction_id,
                            'items' : items
                        }
                        print(f'data that will be send {data}')
                        return_value = self.server_interface.itemTransactionAssociation(data)
                        return_value = 1
                        if return_value == 1 :
                            link['sending_done'] = True
                            self.transactions_list_2.remove(link['transaction'])
                            self.linked_list_2.remove(link)
                        else :
                            pass


            time.sleep(0.2)
        return


# Exécution du module principal pour tester
if __name__ == "__main__":
    mqtt_interface = MQTTInterface()
    mqtt_interface.start()

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Arrêt du script.")
        mqtt_interface.stop()
