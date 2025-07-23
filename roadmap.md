# Project Roadmap

Welcome to the Privora roadmap! This document outlines the major features and improvements planned for the future of this project. It's a work in progress.

## Table of Contents
- [Introduction](#introduction)
- [Current Goals](#current-goals)
- [Recently Completed Features](#recently-completed-features)
- [Future Enhancements](#future-enhancements)
- [Completed Milestones](#completed-milestones)
- [How to Contribute](#how-to-contribute)

## Introduction

Privora is a real-time chat application built on a client-server architecture. It enables seamless communication between users while leveraging multithreading, network communication, and efficient socket programming.

This chat app roadmap outlines the goals for the upcoming phases of the project. This includes upcoming features, optimizations, and bug fixes. We want to keep the community informed and involved in the direction we're heading.

## Current Goals

With the core functionality of the project already implemented — including real-time private messaging, message persistence, and a functional web-based interface — the current focus has shifted toward refining and securing the system.

Our top priorities for the coming months include:

- Implementing user presence tracking (online/offline status).
- Reinforcing security practices, including:
  - Input sanitization and session management.
  - End-to-end encryption for private messages.
- Continuously improving the user experience based on ongoing feedback and testing.

These enhancements aim to make the platform more secure, reliable, and user-friendly.

### Goal 1: Server-Side Development
- Set up a WebSocket-based backend to support real-time communication between users.
- Implement user authentication and connection management.
- Enable direct one-to-one (private) messaging between users.
- Store messages in the backend to support delivery when recipients reconnect (message persistence).
- Handle user presence status (online/offline) for message routing and delivery.
- Ensure scalability and security of the messaging service (e.g., input validation, session handling).

### Goal 2: Client-Side Development (Web App UI)
- Build a responsive web-based user interface for sending and receiving messages.
- Implement UI elements such as:
  - Message input box and send button.
  - Scrollable chat window for real-time message display from other users.
  - Navigation or modal support for help and usage instructions.
- Add user-friendly features like:
  - `/exit` command triggers session logout or page redirect.
  - `/help` displays a modal or tooltip with usage guidelines.
- Ensure real-time updates using WebSockets or other push-based technology for live message exchange.

### Goal 3: Multi-threading and Synchronization
- Ensure the server handles multiple clients in parallel using threads.
- Enable the client to send and receive messages simultaneously without blocking.
- Synchronize access to shared resources to avoid race conditions.

## Recently Completed Features

These features were previously planned and are now fully implemented:

- **Private Messaging**  
Users can send direct messages.

- **Message Timestamps**  
Each message now includes a timestamp to indicate when it was sent.

- **Message History**  
Clients receive recent message history upon login, ensuring continuity in conversations.

## Future Enhancements

In addition to the upcoming features, we have a long-term vision for the project, including some larger initiatives we plan to implement once the current goals are achieved.

- **Security**
Introduce basic encryption for messages to enhance communication security.
Validate user inputs to prevent injection attacks.

- **Scalability**
Optimize the server to handle a higher number of concurrent clients efficiently.
Consider implementing load balancing if needed.

- **Cross-Platform Support**
Ensure compatibility across different operating systems and environments.

## Completed Milestones

Here is a summary of the milestones we have already completed:
- **Milestone 1**: Initial project setup.
- **Milestone 2**: Basic server implementation.
- **Milestone 3**: Basic client implementation.

## How to Contribute

We are always looking for contributors! Here's how you can get started:
1. Fork the repository and clone it to your local machine.
2. Create a new branch for your feature or bugfix.
3. Make your changes and test them thoroughly.
4. Submit a pull request with a clear description of your changes.

---
Thank you for supporting the project! We appreciate the contributions from the community and are excited to continue building this together.

