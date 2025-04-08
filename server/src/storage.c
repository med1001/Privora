#include "storage.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static sqlite3 *db = NULL;

// Fonction pour initialiser la base de données SQLite
void init_database() {
    if (sqlite3_open("chat.db", &db) != SQLITE_OK) {
        fprintf(stderr, "[ERROR] Impossible d'ouvrir la base de données: %s\n", sqlite3_errmsg(db));
        exit(EXIT_FAILURE);
    }

    const char *create_table_query =
        "CREATE TABLE IF NOT EXISTS offline_messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "recipient TEXT NOT NULL, "
        "message TEXT NOT NULL);";

    if (sqlite3_exec(db, create_table_query, NULL, NULL, NULL) != SQLITE_OK) {
        fprintf(stderr, "[ERROR] Erreur lors de la création de la table: %s\n", sqlite3_errmsg(db));
        exit(EXIT_FAILURE);
    }

    printf("[INFO] Base de données initialisée avec succès.\n");
}

// Fonction pour stocker un message hors ligne
void store_offline_message(const char *recipient, const char *message) {
    const char *insert_query = "INSERT INTO offline_messages (recipient, message) VALUES (?, ?);";
    sqlite3_stmt *stmt;

    if (sqlite3_prepare_v2(db, insert_query, -1, &stmt, NULL) != SQLITE_OK) {
        fprintf(stderr, "[ERROR] Erreur lors de la préparation de la requête: %s\n", sqlite3_errmsg(db));
        return;
    }

    sqlite3_bind_text(stmt, 1, recipient, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, message, -1, SQLITE_STATIC);

    if (sqlite3_step(stmt) != SQLITE_DONE) {
        fprintf(stderr, "[ERROR] Erreur lors de l'insertion du message: %s\n", sqlite3_errmsg(db));
    } else {
        printf("[INFO] Message hors ligne stocké pour %s.\n", recipient);
    }

    sqlite3_finalize(stmt);
}

// Fonction pour récupérer et envoyer les messages hors ligne d'un utilisateur
void deliver_offline_messages(const char *username, struct lws *wsi) {
    const char *select_query = "SELECT id, message FROM offline_messages WHERE recipient = ?;";
    sqlite3_stmt *stmt;

    if (sqlite3_prepare_v2(db, select_query, -1, &stmt, NULL) != SQLITE_OK) {
        fprintf(stderr, "[ERROR] Erreur lors de la récupération des messages: %s\n", sqlite3_errmsg(db));
        return;
    }

    sqlite3_bind_text(stmt, 1, username, -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        int id = sqlite3_column_int(stmt, 0);
        const char *message = (const char *)sqlite3_column_text(stmt, 1);

        // Envoi du message à l'utilisateur connecté
        unsigned char buf[LWS_PRE + 1024];
        int msg_len = snprintf((char *)(buf + LWS_PRE), 1024, "[Offline] %s", message);
        if (msg_len > 0) {
            lws_write(wsi, buf + LWS_PRE, msg_len, LWS_WRITE_TEXT);
        }

        // Supprimer le message après envoi
        char delete_query[256];
        snprintf(delete_query, sizeof(delete_query), "DELETE FROM offline_messages WHERE id = %d;", id);
        sqlite3_exec(db, delete_query, NULL, NULL, NULL);
    }

    sqlite3_finalize(stmt);
}
