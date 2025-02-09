#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <pthread.h>

#define SERVER_IP "127.0.0.1"
#define SERVER_PORT 8080
#define MAX_MSG_LENGTH 256  // Updated max message length

int sock;
pthread_t recv_thread;
int running = 1;

// Function to receive messages from the server
void *receive_messages(void *arg) {
    char buffer[MAX_MSG_LENGTH];
    ssize_t bytes_received;

    while (running) {
        bytes_received = recv(sock, buffer, sizeof(buffer) - 1, 0);
        if (bytes_received > 0) {
            buffer[bytes_received] = '\0';
            printf("\nReceived: %s\nEnter message: ", buffer);
            fflush(stdout);
        } else {
            printf("\nServer disconnected. Exiting.\n");
            running = 0;
            break;
        }
    }

    return NULL;
}

// Function to send messages to the server
void send_message() {
    char message[MAX_MSG_LENGTH + 2];  // +2 to handle newline and null terminator

    while (running) {
        printf("Enter message: ");
        fgets(message, sizeof(message), stdin);
        message[strcspn(message, "\n")] = '\0'; // Remove newline

        // Validate input: check for empty messages
        if (strlen(message) == 0) {
            printf("Error: Message cannot be empty.\n");
            continue;
        }

        // Validate input: check message length
        if (strlen(message) > MAX_MSG_LENGTH) {
            printf("Error: Message exceeds %d characters. Please shorten it.\n", MAX_MSG_LENGTH);
            continue;
        }

        if (strcmp(message, "/exit") == 0) {
            printf("Exiting...\n");
            running = 0;
            shutdown(sock, SHUT_RDWR);
            close(sock);
            break;
        } else if (strcmp(message, "/help") == 0) {
            printf("Available commands:\n");
            printf("/exit - Disconnect from the server and exit the client.\n");
            printf("/help - Display this help message.\n");
            continue;
        }

        if (message[0] == '/') {
            printf("Invalid command. Type '/help' for a list of valid commands.\n");
            continue;
        }

        if (send(sock, message, strlen(message), 0) < 0) {
            perror("Message send failed");
            running = 0;
            break;
        }
    }

    printf("Client terminated.\n");
}

int main() {
    struct sockaddr_in server_address;

    if ((sock = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
        perror("Socket creation failed");
        exit(EXIT_FAILURE);
    }
    printf("Socket created successfully.\n");

    server_address.sin_family = AF_INET;
    server_address.sin_port = htons(SERVER_PORT);

    if (inet_pton(AF_INET, SERVER_IP, &server_address.sin_addr) <= 0) {
        perror("Invalid address or address not supported");
        close(sock);
        exit(EXIT_FAILURE);
    }

    if (connect(sock, (struct sockaddr*)&server_address, sizeof(server_address)) < 0) {
        perror("Connection to server failed");
        close(sock);
        exit(EXIT_FAILURE);
    }

    printf("Connected to the server successfully.\n");

    if (pthread_create(&recv_thread, NULL, receive_messages, NULL) != 0) {
        perror("Error creating receiving thread");
        close(sock);
        exit(EXIT_FAILURE);
    }

    send_message();

    pthread_cancel(recv_thread);
    pthread_join(recv_thread, NULL);

    return 0;
}
