#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <sys/socket.h>
#include <netinet/in.h>

#define PORT 8080
#define MAX_CLIENTS 10

// Function to handle client communication
void* handle_client(void* client_socket) {
    int client_fd = *((int*)client_socket);
    free(client_socket);
    
    char buffer[1024];
    int bytes_read;

    // Receive messages from the client
    while ((bytes_read = recv(client_fd, buffer, sizeof(buffer), 0)) > 0) {
        buffer[bytes_read] = '\0';
        printf("Received message: %s\n", buffer);
        send(client_fd, buffer, bytes_read, 0);  // Echo the message back
    }

    close(client_fd);
    printf("Client disconnected.\n");
    return NULL;
}

int main() {
    int server_fd, client_fd;
    struct sockaddr_in server_addr, client_addr;
    socklen_t client_addr_len = sizeof(client_addr);
    
    // Create socket
    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("Socket creation failed");
        exit(EXIT_FAILURE);
    }
    printf("Socket created successfully.\n");

    // Set up server address
    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = INADDR_ANY;
    server_addr.sin_port = htons(PORT);

    // Bind the socket to the address
    if (bind(server_fd, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        perror("Bind failed");
        close(server_fd);
        exit(EXIT_FAILURE);
    }
    printf("Bind successful.\n");

    // Listen for incoming connections
    if (listen(server_fd, MAX_CLIENTS) < 0) {
        perror("Listen failed");
        close(server_fd);
        exit(EXIT_FAILURE);
    }
    printf("Listening for incoming connections on port %d...\n", PORT);

    // Accept client connections and create threads to handle them
    while (1) {
        client_fd = accept(server_fd, (struct sockaddr*)&client_addr, &client_addr_len);
        if (client_fd < 0) {
            perror("Accept failed");
            continue;
        }

        printf("Client connected.\n");

        // Allocate memory for client socket
        int* new_sock = malloc(sizeof(int));
        *new_sock = client_fd;

        // Create a new thread to handle the client
        pthread_t client_thread;
        if (pthread_create(&client_thread, NULL, handle_client, (void*)new_sock) != 0) {
            perror("Thread creation failed");
            close(client_fd);
            continue;
        }

        // Detach the thread to handle client communication independently
        pthread_detach(client_thread);
    }

    close(server_fd);
    return 0;
}
