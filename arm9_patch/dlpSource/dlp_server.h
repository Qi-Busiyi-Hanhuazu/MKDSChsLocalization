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

enum
{
  DLP_PROGRESS_IDLE,
  DLP_PROGRESS_QUEUED,
  DLP_PROGRESS_READING,
  DLP_PROGRESS_SENDING,
  DLP_PROGRESS_READY,
  DLP_PROGRESS_FINISHED,
  DLP_PROGRESS_FAILED
};

struct DlpProgress
{
  u32 state;
  u32 file;
  u32 received;
  u32 size;
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

/* The host supplies the menu and one or more programs; paths remain valid until stop.
   The port-12 information is copied unchanged during initialization.
   Notifications identify the requesting AID, event and index in this file table
   (0xffff for an unavailable size query). */
void *dlp_init(void *heap, const struct DlpFile *files, u32 count, const struct DlpInfo *info, void (*notify)(u32, u32, u32));
/* Update the host snapshot without modifying a metadata packet still in flight. */
void dlp_set_info(const struct DlpInfo *info);
/* Read the current program without changing its scheduling; received counts
   acknowledged, distinct data bytes. File is 0xffff before a program request.
   Returns zero for an unavailable connection or output pointer. */
int dlp_get_progress(u32 aid, struct DlpProgress *progress);
void dlp_request(u32 port, u32 aid, const void *data, u32 size);
void dlp_connect(u32 aid);
void dlp_disconnect(u32 aid);
/* Completion policy belongs to the host: release one receiver or a whole group. */
void dlp_finish(u32 mask);
void dlp_update(void);
/* Nonblocking: returns zero until file I/O and send callbacks have finished. Keep polling
   before releasing the host heap or starting another service. */
int dlp_stop(void);

#endif
