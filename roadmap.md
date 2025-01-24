# Project Roadmap

Welcome to the Privora roadmap! This document outlines the major features and improvements planned for the future of this project. It's a work in progress.

## Table of Contents
- [Introduction](#introduction)
- [Current Goals](#current-goals)
- [Upcoming Features](#upcoming-features)
- [Future Enhancements](#future-enhancements)
- [Completed Milestones](#completed-milestones)
- [How to Contribute](#how-to-contribute)

## Introduction

Privora is a distributed chat application Built on a client-server architecture, it enables real-time communication between users while emphasizing multithreading, network communication, and efficient socket programming.

This chat app roadmap outlines the goals for the upcoming phases of the project. This includes upcoming features, optimizations, and bug fixes. We want to keep the community informed and involved in the direction we're heading.

## Current Goals

As of now, the core functionality of the project is our main focus as well as addressing user feedback. These goals are of the highest priority as we aim to complete them in the upcoming months.
### Goal 1: Server-Side Development
- Implement a TCP server to handle multiple client connections concurrently.
- Create mechanisms for broadcasting messages to all connected clients.
- Ensure robust error handling for socket operations.
### Goal 2: Client-Side Development
- Build a command-line interface (CLI) client for sending and receiving messages.
- Implement user commands like /exit to disconnect and /help for usage instructions.
- Handle real-time message display from other clients.
### Goal 3: Multi-threading and Synchronization
- Ensure the server handles multiple clients in parallel using threads.
- Enable the client to send and receive messages simultaneously without blocking.
- Synchronize access to shared resources to avoid race conditions.

## Upcoming Features

Here are the major features we plan to work on. These features are already in the planning phase and will be developed and released based on community feedback and demand.

- **Private Messaging** 
Allow users to send private messages to specific clients using commands like /msg <username> <message>.

- **Message Timestamps**
Add timestamps to each message to show when it was sent, improving user experience.

- **Message History** 
Implement a feature to display recent messages when clients join the chat.

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

