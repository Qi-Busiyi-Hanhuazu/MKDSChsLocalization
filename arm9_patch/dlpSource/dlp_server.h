#ifndef DLP_SERVER_H
#define DLP_SERVER_H

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

enum
{
  DLP_READY,
  DLP_FINISHED,
  DLP_FAILED,
  DLP_STARTED
};

struct DlpFile
{
  char name[8];
  const char *path;
};

struct DlpInfo
{
  u32 data[27];
};

void *dlp_init(void *heap, const struct DlpFile *files, u32 count, const struct DlpInfo *info, void (*notify)(u32, u32, u32));
/* Update the host snapshot without modifying a metadata packet still in flight. */
void dlp_set_info(const struct DlpInfo *info);
void dlp_request(u32 port, u32 aid, const void *data, u32 size);
void dlp_connect(u32 aid);
void dlp_disconnect(u32 aid);
void dlp_finish(u32 mask);
void dlp_update(void);
/* Nonblocking: returns zero until file I/O and send callbacks have finished. Keep polling
   before releasing the host heap or starting another service. */
int dlp_stop(void);

#endif
