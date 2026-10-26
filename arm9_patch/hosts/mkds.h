typedef struct
{
  unsigned int data[20];
} FSFile;

#define FS_InitFile ((void (*)(FSFile *))0x02004D80)
#define FS_OpenFile ((int (*)(FSFile *, const char *))0x02004A30)
#define FS_CloseFile ((int (*)(FSFile *))0x020049E8)
#define FS_ReadFileAsync ((int (*)(FSFile *, void *, int))0x020048BC)
#define FS_CancelFile ((void (*)(FSFile *))0x020048CC)
#define FS_SeekFile ((int (*)(FSFile *, int, int))0x02004840)
#define NNS_FndAllocFromExpHeapEx ((void *(*)(void *, unsigned int, int))0x02036B78)
#define NNS_FndFreeToExpHeap ((void (*)(void *, void *))0x02036B34)
#define WM_SetMPDataToPortEx ((int (*)(void (*)(void *), void *, const void *, unsigned short, unsigned short, unsigned short, unsigned short))0x0214416C)
#define OS_DisableInterrupts ((unsigned int (*)(void))0x0200FCA0)
#define OS_RestoreInterrupts ((unsigned int (*)(unsigned int))0x0200FCB4)
#define OS_GetOwnerInfo ((void (*)(void *))0x0200FDDC)
#define RTC_GetDate ((int (*)(void *))0x0214E15C)
#define RTC_GetTime ((int (*)(void *))0x0214E09C)

/* FS_GetLength is inlined by the SDK; keep its FSFile layout here. */
#define FS_GetLength(file) ((file)->data[10] - (file)->data[9])
#define FS_TellFile(file) (((volatile FSFile *)(file))->data[11] - (file)->data[9])
#define FS_IsBusy(file) (((volatile FSFile *)(file))->data[3] & 1)
#define FS_GetResultCode(file) (((volatile FSFile *)(file))->data[5])
