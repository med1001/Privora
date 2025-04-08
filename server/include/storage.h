#ifndef STORAGE_H
#define STORAGE_H

#include <libwebsockets.h>
#include <sqlite3.h>

// Fonction pour initialiser la base de données
void init_database();

// Fonction pour stocker un message hors ligne
void store_offline_message(const char *recipient, const char *message);

// Fonction pour récupérer les messages hors ligne d'un utilisateur et les supprimer après envoi
void deliver_offline_messages(const char *username, struct lws *wsi);

#endif
