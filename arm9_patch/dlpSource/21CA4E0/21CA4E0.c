/* AMCJ overlays: keep the original clone-boot state machine and file service. */
#include "../../dlpSource/dlp_server.h"

#define FN(address, type) ((type)(address))
#define WORD(p, off) (*(u32 *)((u8 *)(p) + (off)))
#define HALF(p, off) (*(u16 *)((u8 *)(p) + (off)))
#define BYTE(p, off) (*((u8 *)(p) + (off)))
#define WM_PORT FN(0x021436b0, int (*)(u32, void (*)(void *), void *))
#define MB_RESPONSE FN(0x02007d51, int (*)(u32, u32))
#define MB_USER FN(0x02007e39, const u8 *(*)(u32))
#define NATIVE_CALLBACK FN(0x0204e789, void (*)(u32, u32, void *))
#define NATIVE_ERROR FN(0x02050f24, void (*)(u32))
#define NATIVE_SCENE_UPDATE FN(0x0202f211, void (*)(void *))
#define NATIVE_WORK (*(u8 **)0x0217aa80)
#define SCENE_WORK (*(u8 **)0x02174ecc)
#define NATIVE_GGID (*(u32 *)0x02154864)
#define SERVICE_INIT FN(DLP_INIT_ADDRESS, void *(*)(void *, const struct DlpFile *, u32, const struct DlpInfo *, void (*)(u32, u32, u32)))
#define SERVICE_INFO FN(DLP_SET_INFO_ADDRESS, void (*)(const struct DlpInfo *))
#define SERVICE_CONNECT FN(DLP_CONNECT_ADDRESS, void (*)(u32))
#define SERVICE_DISCONNECT FN(DLP_DISCONNECT_ADDRESS, void (*)(u32))
#define SERVICE_REQUEST FN(DLP_REQUEST_ADDRESS, void (*)(u32, u32, const void *, u32))
#define SERVICE_UPDATE FN(DLP_UPDATE_ADDRESS, void (*)(void))
#define SERVICE_FINISH FN(DLP_FINISH_ADDRESS, void (*)(u32))
#define SERVICE_STOP FN(DLP_STOP_ADDRESS, int (*)(void))

struct RelayState
{
  void *heap;
  void *service;
  u32 active;
  u32 failed;
  u32 started;
  u32 ready;
  u32 completed;
  u32 disconnected;
  u32 released;
  u32 selected;
  u32 frame;
  u8 original_mac[8][6];
  u8 current_mac[16][6];
  u8 original_aid[16];
  u32 original_ggid;
};
struct RelayState relay_state;
static const struct DlpFile files[] = {
    {"demomenu", "/ds_demo/demomenu"},
    {"rom0000d", "/ds_demo/rom0000d"},
};
static struct DlpInfo info = {{0, 1, 1}};

static void zero(void *p, u32 size)
{
  u8 *d = p;
  while (size--)
    *d++ = 0;
}

static void copy(void *p, const void *q, u32 size)
{
  u8 *d = p;
  const u8 *s = q;
  while (size--)
    *d++ = *s++;
}

static int same(const void *p, const void *q, u32 size)
{
  const u8 *a = p, *b = q;
  while (size--)
    if (*a++ != *b++)
      return 0;
  return 1;
}

static void service_notify(u32 aid, u32 event, u32 file)
{
  u32 original = relay_state.original_aid[aid];
  (void)file;
  if (!original)
    return;
  if (event == DLP_STARTED || event == DLP_READY)
    relay_state.failed &= ~(1u << original);
  if (event == DLP_STARTED)
  {
    relay_state.ready &= ~(1u << original);
    relay_state.completed &= ~(1u << original);
  }
  if (event == DLP_READY)
    relay_state.ready |= 1u << original;
  else if (event == DLP_FINISHED)
    relay_state.completed |= 1u << original;
  else if (event == DLP_FAILED)
  {
    relay_state.failed |= 1u << original;
    relay_state.ready &= ~(1u << original);
  }
}

static void port(u32 number, void *cb)
{
  u32 aid = HALF(cb, 0x12), state = HALF(cb, 4);
  if (aid > 0 && aid < 16 && state == 7)
    copy(relay_state.current_mac[aid], (u8 *)cb + 0x14, 6);
  if (relay_state.service && !relay_state.released && aid > 0 && aid < 16 && relay_state.original_aid[aid] &&
      HALF(cb, 2) == 0 && state == 0x15)
  {
    if (number == 12)
      relay_state.selected = 1;
    SERVICE_REQUEST(number, aid, (void *)WORD(cb, 0xc), HALF(cb, 0x10));
  }
}

static void port12(void *cb)
{
  port(12, cb);
}
static void port13(void *cb)
{
  port(13, cb);
}
static void port14(void *cb)
{
  port(14, cb);
}
static void port15(void *cb)
{
  port(15, cb);
}

void relay_parent_callback(u32 aid, u32 event, void *arg)
{
  u32 i;
  if (!relay_state.active)
  {
    NATIVE_CALLBACK(aid, event, arg);
    return;
  }
  if (event == 12)
  {
    NATIVE_GGID = relay_state.original_ggid;
    WM_PORT(12, 0, 0);
    WM_PORT(13, 0, 0);
    WM_PORT(14, 0, 0);
    /* Port 15 carries the game's original post-download file-ready barrier. */
    WM_PORT(15, FN(0x02050828, void (*)(void *)), 0);
    relay_state.released = 3;
    if (SERVICE_STOP())
    {
      NATIVE_CALLBACK(aid, event, arg);
      zero(&relay_state, sizeof(relay_state));
    }
    return;
  }
  if (aid > 0 && aid < 16)
  {
    /* MB forwards WMStartParentCallback before any port connection notification. */
    if (event == 2 && arg && HALF(arg, 2) == 0 && HALF(arg, 8) == 7 && HALF(arg, 0x10) == aid)
    {
      copy(relay_state.current_mac[aid], (u8 *)arg + 0xa, 6);
      relay_state.original_aid[aid] = 0;
      for (i = 1; i < 8; i++)
        if ((relay_state.started & (1u << i)) && same(relay_state.original_mac[i], relay_state.current_mac[aid], 6))
          return;
    }
    u32 original = relay_state.original_aid[aid];
    if (event == 9 && aid < 8)
    {
      relay_state.started |= 1u << aid;
      copy(relay_state.original_mac[aid], relay_state.current_mac[aid], 6);
    }
    if (event == 10)
    {
      const u8 *user = MB_USER(aid);
      if (user && (user[0] & 15) == 1 && user[1] == 10)
      {
        for (i = 0; i < 10; i++)
          if (HALF(user, 2 + i * 2) != 0x20)
            break;
        if (i == 10)
        {
          for (i = 1; i < 8; i++)
            if ((relay_state.started & (1u << i)) && same(relay_state.original_mac[i], relay_state.current_mac[aid], 6))
              break;
          if (i == 8 || relay_state.released || (relay_state.completed & (1u << i)))
          {
            MB_RESPONSE(aid, 0);
            return;
          }
          relay_state.original_aid[aid] = i;
          SERVICE_CONNECT(aid);
          MB_RESPONSE(aid, 1);
          return;
        }
      }
    }
    if (original)
    {
      if (event == 3)
      {
        SERVICE_DISCONNECT(aid);
        if (relay_state.completed & (1u << original))
          relay_state.disconnected |= 1u << original;
        else
        {
          relay_state.ready &= ~(1u << original);
          relay_state.failed |= 1u << original;
        }
      }
      /* A Station menu is a service client; do not download the menu again. */
      return;
    }
    /* MKDS indexes its eight-entry event table with the original AID only. */
    if (aid >= 8)
    {
      if (event == 10)
        MB_RESPONSE(aid, 0);
      return;
    }
    if (event == 3 && (relay_state.started & (1u << aid)))
      return;
  }
  NATIVE_CALLBACK(aid, event, arg);
}

int relay_mb_init(void *work, const void *user, u32 ggid, u32 tgid, u32 dma)
{
  zero(&relay_state, sizeof(relay_state));
  relay_state.original_ggid = NATIVE_GGID;
  /* WLMenu owns this child heap after initialization partitions its parent. */
  relay_state.heap = (void *)WORD(SCENE_WORK, 0x808);
  relay_state.active = 1;
  (void)ggid;
  return FN(0x02009ff5, int (*)(void *, const void *, u32, u32, u32))(work, user, 0x400120, tgid, dma);
}

u32 relay_segment_size(void *unused)
{
  FSFile file;
  u32 size = 0;
  (void)unused;
  FS_InitFile(&file);
  if (FS_OpenFile(&file, "/ds_demo/stage1.srl"))
  {
    size = FN(0x02008881, u32 (*)(void *))(&file);
    FS_CloseFile(&file);
  }
  /* The original MB cache/worker streams the remainder from the ROM archive. */
  return size > 0x20000 ? 0x20000 : size;
}

int relay_register(void)
{
  FSFile file;
  int result = 0;
  /* Keep the Station group only until the original clone-boot parent resumes. */
  NATIVE_GGID = 0x400120;
  FS_InitFile(&file);
  relay_state.service = SERVICE_INIT(relay_state.heap, files, sizeof(files) / sizeof(files[0]), &info, service_notify);
  if (relay_state.service && FS_OpenFile(&file, "/ds_demo/stage1.srl"))
  {
    u32 capacity = WORD(NATIVE_WORK, 0x168c);
    void *buffer = (void *)WORD(NATIVE_WORK, 0x1658);
    u32 required = FN(0x02008881, u32 (*)(void *))(&file);
    if (required && buffer && capacity >= 0x10000 &&
        FN(0x02008571, int (*)(void *, void *, u32))(&file, buffer, capacity))
      result = FN(0x02008311, int (*)(const void *, const void *))((void *)0x02154850, buffer);
    FS_CloseFile(&file);
  }
  if (!result)
  {
    NATIVE_GGID = relay_state.original_ggid;
    SERVICE_STOP();
    relay_state.service = 0;
    relay_state.failed = 1;
    return 0;
  }
  WM_PORT(12, port12, 0);
  WM_PORT(13, port13, 0);
  WM_PORT(14, port14, 0);
  WM_PORT(15, port15, 0);
  return 1;
}

void relay_scene_update(void *work)
{
  u32 aid, expected, mask = 0;
  /* End callbacks must not free the host heap while an async read still owns it. */
  if (relay_state.released == 3 && SERVICE_STOP())
  {
    NATIVE_CALLBACK(0, 12, 0);
    zero(&relay_state, sizeof(relay_state));
  }
  if (relay_state.active && relay_state.service && !relay_state.released)
  {
    if (relay_state.selected)
    {
      /* The original Station information contains RTCDate, RTCTime and OSOwnerInfo. */
      relay_state.selected = 0;
      RTC_GetDate(info.data);
      RTC_GetTime(info.data + 4);
      OS_GetOwnerInfo(info.data + 7);
      SERVICE_INFO(&info);
    }
    SERVICE_UPDATE();
    expected = BYTE(NATIVE_WORK, 0x1696);
    if (relay_state.failed & expected)
    {
      /* A retry may clear the affected slot; otherwise use the native error exit. */
      if (++relay_state.frame > 240)
      {
        relay_state.released = 2;
        NATIVE_ERROR(7);
      }
    }
    else
      relay_state.frame = 0;
    if (!relay_state.failed && expected && (relay_state.ready & expected) == expected)
    {
      for (aid = 1; aid < 16; aid++)
        if (relay_state.original_aid[aid] && (expected & (1u << relay_state.original_aid[aid])))
          mask |= 1u << aid;
      SERVICE_FINISH(mask);
    }
    if (expected && (relay_state.disconnected & expected) == expected)
    {
      NATIVE_GGID = relay_state.original_ggid;
      relay_state.released = 1;
      for (aid = 1; aid < 8; aid++)
        if (expected & (1u << aid))
          NATIVE_CALLBACK(aid, 3, 0);
    }
  }
  NATIVE_SCENE_UPDATE(work);
}
