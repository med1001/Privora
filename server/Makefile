# Variables
CC = gcc
CFLAGS = -Wall -g -I/usr/include
LDFLAGS = -lwebsockets -lsqlite3 -lcjson
SRCDIR = src
BUILDDIR = build
INCLUDEDIR = include
TARGET = $(BUILDDIR)/server

# Source files
SRC = $(wildcard $(SRCDIR)/*.c)
OBJ = $(patsubst $(SRCDIR)/%.c,$(BUILDDIR)/%.o,$(SRC))

# Default target
all: $(TARGET)

# Link the final binary
$(TARGET): $(OBJ)
	@mkdir -p $(BUILDDIR)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

# Compile object files
$(BUILDDIR)/%.o: $(SRCDIR)/%.c
	@mkdir -p $(BUILDDIR)
	$(CC) $(CFLAGS) -I$(INCLUDEDIR) -I/usr/include -c $< -o $@

# Clean build artifacts
clean:
	rm -rf $(BUILDDIR)

.PHONY: all clean
