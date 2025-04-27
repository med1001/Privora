#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <libwebsockets.h>
#include <cjson/cJSON.h>
#include "storage.h"

#define MAX_CLIENTS 100
#define MAX_USERNAME_LEN 32
#define MAX_MESSAGE_HISTORY 100

typedef struct {
    struct lws *wsi;
    char username[MAX_USERNAME_LEN];
} client_t;

static client_t clients[MAX_CLIENTS];
pthread_mutex_t clients_mutex = PTHREAD_MUTEX_INITIALIZER;

static int find_client_index(struct lws *wsi) {
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (clients[i].wsi == wsi)
            return i;
    }
    return -1;
}

static int find_client_by_username(const char *username) {
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (clients[i].wsi != NULL && strcmp(clients[i].username, username) == 0)
            return i;
    }
    return -1;
}

void add_client(struct lws *wsi, const char *username) {
    pthread_mutex_lock(&clients_mutex);
    printf("[DEBUG] add_client: Looking for free slot to add '%s'\n", username);

    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (clients[i].wsi == NULL) {
            clients[i].wsi = wsi;
            strncpy(clients[i].username, username, MAX_USERNAME_LEN - 1);
            clients[i].username[MAX_USERNAME_LEN - 1] = '\0';
            printf("[INFO] New client added: %s (slot %d)\n", username, i);
            break;
        }
    }

    pthread_mutex_unlock(&clients_mutex);
}

void remove_client(struct lws *wsi) {
    pthread_mutex_lock(&clients_mutex);
    printf("[DEBUG] remove_client: Searching client to remove\n");

    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (clients[i].wsi == wsi) {
            printf("[INFO] Client disconnected: %s (slot %d)\n", clients[i].username, i);
            clients[i].wsi = NULL;
            clients[i].username[0] = '\0';
            break;
        }
    }

    pthread_mutex_unlock(&clients_mutex);
}

void send_private_message(const char *recipient, const char *message, struct lws *sender_wsi) {
    pthread_mutex_lock(&clients_mutex);

    int recipient_index = find_client_by_username(recipient);
    int sender_index = find_client_index(sender_wsi);
    const char *sender_name = sender_index != -1 ? clients[sender_index].username : "unknown";

    printf("[DEBUG] send_private_message: from=%s to=%s message=%s\n", sender_name, recipient, message);

    if (recipient_index != -1) {
        char response[512];
        snprintf(response, sizeof(response), "{\"type\":\"message\",\"from\":\"%s\",\"message\":\"%s\"}", sender_name, message);

        unsigned char buf[LWS_PRE + 512];
        size_t msg_len = strlen(response);
        memcpy(&buf[LWS_PRE], response, msg_len);

        lws_write(clients[recipient_index].wsi, &buf[LWS_PRE], msg_len, LWS_WRITE_TEXT);
        printf("[INFO] Private message sent to %s\n", recipient);
        printf("[DEBUG] Message sent over WebSocket: %s\n", response);

        store_message_history(sender_name, recipient, message);
    } else {
        printf("[WARN] Recipient '%s' not online, storing offline message\n", recipient);
        store_offline_message(sender_name, recipient, message);
    }

    pthread_mutex_unlock(&clients_mutex);
}

void fetch_recent_conversations(const char *username, struct lws *wsi) {
    printf("[DEBUG] Fetching recent conversations for user: %s\n", username);
    int count = 0;
    char **contacts = get_recent_contacts(username, &count);

    if (contacts != NULL && count > 0) {
        char response[1024];
        snprintf(response, sizeof(response), "{\"contacts\":[");
        for (int i = 0; i < count; i++) {
            if (i > 0) strncat(response, ",", sizeof(response) - strlen(response) - 1);
            strncat(response, "\"", sizeof(response) - strlen(response) - 1);
            strncat(response, contacts[i], sizeof(response) - strlen(response) - 1);
            strncat(response, "\"", sizeof(response) - strlen(response) - 1);
        }
        strncat(response, "]}", sizeof(response) - strlen(response) - 1);

        unsigned char buf[LWS_PRE + 1024];
        size_t msg_len = strlen(response);
        memcpy(&buf[LWS_PRE], response, msg_len);
        lws_write(wsi, &buf[LWS_PRE], msg_len, LWS_WRITE_TEXT);

        printf("[INFO] Sent recent contacts for %s\n", username);
        printf("[DEBUG] Contacts response: %s\n", response);
    } else {
        printf("[INFO] No recent contacts found for %s\n", username);
    }
}

void fetch_message_history(const char *username, struct lws *wsi) {
    printf("[DEBUG] Fetching message history for: %s\n", username);

    const char *query = "SELECT sender, recipient, message, timestamp FROM message_history "
                        "WHERE sender = ? OR recipient = ? "
                        "ORDER BY timestamp DESC LIMIT 20;";

    sqlite3_stmt *stmt;
    char response[4096] = "{\"type\":\"history\",\"messages\":[";
    int message_count = 0;

    if (sqlite3_prepare_v2(db, query, -1, &stmt, NULL) != SQLITE_OK) {
        fprintf(stderr, "[ERROR] Error fetching message history: %s\n", sqlite3_errmsg(db));
        return;
    }

    sqlite3_bind_text(stmt, 1, username, -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, username, -1, SQLITE_STATIC);

    while (sqlite3_step(stmt) == SQLITE_ROW && message_count < MAX_MESSAGE_HISTORY) {
        const char *sender = (const char *)sqlite3_column_text(stmt, 0);
        const char *recipient = (const char *)sqlite3_column_text(stmt, 1);
        const char *message = (const char *)sqlite3_column_text(stmt, 2);
        const char *timestamp = (const char *)sqlite3_column_text(stmt, 3);

        char message_entry[512];
        snprintf(message_entry, sizeof(message_entry),
                 "{\"sender\":\"%s\",\"recipient\":\"%s\",\"message\":\"%s\",\"timestamp\":\"%s\"}",
                 sender, recipient, message, timestamp);

        if (message_count > 0) {
            strncat(response, ",", sizeof(response) - strlen(response) - 1);
        }

        strncat(response, message_entry, sizeof(response) - strlen(response) - 1);
        printf("[DEBUG] Message from DB: %s -> %s : %s @ %s\n", sender, recipient, message, timestamp);
        message_count++;
    }

    strncat(response, "]}", sizeof(response) - strlen(response) - 1);
    sqlite3_finalize(stmt);

    if (message_count > 0) {
        unsigned char buf[LWS_PRE + 4096];
        size_t msg_len = strlen(response);
        memcpy(&buf[LWS_PRE], response, msg_len);
        lws_write(wsi, &buf[LWS_PRE], msg_len, LWS_WRITE_TEXT);
        printf("[INFO] Sent message history to %s\n", username);
    } else {
        printf("[INFO] No message history found for %s\n", username);
    }
}

static int callback_chat(struct lws *wsi, enum lws_callback_reasons reason, void *user, void *in, size_t len) {
    switch (reason) {
        case LWS_CALLBACK_ESTABLISHED:
            printf("[EVENT] WebSocket connection established.\n");
            break;

        case LWS_CALLBACK_RECEIVE: {
            printf("[EVENT] Message received: %s\n", (char *)in);

            cJSON *root = cJSON_Parse((char *)in);
            if (!root) {
                printf("[ERROR] Invalid JSON received\n");
                break;
            }

            cJSON *type = cJSON_GetObjectItem(root, "type");

            if (type && strcmp(type->valuestring, "login") == 0) {
                cJSON *username = cJSON_GetObjectItem(root, "username");
                if (username && username->valuestring) {
                    printf("[EVENT] Login request from: %s\n", username->valuestring);
                    add_client(wsi, username->valuestring);

                    printf("[INFO] Checking offline messages for user: %s\n", username->valuestring);
                    deliver_offline_messages(username->valuestring, wsi);

                    fetch_recent_conversations(username->valuestring, wsi);
                    fetch_message_history(username->valuestring, wsi);
                }
            } else if (type && strcmp(type->valuestring, "message") == 0) {
                cJSON *to = cJSON_GetObjectItem(root, "to");
                cJSON *message = cJSON_GetObjectItem(root, "message");

                if (to && message && to->valuestring && message->valuestring) {
                    printf("[EVENT] Message to be sent from current client to %s\n", to->valuestring);
                    send_private_message(to->valuestring, message->valuestring, wsi);
                }
            }

            cJSON_Delete(root);
            break;
        }

        case LWS_CALLBACK_CLOSED:
            printf("[EVENT] WebSocket connection closed.\n");
            remove_client(wsi);
            break;

        default:
            break;
    }

    return 0;
}

static struct lws_protocols protocols[] = {
    {
        "chat-protocol",
        callback_chat,
        0,
        1024,
    },
    { NULL, NULL, 0, 0 }
};

int main(int argc, char **argv) {
    init_database();

    struct lws_context_creation_info info;
    memset(&info, 0, sizeof(info));
    info.port = 8080;
    info.protocols = protocols;

    struct lws_context *context = lws_create_context(&info);
    if (context == NULL) {
        printf("[ERROR] Failed to create WebSocket context\n");
        return -1;
    }

    printf("[SERVER] WebSocket server started on port %d\n", info.port);

    while (1) {
        lws_service(context, 100);
    }

    lws_context_destroy(context);
    return 0;
}
