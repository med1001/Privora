#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include <netinet/in.h>
#include "server.h"
#include "broadcast.h"  // Include the broadcast header

#define MAX_CLIENTS 100

// Global variables
client_t *clients[MAX_CLIENTS];  // Array to hold client connections
int num_clients = 0;             // Track the number of connected clients
pthread_mutex_t clients_mutex = PTHREAD_MUTEX_INITIALIZER;  // Mutex for thread safety

// Function to handle client communication
void *client_handler(void *arg) {
    client_t *client = (client_t *)arg;
    char buffer[1024];
    ssize_t bytes_received;

    // Receive messages from the client
    while ((bytes_received = recv(client->socket_fd, buffer, sizeof(buffer), 0)) > 0) {
        buffer[bytes_received] = '\0';  // Null-terminate the received message
        printf("Received message: %s\n", buffer);

        // Broadcast the message to other clients
        broadcast_message(buffer, client->socket_fd);
    }

    // Handle client disconnection
    close(client->socket_fd);
    pthread_mutex_lock(&clients_mutex);
    for (int i = 0; i < num_clients; i++) {
        if (clients[i]->socket_fd == client->socket_fd) {
            // Remove the client from the list
            clients[i] = clients[num_clients - 1];
            num_clients--;
            break;
        }
    }
    pthread_mutex_unlock(&clients_mutex);
    free(client);
    return NULL;
}

// Function to accept client connections
void accept_connections(int server_fd) {
    struct sockaddr_in client_addr;
    socklen_t client_len = sizeof(client_addr);
    int client_socket;

    while ((client_socket = accept(server_fd, (struct sockaddr *)&client_addr, &client_len)) >= 0) {
        if (num_clients >= MAX_CLIENTS) {
            printf("Max clients reached, rejecting connection.\n");
            close(client_socket);
            continue;
        }

        // Allocate memory for the new client
        client_t *new_client = (client_t *)malloc(sizeof(client_t));
        new_client->socket_fd = client_socket;

        // Add client to the global clients array
        pthread_mutex_lock(&clients_mutex);
        clients[num_clients++] = new_client;
        pthread_mutex_unlock(&clients_mutex);

        // Create a new thread to handle the client
        if (pthread_create(&new_client->thread_id, NULL, client_handler, (void *)new_client) != 0) {
            perror("Failed to create thread");
            close(client_socket);
            free(new_client);
        }
    }
}

// Main server loop
int main() {
    int server_fd;
    struct sockaddr_in server_addr;

    // Create server socket
    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == -1) {
        perror("Socket creation failed");
        exit(EXIT_FAILURE);
    }

    // Set up the server address struct
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(8080);

    // Bind the socket
    if (bind(server_fd, (struct sockaddr *)&server_addr, sizeof(server_addr)) == -1) {
        perror("Bind failed");
        exit(EXIT_FAILURE);
    }

    // Listen for incoming connections
    if (listen(server_fd, 10) == -1) {
        perror("Listen failed");
        exit(EXIT_FAILURE);
    }

    printf("Server is listening on port 8080...\n");

    // Accept client connections and spawn threads
    accept_connections(server_fd);

    return 0;
}
