# Variables
CC = gcc
CFLAGS = -Wall -g
LDFLAGS = -lcurl  # Add libcurl for HTTP support
SRCDIR = src
BUILDDIR = build
INCLUDEDIR = include
TARGET = $(BUILDDIR)/client

# Collect source files
SRC = $(wildcard $(SRCDIR)/*.c)
OBJ = $(SRC:$(SRCDIR)/%.c=$(BUILDDIR)/%.o)

# Default target
all: $(TARGET)

# Link the final binary
$(TARGET): $(OBJ)
	@mkdir -p $(BUILDDIR)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)  # Include LDFLAGS here

# Compile object files
$(BUILDDIR)/%.o: $(SRCDIR)/%.c $(INCLUDEDIR)/%.h
	@mkdir -p $(BUILDDIR)
	$(CC) $(CFLAGS) -I$(INCLUDEDIR) -c $< -o $@

# Clean build artifacts
clean:
	rm -rf $(BUILDDIR)

.PHONY: all clean
