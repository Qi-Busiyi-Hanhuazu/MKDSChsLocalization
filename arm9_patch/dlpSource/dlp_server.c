#include "dlp_server.h"
#include "../hosts/mkds.h"

#define WORD(p, off) (*(u32 *)((u8 *)(p) + (off)))
#define HALF(p, off) (*(u16 *)((u8 *)(p) + (off)))

/* Both buffers contain complete 126-byte game blocks and remain 32-byte aligned. */
#define CACHE_SIZE 2016
#define RETRIES 240

struct Receiver
{
  u8 *received;
  u32 bytes;
  u32 generation;
  u16 attempts[3];
};

struct Transfer
{
  FSFile file;
  u32 aid;
  u32 port;
  u32 resource;
  u32 size;
  u32 position;
  u32 block;
  u32 loaded;
  u32 reading;
  u32 writer;
  u32 reader;
  u32 used;
  u32 length;
  u32 attempts;
  u32 opened;
  u32 destination;
  u32 generation[16];
  volatile u32 available[2];
  volatile u32 busy;
  volatile u32 done;
  volatile u32 cancelled;
  volatile u32 failed;
  u8 packet[128] __attribute__((aligned(32)));
  u8 cache[2][CACHE_SIZE] __attribute__((aligned(32)));
};

struct Reply
{
  u32 aid;
  u32 size;
  u32 file;
  u32 generation;
  u32 attempts;
  volatile u32 busy;
  u8 packet[128] __attribute__((aligned(32)));
};

struct Server
{
  void *heap;
  void (*notify)(u32, u32, u32);
  u32 connected;
  u32 ready;
  u32 finished;
  u32 allowed;
  u32 pending[4];
  u32 order[4][16];
  u32 reset;
  u32 failed;
  u32 serial;
  u32 interrupts;
  u32 file_count;
  u16 requested[3][16];
  u16 program[16];
  u16 failure_file[16];
  struct Receiver receivers[16];
  volatile u32 sending;
  volatile u32 status_busy;
  volatile u32 status_dirty;
  volatile u32 terminal_busy;
  u32 terminal_mask;
  u32 terminal_generation;
  u32 status_mask;
  u32 status_sent;
  u32 status_generation[16];
  struct DlpInfo info;
  struct Reply replies[2];
  struct Transfer transfers[2];
  u16 status[16] __attribute__((aligned(32)));
  struct
  {
    struct DlpFile file;
    u32 size;
  } files[];
};

static struct Server *server;
static volatile u32 updating, stopping;
static const u16 terminal[16] __attribute__((aligned(32))) = {0xffff};

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

/* Publish shared state with IRQ disabled; SDK file/heap calls may yield. */
static void unlock(void)
{
  OS_RestoreInterrupts(server->interrupts);
}

static void lock(void)
{
  OS_DisableInterrupts();
}

static u32 first(u32 mask)
{
  u32 aid;
  for (aid = 1; aid < 16; aid++)
    if (mask & (1u << aid))
      return aid;
  return 0;
}

static u32 oldest(u32 mask, u32 port)
{
  u32 aid = 0;
  while (mask)
  {
    u32 next = first(mask);
    mask &= ~(1u << next);
    if (!aid || (int)(server->order[port][next] - server->order[port][aid]) < 0)
      aid = next;
  }
  return aid;
}

static int received(u32 aid, u32 block)
{
  return server->receivers[aid].received[block >> 3] & (1u << (block & 7));
}

static void fail(u32 aid, u32 file)
{
  u32 i, mask = 1u << aid;
  if (!(server->connected & mask) || (server->failed & mask))
    return;
  server->failure_file[aid] = file;
  server->failed |= mask;
  server->reset |= mask;
  server->ready &= ~mask;
  server->allowed &= ~mask;
  server->receivers[aid].generation++;
  for (i = 0; i < 4; i++)
    server->pending[i] &= ~mask;
  for (i = 0; i < 2; i++)
    if (server->transfers[i].aid == aid)
      server->transfers[i].cancelled = 1;
  server->status_mask &= ~mask;
  server->status_dirty = 1;
}

static void ready(u32 aid)
{
  u32 mask = 1u << aid;
  server->pending[3] &= ~mask;
  server->ready |= mask;
  server->status_dirty = 1;
  server->notify(aid, DLP_READY, server->program[aid]);
}

static void update_receivers(void)
{
  u32 aid;
  for (aid = 1; aid < 16; aid++)
  {
    u32 mask = 1u << aid;
    struct Receiver *r = &server->receivers[aid];
    if ((server->reset & mask) || !(server->pending[3] & mask))
    {
      u8 *old = r->received;
      r->received = 0;
      if (old)
      {
        unlock();
        NNS_FndFreeToExpHeap(server->heap, old);
        lock();
      }
    }
    if (server->reset & mask)
    {
      server->reset &= ~mask;
      r->bytes = 0;
      zero(r->attempts, sizeof(r->attempts));
    }
    if (server->failed & mask)
    {
      server->failed &= ~mask;
      server->notify(aid, DLP_FAILED, server->failure_file[aid]);
    }
    if ((server->pending[3] & mask) && !r->received)
    {
      u32 size = server->files[server->program[aid]].size;
      u32 generation = r->generation;
      u32 blocks = 0;
      for (; size; blocks++)
        size = size > 126 ? size - 126 : 0;
      u8 *map;
      unlock();
      map = NNS_FndAllocFromExpHeapEx(server->heap, (blocks + 7) >> 3, 4);
      if (map)
        zero(map, (blocks + 7) >> 3);
      lock();
      if (generation != r->generation || !(server->pending[3] & mask) || (server->reset & mask) || stopping)
      {
        if (map)
        {
          unlock();
          NNS_FndFreeToExpHeap(server->heap, map);
          lock();
        }
      }
      else if (!map)
        fail(aid, server->program[aid]);
      else
        r->received = map;
    }
  }
}

static void send_done(void *cb)
{
  (void)cb;
  server->sending--;
}

static void reply_done(u32 index, void *cb)
{
  struct Reply *r = &server->replies[index];
  if (r->generation == server->receivers[r->aid].generation)
  {
    if (HALF(cb, 2) == 0)
    {
      if (!index || server->requested[0][r->aid] == r->file)
        server->pending[index] &= ~(1u << r->aid);
      r->attempts = 0;
    }
    else
      r->attempts++;
  }
  r->busy = 0;
}

static void metadata_done(void *cb)
{
  reply_done(0, cb);
  send_done(cb);
}

static void size_done(void *cb)
{
  reply_done(1, cb);
  send_done(cb);
}

static void status_done(void *cb)
{
  u32 mask = server->status_sent;
  u32 missing = HALF(cb, 2) == 0 ? 0 : mask;
  if (HALF(cb, 2) == 15)
    missing &= HALF(cb, 0xe);
  while (mask)
  {
    u32 aid = first(mask), bit = 1u << aid;
    struct Receiver *r = &server->receivers[aid];
    mask &= ~bit;
    if (server->status_generation[aid] != r->generation || !(server->connected & bit))
      server->status_mask &= ~bit;
    else if (!(missing & bit))
    {
      server->status_mask &= ~bit;
      r->attempts[1] = 0;
    }
    else if (++r->attempts[1] > RETRIES)
      fail(aid, server->program[aid]);
  }
  server->status_busy = 0;
  send_done(cb);
}

static void terminal_done(void *cb)
{
  u32 mask = server->terminal_mask & server->connected & server->ready;
  u32 aid = first(server->terminal_mask);
  if (server->terminal_generation != server->receivers[aid].generation)
    mask = 0;
  if (mask && HALF(cb, 2) == 0)
  {
    server->finished |= mask;
    while (mask)
    {
      u32 aid = first(mask);
      mask &= ~(1u << aid);
      server->notify(aid, DLP_FINISHED, server->program[aid]);
    }
  }
  else if (mask && ++server->receivers[aid].attempts[2] > RETRIES)
    fail(aid, server->program[aid]);
  server->terminal_busy = 0;
  send_done(cb);
}

static void send_block(struct Transfer *t);

static void block_done(u32 index, void *cb)
{
  struct Transfer *t = &server->transfers[index];
  t->busy = 0;
  if (t->failed)
    return;
  if (index)
  {
    u32 mask = t->destination;
    u32 acknowledged = HALF(cb, 0x10);
    if (HALF(cb, 2) == 15)
      acknowledged &= ~HALF(cb, 0xe);
    else if (HALF(cb, 2) != 0)
      acknowledged = 0;
    while (mask)
    {
      u32 aid = first(mask), bit = 1u << aid;
      struct Receiver *r = &server->receivers[aid];
      mask &= ~bit;
      if (t->generation[aid] != r->generation || !(server->pending[3] & bit))
        continue;
      if (acknowledged & bit)
      {
        r->attempts[0] = 0;
        if (!received(aid, t->block))
        {
          r->received[t->block >> 3] |= 1u << (t->block & 7);
          r->bytes += t->length - 2;
          if (r->bytes == t->size)
            ready(aid);
        }
      }
      else if (++r->attempts[0] > RETRIES)
        fail(aid, t->resource);
    }
  }
  else if (t->cancelled || t->generation[t->aid] != server->receivers[t->aid].generation)
    return;
  else if (HALF(cb, 2) != 0)
  {
    t->attempts++;
    return;
  }
  t->attempts = 0;
  if (t->length == 2)
  {
    t->done = 1;
    return;
  }
  t->position += t->length - 2;
  t->block++;
  t->used += t->length - 2;
  if (t->used == t->available[t->reader])
  {
    t->available[t->reader] = 0;
    t->reader ^= 1;
    t->used = 0;
  }
  send_block(t);
}

static void menu_done(void *cb)
{
  block_done(0, cb);
  send_done(cb);
}

static void program_done(void *cb)
{
  block_done(1, cb);
  send_done(cb);
}

static void send_block(struct Transfer *t)
{
  u32 mask, aid;
  u32 capacity = t->port == 14 ? 30 : 126;
  void (*callback)(void *) = t->port == 14 ? menu_done : program_done;
  if (stopping || !t->aid || t->busy || t->cancelled || t->failed || t->done)
    return;
  if (t->port == 15 && (!(server->pending[3] & (1u << t->aid)) ||
      server->program[t->aid] != t->resource))
    return;
  if (t->position == t->size)
  {
    if (t->port == 15)
    {
      t->done = 1;
      return;
    }
    HALF(t->packet, 0) = 0xffff;
    t->length = 2;
  }
  else
  {
    u32 count = t->available[t->reader] - t->used;
    if (!count)
      return;
    if (count > capacity)
      count = capacity;
    /* Menu blocks also span cache boundaries; only publish complete blocks. */
    if (count < capacity && t->position + count != t->size)
      return;
    HALF(t->packet, 0) = t->block;
    copy(t->packet + 2, t->cache[t->reader] + t->used, count);
    t->length = count + 2;
  }
  t->destination = 1u << t->aid;
  if (t->port == 15)
  {
    if (received(t->aid, t->block))
      return;
    t->destination = 0;
    mask = server->pending[3] & server->connected & ~server->reset;
    while (mask)
    {
      aid = first(mask);
      mask &= ~(1u << aid);
      if (server->program[aid] == t->resource && server->receivers[aid].received && !received(aid, t->block))
        t->destination |= 1u << aid;
    }
  }
  mask = t->destination;
  while (mask)
  {
    aid = first(mask);
    mask &= ~(1u << aid);
    t->generation[aid] = server->receivers[aid].generation;
  }
  t->busy = 1;
  server->sending++;
  if (WM_SetMPDataToPortEx(callback, 0, t->packet, t->length, t->destination, t->port, 3) != 2)
  {
    server->sending--;
    t->busy = 0;
    t->attempts++;
    if (t->port == 15)
    {
      mask = t->destination;
      while (mask)
      {
        aid = first(mask);
        mask &= ~(1u << aid);
        if (++server->receivers[aid].attempts[0] > RETRIES)
          fail(aid, t->resource);
      }
    }
  }
}

static void update_read(struct Transfer *t)
{
  if (t->reading && !FS_IsBusy(&t->file))
  {
    u32 count = t->reading;
    t->reading = 0;
    if (stopping || t->cancelled || t->failed)
      return;
    if (FS_GetResultCode(&t->file) || FS_TellFile(&t->file) != t->loaded + count)
      t->failed = 1;
    else
    {
      t->loaded += count;
      __asm__ volatile("" ::: "memory");
      t->available[t->writer] = count;
      t->writer ^= 1;
    }
  }
}

static void update_transfer(u32 index)
{
  struct Transfer *t = &server->transfers[index];
  u32 aid, mask;
  if (index && t->aid && (!(server->pending[3] & (1u << t->aid)) || server->program[t->aid] != t->resource))
    t->cancelled = 1;
  update_read(t);
  if (t->aid && !t->busy && (t->done || t->cancelled || t->failed || t->attempts > RETRIES))
  {
    if (t->reading && FS_IsBusy(&t->file))
    {
      FS_CancelFile(&t->file);
      return;
    }
    aid = t->aid;
    if (t->opened)
    {
      unlock();
      FS_CloseFile(&t->file);
      lock();
    }
    if (index && t->failed)
    {
      mask = server->pending[3];
      while (mask)
      {
        u32 next = first(mask);
        mask &= ~(1u << next);
        if (server->program[next] == t->resource)
          fail(next, t->resource);
      }
    }
    else if (!index && !t->done && !t->cancelled)
      fail(aid, t->resource);
    zero(t, sizeof(*t));
    server->status_dirty = 1;
  }
  if (!t->aid)
  {
    mask = server->pending[index + 2] & server->connected & ~server->reset;
    aid = oldest(mask, index + 2);
    if (!aid)
      return;
    if (!index)
      server->pending[2] &= ~(1u << aid);
    t->aid = aid;
    t->port = index + 14;
    t->resource = server->requested[index + 1][aid];
    unlock();
    FS_InitFile(&t->file);
    t->opened = FS_OpenFile(&t->file, server->files[t->resource].file.path);
    lock();
    if (!t->opened)
    {
      t->failed = 1;
      return;
    }
    t->size = server->files[t->resource].size;
    server->status_dirty = 1;
  }
  if (index && !t->busy && t->position < t->size && received(t->aid, t->block))
  {
    if (t->reading)
      return;
    while (t->block * 126 < t->size && received(t->aid, t->block))
      t->block++;
    t->position = t->block * 126;
    if (t->position > t->size)
      t->position = t->size;
    t->loaded = t->position;
    t->writer = t->reader = t->used = 0;
    t->available[0] = t->available[1] = 0;
    unlock();
    int result = FS_SeekFile(&t->file, t->position, 0);
    lock();
    if (!result)
    {
      t->failed = 1;
      return;
    }
  }
  while (!stopping && !t->cancelled && !t->failed && !t->reading && t->loaded < t->size && !t->available[t->writer])
  {
    u32 bank = t->writer;
    u32 count = t->size - t->loaded;
    /* Use a multiple of both block sizes (30 and 126). */
    u32 capacity = index ? CACHE_SIZE : 1890;
    if (count > capacity)
      count = capacity;
    t->reading = count;
    unlock();
    int result = FS_ReadFileAsync(&t->file, t->cache[bank], count);
    lock();
    if (result != (int)count)
    {
      t->failed = 1;
      return;
    }
    update_read(t);
  }
  send_block(t);
}

void *dlp_init(void *heap, const struct DlpFile *files, u32 count, const struct DlpInfo *info, void (*notify)(u32, u32, u32))
{
  u32 i;
  FSFile file;
  if (updating || !dlp_stop())
    return 0;
  server = NNS_FndAllocFromExpHeapEx(heap, sizeof(*server) + count * sizeof(server->files[0]), 32);
  if (!server)
    return 0;
  zero(server, sizeof(*server));
  server->heap = heap;
  server->notify = notify;
  server->file_count = count;
  for (i = 0; i < 16; i++)
    server->program[i] = 0xffff;
  for (i = 0; i < count; i++)
  {
    server->files[i].file = files[i];
    FS_InitFile(&file);
    if (!FS_OpenFile(&file, files[i].path))
    {
      dlp_stop();
      return 0;
    }
    server->files[i].size = FS_GetLength(&file);
    FS_CloseFile(&file);
  }
  dlp_set_info(info);
  server->replies[0].size = sizeof(*info);
  server->replies[1].size = 4;
  return server;
}

void dlp_set_info(const struct DlpInfo *info)
{
  u32 interrupts = OS_DisableInterrupts();
  if (server)
    copy(&server->info, info, sizeof(*info));
  OS_RestoreInterrupts(interrupts);
}

void dlp_connect(u32 aid)
{
  if (server)
  {
    dlp_disconnect(aid);
    server->connected |= 1u << aid;
  }
}

void dlp_request(u32 port, u32 aid, const void *data, u32 size)
{
  const u8 *name = data;
  u32 i, file = 0;
  if (!server || stopping || !(server->connected & (1u << aid)))
    return;
  if (port != 12)
  {
    if (size < 8 || !data)
      return;
    for (file = 0; file < server->file_count; file++)
    {
      for (i = 0; i < 8 && name[i] == (u8)server->files[file].file.name[i]; i++)
        ;
      if (i == 8)
        break;
    }
    if (file == server->file_count)
    {
      if (port != 13)
        return;
      file = 0xffff;
    }
  }
  if (port >= 14 && ((server->transfers[port - 14].aid == aid && !server->transfers[port - 14].cancelled) ||
      (server->ready & (1u << aid))))
  {
    if (port == 14 || server->program[aid] == file)
      return;
  }
  if (port == 15 && (server->pending[3] & (1u << aid)) && server->program[aid] == file)
    return;
  if (!(server->pending[port - 12] & (1u << aid)) ||
      (port >= 13 && server->requested[port - 13][aid] != file))
    server->order[port - 12][aid] = ++server->serial;
  if (port >= 13)
    server->requested[port - 13][aid] = file;
  server->pending[port - 12] |= 1u << aid;
  if (port == 15)
  {
    server->program[aid] = file;
    server->receivers[aid].bytes = 0;
    server->ready &= ~(1u << aid);
    server->finished &= ~(1u << aid);
    server->allowed &= ~(1u << aid);
    server->reset |= 1u << aid;
    server->failed &= ~(1u << aid);
    server->receivers[aid].generation++;
    server->status_dirty = 1;
    server->notify(aid, DLP_STARTED, file);
  }
}

void dlp_disconnect(u32 aid)
{
  u32 i, mask;
  if (!server)
    return;
  mask = 1u << aid;
  server->connected &= ~mask;
  server->ready &= ~mask;
  server->finished &= ~mask;
  server->allowed &= ~mask;
  server->failed &= ~mask;
  server->reset |= mask;
  server->status_mask &= ~mask;
  server->receivers[aid].generation++;
  server->receivers[aid].bytes = 0;
  server->program[aid] = 0xffff;
  for (i = 0; i < 4; i++)
    server->pending[i] &= ~mask;
  for (i = 0; i < 2; i++)
    if (server->transfers[i].aid == aid)
      server->transfers[i].cancelled = 1;
  server->status_dirty = 1;
}

void dlp_finish(u32 mask)
{
  u32 interrupts = OS_DisableInterrupts();
  if (server)
    server->allowed |= mask & server->ready & server->connected;
  OS_RestoreInterrupts(interrupts);
}

void dlp_update(void)
{
  u32 i, mask;
  u32 interrupts = OS_DisableInterrupts();
  if (!server)
  {
    OS_RestoreInterrupts(interrupts);
    return;
  }
  updating = 1;
  server->interrupts = interrupts;
  update_receivers();
  for (i = 0; i < 2; i++)
  {
    if (stopping)
      break;
    struct Reply *r = &server->replies[i];
    if (!r->busy)
    {
      u32 aid = oldest(server->pending[i] & server->connected, i);
      if (aid != r->aid || r->generation != server->receivers[aid].generation ||
          (i && aid && r->file != server->requested[0][aid]))
        r->attempts = 0;
      r->aid = aid;
      if (r->aid)
      {
        if (r->attempts > RETRIES)
        {
          fail(r->aid, r->file);
          continue;
        }
        if (i)
        {
          r->file = server->requested[0][r->aid];
          WORD(r->packet, 0) = r->file < server->file_count ? server->files[r->file].size : 0;
        }
        else
          copy(r->packet, &server->info, sizeof(server->info));
        r->busy = 1;
        r->generation = server->receivers[r->aid].generation;
        server->sending++;
        if (WM_SetMPDataToPortEx(i ? size_done : metadata_done, 0, r->packet, r->size, 1u << r->aid, i + 12, 3) != 2)
        {
          server->sending--;
          r->busy = 0;
          r->attempts++;
        }
      }
    }
    update_transfer(i);
  }
  if (stopping)
    goto end;
  if (server->status_dirty && !server->status_busy)
  {
    u32 rank = 0;
    u32 destination = server->pending[3] & server->connected;
    mask = destination;
    zero(server->status, sizeof(server->status));
    server->status[0] = 0xfffe;
    while (mask)
    {
      u32 next = oldest(mask, 3);
      server->status[next] = rank++;
      mask &= ~(1u << next);
    }
    server->status_dirty = 0;
    server->status_mask = destination;
  }
  if (server->status_mask && !server->status_busy)
  {
    mask = server->status_mask & server->connected;
    server->status_sent = mask;
    while (mask)
    {
      u32 aid = first(mask);
      mask &= ~(1u << aid);
      server->status_generation[aid] = server->receivers[aid].generation;
    }
    server->status_busy = 1;
    server->sending++;
    if (WM_SetMPDataToPortEx(status_done, 0, server->status, 32, server->status_sent, 15, 3) != 2)
    {
      /* Feed an immediate WM error through the same per-receiver accounting. */
      u16 error[9];
      zero(error, sizeof(error));
      error[1] = 1;
      status_done(error);
    }
  }
  mask = server->allowed & server->ready & server->connected & ~server->finished;
  if (mask && !server->terminal_busy)
  {
    /* Acknowledge each receiver separately before permitting its disconnect. */
    mask = 1u << first(mask);
    server->terminal_mask = mask;
    server->terminal_generation = server->receivers[first(mask)].generation;
    server->terminal_busy = 1;
    server->sending++;
    if (WM_SetMPDataToPortEx(terminal_done, 0, terminal, 2, mask, 15, 3) != 2)
    {
      u16 error[9];
      zero(error, sizeof(error));
      error[1] = 1;
      terminal_done(error);
    }
  }
  update_receivers();
end:
  unlock();
  updating = 0;
  if (stopping)
    dlp_stop();
}

int dlp_stop(void)
{
  u32 interrupts = OS_DisableInterrupts();
  struct Server *old;
  stopping = 1;
  if (updating)
  {
    OS_RestoreInterrupts(interrupts);
    return 0;
  }
  if (server)
  {
    u32 i, busy = server->sending;
    for (i = 0; i < 2; i++)
      if (server->transfers[i].opened && FS_IsBusy(&server->transfers[i].file))
      {
        FS_CancelFile(&server->transfers[i].file);
        busy = 1;
      }
    if (busy)
    {
      OS_RestoreInterrupts(interrupts);
      return 0;
    }
  }
  stopping = 0;
  old = server;
  server = 0;
  OS_RestoreInterrupts(interrupts);
  if (old)
  {
    u32 i;
    for (i = 0; i < 2; i++)
      if (old->transfers[i].opened)
        FS_CloseFile(&old->transfers[i].file);
    for (i = 1; i < 16; i++)
      if (old->receivers[i].received)
        NNS_FndFreeToExpHeap(old->heap, old->receivers[i].received);
    NNS_FndFreeToExpHeap(old->heap, old);
  }
  return 1;
}
