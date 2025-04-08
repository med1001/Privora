#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <libwebsockets.h>
#include <cjson/cJSON.h>
#include "storage.h" // For offline message storage

#define MAX_CLIENTS 100
#define MAX_USERNAME_LEN 32

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
    if (recipient_index != -1) {
        // Send message to the online user
        int sender_index = find_client_index(sender_wsi);
        const char *sender_name = sender_index != -1 ? clients[sender_index].username : "unknown";

        char response[512];
        snprintf(response, sizeof(response), "{\"from\":\"%s\",\"message\":\"%s\"}", sender_name, message);

        unsigned char buf[LWS_PRE + 512];
        size_t msg_len = strlen(response);
        memcpy(&buf[LWS_PRE], response, msg_len);

        lws_write(clients[recipient_index].wsi, &buf[LWS_PRE], msg_len, LWS_WRITE_TEXT);
        printf("[INFO] Private message sent to %s\n", recipient);
    } else {
        // Recipient is offline
        printf("[INFO] Storing offline message for %s\n", recipient);
        store_offline_message(recipient, message);
    }

    pthread_mutex_unlock(&clients_mutex);
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

// Main function to initialize the WebSocket server
int main(void) {
    struct lws_context_creation_info info;
    struct lws_context *context;

    init_database();
    
    memset(&info, 0, sizeof(info));
    info.port = 9000;
    info.protocols = protocols;

    context = lws_create_context(&info);
    if (context == NULL) {
        fprintf(stderr, "lws_create_context failed\n");
        return -1;
    }

    printf("Server started on port 9000\n");

    while (1) {
        lws_service(context, 1000);
    }

    lws_context_destroy(context);
    return 0;
}