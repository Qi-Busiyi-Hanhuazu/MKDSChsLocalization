PREFIX := $(subst \,/,$(DEVKITARM))/bin/arm-none-eabi-
CC := $(PREFIX)gcc
OBJCOPY := $(PREFIX)objcopy

BUILD ?= build
CFILES := $(wildcard $(SOURCES)/*.c)
SFILES := $(wildcard $(SOURCES)/*.s)
OFILES := $(addprefix $(BUILD)/$(TARGET)_,$(notdir $(CFILES:.c=.o) $(SFILES:.s=.o)))

ARCH := -mcpu=arm946e-s -mthumb -mthumb-interwork
CFLAGS := $(ARCH) -Os -Wall -Wextra -Werror -ffreestanding -fno-builtin \
          -fno-unwind-tables -fno-asynchronous-unwind-tables
ASFLAGS := $(ARCH) -x assembler-with-cpp
LDFLAGS := $(ARCH) -nostdlib -Wl,--build-id=none,--defsym=CODEADDR=$(CODEADDR),-T,linker.x

.PHONY: all clean
all: $(BUILD)/$(TARGET).bin

clean:
	$(RM) $(wildcard $(BUILD)/repl_*.bin $(BUILD)/repl_*.elf $(BUILD)/repl_*.o)

$(BUILD)/$(TARGET).bin: $(BUILD)/$(TARGET).elf
	$(OBJCOPY) -O binary --only-section=.text $< $@

$(BUILD)/$(TARGET).elf: $(OFILES) linker.x
	$(CC) $(LDFLAGS) $(OFILES) -o $@

$(BUILD)/$(TARGET)_%.o: $(SOURCES)/%.c
	mkdir -p $(@D)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $< -o $@

$(BUILD)/$(TARGET)_%.o: $(SOURCES)/%.s
	mkdir -p $(@D)
	$(CC) $(ASFLAGS) $(CPPFLAGS) -c $< -o $@
