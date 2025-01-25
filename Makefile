# Variables
CC = gcc
CFLAGS = -Wall -g
SRCDIR = src
BUILDDIR = build
INCLUDEDIR = include
TARGET = $(BUILDDIR)/server

# Collect source files
SRC = $(wildcard $(SRCDIR)/*.c)
OBJ = $(SRC:$(SRCDIR)/%.c=$(BUILDDIR)/%.o)

# Default target
all: $(TARGET)

# Link the final binary
$(TARGET): $(OBJ)
	@mkdir -p $(BUILDDIR)
	$(CC) $(CFLAGS) -o $@ $^

# Compile object files
$(BUILDDIR)/%.o: $(SRCDIR)/%.c $(INCLUDEDIR)/%.h
	@mkdir -p $(BUILDDIR)
	$(CC) $(CFLAGS) -I$(INCLUDEDIR) -c $< -o $@

# Clean build artifacts
clean:
	rm -rf $(BUILDDIR)

# Rebuild everything
rebuild: clean all

.PHONY: all clean rebuild
