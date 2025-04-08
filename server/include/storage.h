#ifndef STORAGE_H
#define STORAGE_H

#include <libwebsockets.h>
#include <sqlite3.h>

extern sqlite3 *db;

// Initialize the database
void init_database();

// Store offline message
void store_offline_message(const char *recipient, const char *message);

// Deliver offline messages and delete after sending
void deliver_offline_messages(const char *username, struct lws *wsi);

// New: Store a message in history
void store_message_history(const char *sender, const char *recipient, const char *message);

// New: Get recent discussion usernames for a user
char **get_recent_contacts(const char *username, int *count);

// In storage.h, declare the function prototype
int fetch_offline_messages(const char *username, char messages[10][512], int max_messages);

#endif
