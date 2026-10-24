#---------------------------------------------------------------------------------
# path to tools
#---------------------------------------------------------------------------------
ifeq ($(strip $(DEVKITARM)),)
$(error "Please set DEVKITARM in your environment")
endif

PREFIX := $(subst \,/,$(DEVKITARM))/bin/arm-none-eabi-
CC := $(PREFIX)gcc
OBJCOPY := $(PREFIX)objcopy

#---------------------------------------------------------------------------------
# source and output files
#---------------------------------------------------------------------------------
TARGET ?= newcode
BUILD ?= ../out
SOURCES ?= source
CODEADDR ?= 0x02000000
CFILES := $(wildcard $(SOURCES)/*.c)
SFILES := $(wildcard $(SOURCES)/*.s)
OFILES := $(addprefix $(BUILD)/$(TARGET)_,$(notdir $(CFILES:.c=.o) $(SFILES:.s=.o)))

#---------------------------------------------------------------------------------
# options for code generation
#---------------------------------------------------------------------------------
ARCH := -mcpu=arm946e-s -mthumb -mthumb-interwork
CFLAGS := $(ARCH) -Os -Wall -Wextra -Werror -ffreestanding -fno-builtin \
          -fno-unwind-tables -fno-asynchronous-unwind-tables -MMD -MP
ASFLAGS := $(ARCH) -x assembler-with-cpp -MMD -MP
LDFLAGS := $(ARCH) -nostdlib -Wl,--build-id=none,--defsym=CODEADDR=$(CODEADDR),-T,linker.x

#---------------------------------------------------------------------------------
# main targets
#---------------------------------------------------------------------------------
.PHONY: all clean
all: $(BUILD)/$(TARGET).bin

clean:
	$(RM) $(wildcard $(BUILD)/repl_*.bin $(BUILD)/repl_*.elf $(BUILD)/repl_*.o $(BUILD)/repl_*.d)

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

-include $(OFILES:.o=.d)
