#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>  // Use libcurl for HTTP requests
#include <ctype.h>      // For handling password input

// Function to capture server response
static size_t write_callback(void *buffer, size_t size, size_t nmemb, void *userp) {
    strcat((char *)userp, (char *)buffer);  // Append response to user buffer
    return size * nmemb;
}

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

    // Buffer to store the response
    char response[1024] = "";  

    // Send POST request to Flask authentication server
    CURL *curl = curl_easy_init();
    if (curl) {
        struct curl_slist *headers = NULL;
        headers = curl_slist_append(headers, "Content-Type: application/json");

        curl_easy_setopt(curl, CURLOPT_URL, "http://127.0.0.1:5000/register");
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, data);
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, response);

        CURLcode res = curl_easy_perform(curl);
        if (res == CURLE_OK) {
            // Ensure response is not empty before checking for "error"
            if (strlen(response) > 0 && strstr(response, "\"error\"")) {
                printf("\nRegistration failed: %s\n", response);
            } else {
                printf("\nRegistration request sent successfully!\n");
            }
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

    // Masquer la saisie du mot de passe
    printf("Enter password: ");
    char ch;
    int i = 0;
    while ((ch = getchar()) != '\n' && ch != EOF); // Clear the buffer
    while ((ch = getchar()) != '\n' && ch != EOF) {
        password[i++] = ch;
        putchar('*');  // Affiche un astérisque pour chaque caractère du mot de passe
    }
    password[i] = '\0';

    // Construct JSON payload
    char data[128];
    snprintf(data, sizeof(data),
             "{\"username\": \"%s\", \"password\": \"%s\"}", username, password);

    // Send POST request to Flask authentication server
    CURL *curl = curl_easy_init();
    int login_successful = 0;
    char response[1024] = "";  // Buffer to store server response

    if (curl) {
        struct curl_slist *headers = NULL;
        headers = curl_slist_append(headers, "Content-Type: application/json");

        curl_easy_setopt(curl, CURLOPT_URL, "http://127.0.0.1:5000/login");
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, data);
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, response);

        CURLcode res = curl_easy_perform(curl);
        if (res == CURLE_OK) {
            // Check server response
            if (strstr(response, "\"error\": \"Email not verified\"")) {
                printf("Login failed: Email not verified. Please check your inbox.\n");
            } else if (strstr(response, "\"error\": \"Invalid credentials\"")) {
                printf("Login failed: Invalid username or password.\n");
            } else {
                printf("Login successful!\n");
                login_successful = 1;
            }
        } else {
            fprintf(stderr, "Login failed: %s\n", curl_easy_strerror(res));
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
