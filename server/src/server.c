#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <libwebsockets.h>
#include <cjson/cJSON.h>
#include "storage.h" // For offline message storage and discussions

#define MAX_CLIENTS 100
#define MAX_USERNAME_LEN 32
#define MAX_MESSAGE_HISTORY 100 // Limit to 100 recent messages per user

// Client structure to hold connection data
typedef struct {
    struct lws *wsi;
    char username[MAX_USERNAME_LEN];
} client_t;

static client_t clients[MAX_CLIENTS];

// Mutex to protect access to the clients array
pthread_mutex_t clients_mutex = PTHREAD_MUTEX_INITIALIZER;

// Helper functions for managing clients
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

// Function to add a new client to the array
void add_client(struct lws *wsi, const char *username) {
    pthread_mutex_lock(&clients_mutex);
    
    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (clients[i].wsi == NULL) {
            clients[i].wsi = wsi;
            strncpy(clients[i].username, username, MAX_USERNAME_LEN - 1);
            clients[i].username[MAX_USERNAME_LEN - 1] = '\0'; // ensure null-terminated
            printf("[INFO] New client added: %s\n", username);
            break;
        }
    }

    pthread_mutex_unlock(&clients_mutex);
}

// Function to remove a client
void remove_client(struct lws *wsi) {
    pthread_mutex_lock(&clients_mutex);

    for (int i = 0; i < MAX_CLIENTS; i++) {
        if (clients[i].wsi == wsi) {
            printf("[INFO] Client disconnected: %s\n", clients[i].username);
            clients[i].wsi = NULL;
            clients[i].username[0] = '\0';
            break;
        }
    }

    pthread_mutex_unlock(&clients_mutex);
}

// Function to send a private message
void send_private_message(const char *recipient, const char *message, struct lws *sender_wsi) {
    pthread_mutex_lock(&clients_mutex);

    int recipient_index = find_client_by_username(recipient);

    int sender_index = find_client_index(sender_wsi);
    const char *sender_name = sender_index != -1 ? clients[sender_index].username : "unknown";

    if (recipient_index != -1) {
        // Send message to the online user
        

        char response[512];
        snprintf(response, sizeof(response), "{\"from\":\"%s\",\"message\":\"%s\"}", sender_name, message);

        unsigned char buf[LWS_PRE + 512];
        size_t msg_len = strlen(response);
        memcpy(&buf[LWS_PRE], response, msg_len);

        lws_write(clients[recipient_index].wsi, &buf[LWS_PRE], msg_len, LWS_WRITE_TEXT);
        printf("[INFO] Private message sent to %s\n", recipient);
        
        // Store message in database with timestamp
        store_message_history(sender_name, recipient, message);
    } else {
        // Recipient is offline
        printf("[INFO] Storing offline message for %s\n", recipient);
        store_offline_message(sender_name, recipient, message);
    }

    pthread_mutex_unlock(&clients_mutex);
}

// // Function to deliver offline messages after login
// void deliver_offline_messages(const char *username, struct lws *wsi) {
//     char messages[1024];
//     if (fetch_offline_messages(username, messages, sizeof(messages)) > 0) {
//         // Send offline messages back to the user
//         unsigned char buf[LWS_PRE + 1024];
//         size_t msg_len = strlen(messages);
//         memcpy(&buf[LWS_PRE], messages, msg_len);
//         lws_write(wsi, &buf[LWS_PRE], msg_len, LWS_WRITE_TEXT);
//         printf("[INFO] Delivered offline messages to %s\n", username);
//     }
// }

// Function to fetch recent conversations
void fetch_recent_conversations(const char *username, struct lws *wsi) {
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
    }
}

// Function to fetch message history for a specific user
void fetch_message_history(const char *username, struct lws *wsi) {
    // Retrieve last N messages for this user
    const char *query = "SELECT sender, recipient, message, timestamp FROM message_history "
                        "WHERE sender = ? OR recipient = ? "
                        "ORDER BY timestamp DESC LIMIT 20;";

    sqlite3_stmt *stmt;
    char response[2048] = "{\"history\":[";  // Initialize the JSON response string
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
        snprintf(message_entry, sizeof(message_entry), "{\"sender\":\"%s\",\"recipient\":\"%s\",\"message\":\"%s\",\"timestamp\":\"%s\"}",
                 sender, recipient, message, timestamp);

        if (message_count > 0) {
            strncat(response, ",", sizeof(response) - strlen(response) - 1);  // Separate messages with commas
        }

        strncat(response, message_entry, sizeof(response) - strlen(response) - 1);
        message_count++;
    }

    strncat(response, "]}", sizeof(response) - strlen(response) - 1);  // Close the JSON array

    sqlite3_finalize(stmt);

    if (message_count > 0) {
        // Send message history back to the user
        unsigned char buf[LWS_PRE + 2048];
        size_t msg_len = strlen(response);
        memcpy(&buf[LWS_PRE], response, msg_len);
        lws_write(wsi, &buf[LWS_PRE], msg_len, LWS_WRITE_TEXT);
        printf("[INFO] Sent message history to %s\n", username);
    }
}

// WebSocket callback function to handle incoming messages
static int callback_chat(struct lws *wsi, enum lws_callback_reasons reason, void *user, void *in, size_t len) {
    switch (reason) {
        case LWS_CALLBACK_ESTABLISHED: {
            // Client has connected, waiting for login message
            printf("[INFO] New WebSocket connection established.\n");
            break;
        }

        case LWS_CALLBACK_RECEIVE: {
            // Parsing JSON message
            cJSON *root = cJSON_Parse((char *)in);
            if (!root) {
                printf("Invalid JSON received\n");
                break;
            }

            cJSON *type = cJSON_GetObjectItem(root, "type");

            if (type && strcmp(type->valuestring, "login") == 0) {
                // Handle login
                cJSON *username = cJSON_GetObjectItem(root, "username");
                if (username && username->valuestring) {
                    // Add the client after login
                    add_client(wsi, username->valuestring);
                    printf("User logged in: %s\n", username->valuestring);

                    // ✅ Deliver offline messages only after login is complete
                    printf("[INFO] Checking offline messages for user: %s\n", username->valuestring);
                    deliver_offline_messages(username->valuestring, wsi);

                    // Fetch and send recent conversations
                    fetch_recent_conversations(username->valuestring, wsi);

                    // Fetch and send message history for the logged-in user
                    fetch_message_history(username->valuestring, wsi);
                }
            } else if (type && strcmp(type->valuestring, "message") == 0) {
                // Handle message
                cJSON *to = cJSON_GetObjectItem(root, "to");
                cJSON *message = cJSON_GetObjectItem(root, "message");

                if (to && message && to->valuestring && message->valuestring) {
                    send_private_message(to->valuestring, message->valuestring, wsi);
                }
            }

            cJSON_Delete(root);
            break;
        }

        case LWS_CALLBACK_CLOSED: {
            // Client has disconnected
            remove_client(wsi);
            break;
        }

        default:
            break;
    }

    return 0;
}

// WebSocket protocols
static struct lws_protocols protocols[] = {
    {
        "chat-protocol",
        callback_chat,
        0,
        1024,
    },
    { NULL, NULL, 0, 0 } // terminator
};

int main(int argc, char **argv) {
    // Initialize database
    init_database();

    // WebSocket context creation
    struct lws_context_creation_info info;
    memset(&info, 0, sizeof(info));
    info.port = 8080;
    info.protocols = protocols;

    struct lws_context *context = lws_create_context(&info);
    if (context == NULL) {
        printf("Error creating WebSocket context\n");
        return -1;
    }

    // Server loop
    while (1) {
        lws_service(context, 100);
    }

    lws_context_destroy(context);
    return 0;
}
