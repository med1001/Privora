#include "broadcast.h"
#include "server.h"   // Include server.h to access the global clients array and mutex
#include <string.h>   // For strlen
#include <sys/socket.h> // For send
#include <stdio.h>    // For perror

// Function to broadcast messages to all clients except the sender
void broadcast_message(const char *message, int sender_socket) {
    pthread_mutex_lock(&clients_mutex);  // Lock to ensure thread safety

    // Iterate over all clients and send the message
    for (int i = 0; i < num_clients; i++) {
        if (clients[i]->socket_fd != sender_socket) {
            // Send message to each client except the sender
            if (send(clients[i]->socket_fd, message, strlen(message), 0) == -1) {
                perror("Error sending message");
            }
        }
    }

    pthread_mutex_unlock(&clients_mutex);  // Unlock the mutex
}
