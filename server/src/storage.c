#include "storage.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

sqlite3 *db = NULL;

void init_database() {
    if (sqlite3_open("chat.db", &db) != SQLITE_OK) {
        fprintf(stderr, "[ERROR] Impossible d'ouvrir la base de données: %s\n", sqlite3_errmsg(db));
        exit(EXIT_FAILURE);
    }

    const char *offline_query =
        "CREATE TABLE IF NOT EXISTS offline_messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "recipient TEXT NOT NULL, "
        "message TEXT NOT NULL);";

    const char *history_query =
        "CREATE TABLE IF NOT EXISTS message_history ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "sender TEXT NOT NULL, "
        "recipient TEXT NOT NULL, "
        "message TEXT NOT NULL, "
        "timestamp DATETIME DEFAULT CURRENT_TIMESTAMP);";

    if (sqlite3_exec(db, offline_query, NULL, NULL, NULL) != SQLITE_OK ||
        sqlite3_exec(db, history_query, NULL, NULL, NULL) != SQLITE_OK) {
        fprintf(stderr, "[ERROR] Erreur lors de la création des tables: %s\n", sqlite3_errmsg(db));
        exit(EXIT_FAILURE);
    }

    printf("[INFO] Base de données initialisée avec succès.\n");
}

void store_offline_message(const char *recipient, const char *message) {
    const char *insert_query = "INSERT INTO offline_messages (recipient, message) VALUES (?, ?);";
    sqlite3_stmt *stmt;

    if (sqlite3_prepare_v2(db, insert_query, -1, &stmt, NULL) != SQLITE_OK) {
        fprintf(stderr, "[ERROR] Erreur préparation requête: %s\n", sqlite3_errmsg(db));
        return;
    }

    sqlite3_bind_text(stmt, 1, recipient, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, message, -1, SQLITE_STATIC);

    if (sqlite3_step(stmt) != SQLITE_DONE) {
        fprintf(stderr, "[ERROR] Insertion message échouée: %s\n", sqlite3_errmsg(db));
    } else {
        printf("[INFO] Message hors ligne stocké pour %s.\n", recipient);
    }

    sqlite3_finalize(stmt);
}

// Fetch offline messages from the database
int fetch_offline_messages(const char *username, char messages[10][512], int max_messages) {
    const char *select_query = "SELECT message FROM offline_messages WHERE recipient = ?;";
    sqlite3_stmt *stmt;
    int message_count = 0;

    if (sqlite3_prepare_v2(db, select_query, -1, &stmt, NULL) != SQLITE_OK) {
        fprintf(stderr, "[ERROR] Récupération messages échouée: %s\n", sqlite3_errmsg(db));
        return 0;
    }

    sqlite3_bind_text(stmt, 1, username, -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW && message_count < max_messages) {
        const char *message = (const char *)sqlite3_column_text(stmt, 0);
        strncpy(messages[message_count], message, 512);
        message_count++;
    }

    sqlite3_finalize(stmt);
    return message_count;
}

// Deliver offline messages to the client
void deliver_offline_messages(const char *username, struct lws *wsi) {
    char messages[10][512]; // Store up to 10 offline messages
    int message_count = fetch_offline_messages(username, messages, 10);

    for (int i = 0; i < message_count; i++) {
        unsigned char buf[LWS_PRE + 512];
        int msg_len = snprintf((char *)(buf + LWS_PRE), 512, "[Offline] %s", messages[i]);
        if (msg_len > 0) {
            lws_write(wsi, buf + LWS_PRE, msg_len, LWS_WRITE_TEXT);
        }
    }

    // Optionally delete the messages after sending them to the user
    char delete_query[256];
    snprintf(delete_query, sizeof(delete_query), "DELETE FROM offline_messages WHERE recipient = ?;");
    sqlite3_stmt *stmt;
    if (sqlite3_prepare_v2(db, delete_query, -1, &stmt, NULL) == SQLITE_OK) {
        sqlite3_bind_text(stmt, 1, username, -1, SQLITE_STATIC);
        sqlite3_step(stmt);
        sqlite3_finalize(stmt);
    }
}

void store_message_history(const char *sender, const char *recipient, const char *message) {
    const char *insert_query =
        "INSERT INTO message_history (sender, recipient, message) VALUES (?, ?, ?);";
    sqlite3_stmt *stmt;

    if (sqlite3_prepare_v2(db, insert_query, -1, &stmt, NULL) != SQLITE_OK) {
        fprintf(stderr, "[ERROR] Historique: préparation échouée: %s\n", sqlite3_errmsg(db));
        return;
    }

    sqlite3_bind_text(stmt, 1, sender, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, recipient, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 3, message, -1, SQLITE_STATIC);

    if (sqlite3_step(stmt) != SQLITE_DONE) {
        fprintf(stderr, "[ERROR] Historique: insertion échouée: %s\n", sqlite3_errmsg(db));
    } else {
        printf("[INFO] Message historique stocké entre %s et %s\n", sender, recipient);
    }

    sqlite3_finalize(stmt);
}

char **get_recent_contacts(const char *username, int *count) {
    const char *query =
        "SELECT DISTINCT CASE "
        "WHEN sender = ? THEN recipient "
        "WHEN recipient = ? THEN sender "
        "END AS contact "
        "FROM message_history "
        "WHERE sender = ? OR recipient = ? "
        "ORDER BY timestamp DESC LIMIT 20;";

    sqlite3_stmt *stmt;
    *count = 0;
    static char *contacts[20];

    if (sqlite3_prepare_v2(db, query, -1, &stmt, NULL) != SQLITE_OK) {
        fprintf(stderr, "[ERROR] Récupération des contacts: %s\n", sqlite3_errmsg(db));
        return NULL;
    }

    sqlite3_bind_text(stmt, 1, username, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, username, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 3, username, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 4, username, -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW && *count < 20) {
        const unsigned char *contact = sqlite3_column_text(stmt, 0);
        if (contact) {
            contacts[*count] = strdup((const char *)contact);
            (*count)++;
        }
    }

    sqlite3_finalize(stmt);
    return contacts;
}
