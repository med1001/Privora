#ifndef SERVER_H
#define SERVER_H

#include <pthread.h>

// Client structure
typedef struct {
    int socket_fd;        // Client socket file descriptor
    pthread_t thread_id;  // Thread ID for handling the client
} client_t;

// Global variables
extern client_t *clients[100];  // Array to hold client connections
extern int num_clients;         // Track the number of connected clients
extern pthread_mutex_t clients_mutex;  // Mutex for thread safety

// Function to handle client communication
void *client_handler(void *arg);

// Function to accept client connections
void accept_connections(int server_fd);

#endif
