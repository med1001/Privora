#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <pthread.h>

#define SERVER_IP "127.0.0.1" // Server IP address
#define SERVER_PORT 8080      // Server port
#define MAX_MSG_LENGTH 1024   // Maximum message length

int sock; // Global socket descriptor

// Function to receive messages from the server
void *receive_messages(void *arg) {
    char buffer[MAX_MSG_LENGTH];
    ssize_t bytes_received;

    while (1) {
        // Receive messages from the server
        bytes_received = recv(sock, buffer, sizeof(buffer) - 1, 0);
        if (bytes_received > 0) {
            buffer[bytes_received] = '\0';  // Null-terminate the message
            printf("Received: %s\n", buffer);
        } else if (bytes_received == 0) {
            printf("Server closed the connection.\n");
            break;
        } else {
            perror("Error receiving message");
            break;
        }
    }

    close(sock);
    pthread_exit(NULL);
}

// Function to send messages to the server
void send_message(int sock) {
    char message[1024];

    while (1) {
        printf("Enter message: ");
        fgets(message, sizeof(message), stdin);
        
        // Remove newline character from the input
        message[strcspn(message, "\n")] = '\0';

        // Check if the user wants to exit
        if (strcmp(message, "exit") == 0) {
            // Inform the server that the client is exiting (optional)
            printf("Exiting...\n");

            // Break the loop and close the connection
            break;
        }

        // Send the message to the server
        if (send(sock, message, strlen(message), 0) < 0) {
            perror("Message send failed");
            break;
        }
    }
    // Close the socket after exit
    close(sock);
    printf("Client terminated.\n");
}


int main() {
    int sock;
    struct sockaddr_in server_address;

    // Create socket
    if ((sock = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
        perror("Socket creation failed");
        exit(EXIT_FAILURE);
    }
    printf("Socket created successfully.\n");

    // Configure server address
    server_address.sin_family = AF_INET;
    server_address.sin_port = htons(SERVER_PORT);

    if (inet_pton(AF_INET, SERVER_IP, &server_address.sin_addr) <= 0) {
        perror("Invalid address or address not supported");
        close(sock);
        exit(EXIT_FAILURE);
    }

    // Attempt to connect to the server
    if (connect(sock, (struct sockaddr*)&server_address, sizeof(server_address)) < 0) {
        perror("Connection to server failed");
        close(sock);
        exit(EXIT_FAILURE);
    }

    printf("Connected to the server successfully.\n");

    // Call send_message with the socket
    send_message(sock);

    return 0;
}