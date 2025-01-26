#ifndef BROADCAST_H
#define BROADCAST_H

// Function to broadcast messages to all clients except the sender
void broadcast_message(const char *message, int sender_socket);

#endif
