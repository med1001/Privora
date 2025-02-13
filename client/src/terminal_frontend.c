#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>  // Use libcurl for HTTP requests

// Function to register a new user
void register_user() {
    char username[50], email[100], password[50];
    printf("Enter username: ");
    scanf("%s", username);
    printf("Enter email: ");
    scanf("%s", email);
    printf("Enter password: ");
    scanf("%s", password);

    // Construct JSON payload
    char data[256];
    snprintf(data, sizeof(data),
             "{\"username\": \"%s\", \"email\": \"%s\", \"password\": \"%s\"}",
             username, email, password);

    // Send POST request to Flask authentication server
    CURL *curl = curl_easy_init();
    if (curl) {
        struct curl_slist *headers = NULL;
        headers = curl_slist_append(headers, "Content-Type: application/json");

        curl_easy_setopt(curl, CURLOPT_URL, "http://127.0.0.1:5000/register");
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, data);
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

        CURLcode res = curl_easy_perform(curl);
        if (res == CURLE_OK) {
            printf("\nRegistration request sent successfully!\n");
        } else {
            fprintf(stderr, "\nFailed to send request: %s\n", curl_easy_strerror(res));
        }

        curl_easy_cleanup(curl);
        curl_slist_free_all(headers);
    }
}

// Function to log in a user
int login_user(char *username) {
    char password[50];
    printf("Enter username: ");
    scanf("%s", username);
    printf("Enter password: ");
    scanf("%s", password);

    // Construct JSON payload
    char data[128];
    snprintf(data, sizeof(data),
             "{\"username\": \"%s\", \"password\": \"%s\"}", username, password);

    // Send POST request to Flask authentication server
    CURL *curl = curl_easy_init();
    int login_successful = 0;

    if (curl) {
        struct curl_slist *headers = NULL;
        headers = curl_slist_append(headers, "Content-Type: application/json");

        curl_easy_setopt(curl, CURLOPT_URL, "http://127.0.0.1:5000/login");
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, data);
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);

        CURLcode res = curl_easy_perform(curl);
        if (res == CURLE_OK) {
            printf("\nLogin successful!\n");
            login_successful = 1;
        } else {
            fprintf(stderr, "\nLogin failed: %s\n", curl_easy_strerror(res));
        }

        curl_easy_cleanup(curl);
        curl_slist_free_all(headers);
    }

    return login_successful;
}

// Function to display the menu for user registration and login
void display_menu(char *username) {
    int choice;
    do {
        printf("\nChat Application - Account Management\n");
        printf("1. Register\n");
        printf("2. Login\n");
        printf("3. Exit\n");
        printf("Enter your choice: ");
        scanf("%d", &choice);

        switch (choice) {
            case 1:
                register_user();
                break;
            case 2:
                if (login_user(username)) {
                    return;  // Successful login, exit the menu
                }
                break;
            case 3:
                printf("Exiting...\n");
                exit(0);
                break;
            default:
                printf("Invalid choice. Try again.\n");
                break;
        }
    } while (choice != 3);
}
