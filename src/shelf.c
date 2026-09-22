#include "shelf.h"

#include "kry_filesystem.h"

#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef KRYON_NATIVE_PLAN9
#include <strings.h>
#endif
#ifdef FILE_MANAGER_HAS_GDK_PIXBUF
#include <gdk-pixbuf/gdk-pixbuf.h>
#endif

static FileSortMode sort_mode;
static int sort_reverse;

typedef struct IconSet {
    Texture2D folder;
    Texture2D file;
    Texture2D home;
    Texture2D desktop;
    Texture2D documents;
    Texture2D downloads;
    Texture2D trash;
    Texture2D filesystem;
    int loaded;
} IconSet;

static IconSet icons;

static const char *
home_path(void)
{
    static char home[FILE_MANAGER_PATH_MAX];

    if(kry_fs_home_dir(home, sizeof(home)))
        return home;
    return "/";
}

static int
mod_down(void)
{
    return IsKeyDown(KEY_LEFT_CONTROL) || IsKeyDown(KEY_RIGHT_CONTROL) ||
           IsKeyDown(KEY_LEFT_SUPER) || IsKeyDown(KEY_RIGHT_SUPER);
}

static int
shift_down(void)
{
    return IsKeyDown(KEY_LEFT_SHIFT) || IsKeyDown(KEY_RIGHT_SHIFT);
}

static void
copy_text(char *dst, int size, const char *src)
{
    int i;

    if(dst == NULL || size <= 0)
        return;
    if(src == NULL)
        src = "";
    for(i = 0; i < size - 1 && src[i] != '\0'; i++)
        dst[i] = src[i];
    dst[i] = '\0';
}

static Color
opaque_color(Color color)
{
    color.a = 255;
    return color;
}

static int
same_text(const char *a, const char *b)
{
    return strcmp(a != NULL ? a : "", b != NULL ? b : "") == 0;
}

static int
contains_text_ci(const char *haystack, const char *needle)
{
    size_t needle_len;
    size_t i;

    if(haystack == NULL || needle == NULL)
        return 0;
    needle_len = strlen(needle);
    if(needle_len == 0)
        return 1;
    for(i = 0; haystack[i] != '\0'; i++)
        if(strncasecmp(haystack + i, needle, needle_len) == 0)
            return 1;
    return 0;
}

static void
set_error(FileManager *manager, const char *path)
{
#ifdef KRYON_NATIVE_PLAN9
    char err[ERRMAX];
#endif

    if(manager == NULL)
        return;
#ifdef KRYON_NATIVE_PLAN9
    errstr(err, sizeof(err));
    snprintf(manager->error, sizeof(manager->error), "%.160s: %.80s",
             path != NULL ? path : "", err);
#else
    snprintf(manager->error, sizeof(manager->error), "%.160s: %.80s",
             path != NULL ? path : "", strerror(errno));
#endif
}

static void
set_message(FileManager *manager, const char *message)
{
    if(manager != NULL)
        copy_text(manager->error, sizeof(manager->error), message);
}

static void
unique_child_path(char *out, int out_size, const char *dir, const char *name)
{
    char candidate[FILE_MANAGER_PATH_MAX];
    const char *dot;
    int i;

    kry_fs_join_path(candidate, sizeof(candidate), dir, name);
    if(!kry_fs_exists(candidate)) {
        copy_text(out, out_size, candidate);
        return;
    }

    dot = strrchr(name, '.');
    if(dot == name)
        dot = NULL;
    for(i = 1; i < 10000; i++) {
        char renamed[256];

        if(dot != NULL) {
            int stem_len = (int)(dot - name);
            snprintf(renamed, sizeof(renamed), "%.*s copy %d%s",
                     stem_len, name, i, dot);
        } else {
            snprintf(renamed, sizeof(renamed), "%s copy %d", name, i);
        }
        kry_fs_join_path(candidate, sizeof(candidate), dir, renamed);
        if(!kry_fs_exists(candidate)) {
            copy_text(out, out_size, candidate);
            return;
        }
    }
    copy_text(out, out_size, candidate);
}

static int
entry_compare(const void *a, const void *b)
{
    const FileEntry *ea = a;
    const FileEntry *eb = b;
    int result = 0;

    if(ea->is_dir != eb->is_dir)
        result = eb->is_dir - ea->is_dir;
    else if(sort_mode == FILE_SORT_SIZE && ea->size != eb->size)
        result = ea->size < eb->size ? -1 : 1;
    else if(sort_mode == FILE_SORT_MODIFIED && ea->modified != eb->modified)
        result = ea->modified < eb->modified ? -1 : 1;
    else if(sort_mode == FILE_SORT_TYPE) {
        const char *ae = strrchr(ea->name, '.');
        const char *be = strrchr(eb->name, '.');

        if(ae == NULL)
            ae = "";
        if(be == NULL)
            be = "";
        result = strcasecmp(ae, be);
    }
    if(result == 0)
        result = strcasecmp(ea->name, eb->name);
    if(sort_reverse && ea->is_dir == eb->is_dir)
        result = -result;
    return result;
}

static void
format_size(char *out, int out_size, unsigned long long size, int is_dir)
{
    if(is_dir) {
        copy_text(out, out_size, "Folder");
    } else if(size >= 1024ull * 1024ull * 1024ull) {
        snprintf(out, (size_t)out_size, "%llu GB",
                 size / (1024ull * 1024ull * 1024ull));
    } else if(size >= 1024ull * 1024ull) {
        snprintf(out, (size_t)out_size, "%llu MB", size / (1024ull * 1024ull));
    } else if(size >= 1024ull) {
        snprintf(out, (size_t)out_size, "%llu KB", size / 1024ull);
    } else {
        snprintf(out, (size_t)out_size, "%llu B", size);
    }
}

static void
format_modified(char *out, int out_size, time_t modified)
{
    struct tm *tm_info;

    if(modified <= 0) {
        copy_text(out, out_size, "");
        return;
    }
    tm_info = localtime(&modified);
    if(tm_info == NULL) {
        copy_text(out, out_size, "");
        return;
    }
    strftime(out, (size_t)out_size, "%Y-%m-%d %H:%M", tm_info);
}

static void
history_push(char paths[FILE_MANAGER_MAX_HISTORY][FILE_MANAGER_PATH_MAX],
             int *count, const char *path)
{
    int i;

    if(paths == NULL || count == NULL || path == NULL || path[0] == '\0')
        return;
    if(*count > 0 && same_text(paths[*count - 1], path))
        return;
    if(*count >= FILE_MANAGER_MAX_HISTORY) {
        for(i = 1; i < FILE_MANAGER_MAX_HISTORY; i++)
            copy_text(paths[i - 1], FILE_MANAGER_PATH_MAX, paths[i]);
        *count = FILE_MANAGER_MAX_HISTORY - 1;
    }
    copy_text(paths[*count], FILE_MANAGER_PATH_MAX, path);
    (*count)++;
}

static int
history_pop(char paths[FILE_MANAGER_MAX_HISTORY][FILE_MANAGER_PATH_MAX],
            int *count, char *out, int out_size)
{
    if(paths == NULL || count == NULL || *count <= 0)
        return 0;
    (*count)--;
    copy_text(out, out_size, paths[*count]);
    paths[*count][0] = '\0';
    return 1;
}

static void
clamp_cursor(FileManager *manager)
{
    if(manager->entry_count <= 0) {
        manager->cursor = -1;
        manager->anchor = -1;
        manager->scroll = 0;
        return;
    }
    if(manager->cursor < 0)
        manager->cursor = 0;
    if(manager->cursor >= manager->entry_count)
        manager->cursor = manager->entry_count - 1;
    if(manager->anchor < 0 || manager->anchor >= manager->entry_count)
        manager->anchor = manager->cursor;
}

static void
ensure_cursor_visible(FileManager *manager, int visible)
{
    if(manager->cursor < 0 || visible <= 0)
        return;
    if(manager->cursor < manager->scroll)
        manager->scroll = manager->cursor;
    if(manager->cursor >= manager->scroll + visible)
        manager->scroll = manager->cursor - visible + 1;
}

static void
sort_entries(FileManager *manager)
{
    sort_mode = manager->sort_mode;
    sort_reverse = manager->sort_reverse;
    qsort(manager->entries, (size_t)manager->entry_count,
          sizeof(manager->entries[0]), entry_compare);
}

static void
select_first_after_load(FileManager *manager)
{
    manager->cursor = manager->entry_count > 0 ? 0 : -1;
    manager->anchor = manager->cursor;
    manager->scroll = 0;
    if(manager->entry_count > 0)
        manager->entries[0].selected = 1;
    manager->last_click_index = -1;
}

static void
remember_active_tab(FileManager *manager)
{
    if(manager == NULL || manager->tab_count <= 0 ||
       manager->active_tab < 0 || manager->active_tab >= manager->tab_count)
        return;
    copy_text(manager->tabs[manager->active_tab].path,
              sizeof(manager->tabs[manager->active_tab].path), manager->cwd);
}

int
FileManagerOpenPath(FileManager *manager, const char *path)
{
    KryDirEntry dir_entries[FILE_MANAGER_MAX_ENTRIES];
    char resolved[FILE_MANAGER_PATH_MAX];
    int dir_count;
    int i;

    if(manager == NULL || path == NULL || path[0] == '\0')
        return 0;
    if(!kry_fs_realpath(path, resolved, sizeof(resolved))) {
        set_error(manager, path);
        return 0;
    }
    dir_count = kry_fs_list_dir_ex(resolved, dir_entries,
                                   FILE_MANAGER_MAX_ENTRIES,
                                   manager->show_hidden);
    if(dir_count == 0 && !kry_fs_exists(resolved)) {
        set_error(manager, resolved);
        return 0;
    }

    for(i = 0; i < dir_count; i++) {
        FileEntry *entry = &manager->entries[i];

        memset(entry, 0, sizeof(*entry));
        copy_text(entry->name, sizeof(entry->name), dir_entries[i].name);
        kry_fs_join_path(entry->path, sizeof(entry->path), resolved, dir_entries[i].name);
        entry->is_dir = dir_entries[i].is_dir;
        entry->size = dir_entries[i].size;
        entry->modified = (time_t)dir_entries[i].mtime;
        entry->readable = dir_entries[i].readable;
        entry->hidden = dir_entries[i].hidden;
    }
    copy_text(manager->cwd, sizeof(manager->cwd), resolved);
    remember_active_tab(manager);
    manager->entry_count = dir_count;
    manager->search_active = 0;
    manager->search_query[0] = '\0';
    manager->search_root[0] = '\0';
    sort_entries(manager);
    select_first_after_load(manager);
    manager->error[0] = '\0';
    return 1;
}

int
FileManagerOpenPathTracked(FileManager *manager, const char *path)
{
    char old[FILE_MANAGER_PATH_MAX];

    if(manager == NULL)
        return 0;
    copy_text(old, sizeof(old), manager->cwd);
    if(!FileManagerOpenPath(manager, path))
        return 0;
    if(old[0] != '\0' && !same_text(old, manager->cwd)) {
        history_push(manager->back, &manager->back_count, old);
        manager->forward_count = 0;
    }
    return 1;
}

static void
search_dir(FileManager *manager, const char *dir, const char *query,
           int depth, int *count)
{
    KryDirEntry dir_entries[FILE_MANAGER_MAX_ENTRIES];
    int dir_count;
    int i;

    if(manager == NULL || dir == NULL || query == NULL || count == NULL ||
       depth > 32 || *count >= FILE_MANAGER_MAX_ENTRIES)
        return;
    dir_count = kry_fs_list_dir_ex(dir, dir_entries, FILE_MANAGER_MAX_ENTRIES,
                                   manager->show_hidden);
    for(i = 0; i < dir_count && *count < FILE_MANAGER_MAX_ENTRIES; i++) {
        char path[FILE_MANAGER_PATH_MAX];
        KryDirEntry *dir_entry = &dir_entries[i];

        kry_fs_join_path(path, sizeof(path), dir, dir_entry->name);
        if(contains_text_ci(dir_entry->name, query)) {
            FileEntry *entry = &manager->entries[*count];

            memset(entry, 0, sizeof(*entry));
            copy_text(entry->name, sizeof(entry->name), dir_entry->name);
            copy_text(entry->path, sizeof(entry->path), path);
            entry->is_dir = dir_entry->is_dir;
            entry->size = dir_entry->size;
            entry->modified = (time_t)dir_entry->mtime;
            entry->readable = dir_entry->readable;
            entry->hidden = dir_entry->hidden;
            (*count)++;
        }
        if(dir_entry->is_dir)
            search_dir(manager, path, query, depth + 1, count);
    }
}

int
FileManagerSearch(FileManager *manager, const char *query)
{
    char root[FILE_MANAGER_PATH_MAX];
    int count = 0;

    if(manager == NULL || query == NULL || query[0] == '\0')
        return 0;
    copy_text(root, sizeof(root),
              manager->search_active && manager->search_root[0] != '\0' ?
                  manager->search_root : manager->cwd);
    memset(manager->entries, 0, sizeof(manager->entries));
    search_dir(manager, root, query, 0, &count);
    manager->entry_count = count;
    manager->search_active = 1;
    copy_text(manager->search_root, sizeof(manager->search_root), root);
    copy_text(manager->search_query, sizeof(manager->search_query), query);
    sort_entries(manager);
    select_first_after_load(manager);
    manager->error[0] = '\0';
    return 1;
}

static int
refresh_view(FileManager *manager)
{
    if(manager == NULL)
        return 0;
    if(manager->search_active && manager->search_query[0] != '\0')
        return FileManagerSearch(manager, manager->search_query);
    return FileManagerOpenPath(manager, manager->cwd);
}

void
FileManagerInit(FileManager *manager, const char *start_path)
{
    if(manager == NULL)
        return;
    memset(manager, 0, sizeof(*manager));
    manager->cursor = -1;
    manager->anchor = -1;
    manager->last_click_index = -1;
    manager->width = 640;
    manager->height = 420;
    manager->sort_mode = FILE_SORT_NAME;
    manager->tab_count = 1;
    manager->active_tab = 0;
    if(start_path == NULL || start_path[0] == '\0')
        start_path = home_path();
    if(!FileManagerOpenPath(manager, start_path))
        (void)FileManagerOpenPath(manager, "/");
}

int
FileManagerNewTab(FileManager *manager, const char *path)
{
    int old_active;
    char old_path[FILE_MANAGER_PATH_MAX];

    if(manager == NULL || manager->tab_count >= FILE_MANAGER_MAX_TABS)
        return 0;
    remember_active_tab(manager);
    old_active = manager->active_tab;
    copy_text(old_path, sizeof(old_path), manager->cwd);
    manager->active_tab = manager->tab_count;
    manager->tab_count++;
    if(path == NULL || path[0] == '\0')
        path = old_path;
    if(!FileManagerOpenPath(manager, path)) {
        manager->tab_count--;
        manager->active_tab = old_active;
        (void)FileManagerOpenPath(manager, old_path);
        return 0;
    }
    return 1;
}

int
FileManagerSwitchTab(FileManager *manager, int index)
{
    if(manager == NULL || index < 0 || index >= manager->tab_count)
        return 0;
    remember_active_tab(manager);
    manager->active_tab = index;
    return FileManagerOpenPath(manager, manager->tabs[index].path);
}

int
FileManagerCloseTab(FileManager *manager, int index)
{
    int i;

    if(manager == NULL || manager->tab_count <= 1 ||
       index < 0 || index >= manager->tab_count)
        return 0;
    for(i = index + 1; i < manager->tab_count; i++)
        manager->tabs[i - 1] = manager->tabs[i];
    manager->tab_count--;
    if(manager->active_tab > index)
        manager->active_tab--;
    else if(manager->active_tab == index) {
        if(index >= manager->tab_count)
            manager->active_tab = manager->tab_count - 1;
        else
            manager->active_tab = index;
        return FileManagerOpenPath(manager,
                                   manager->tabs[manager->active_tab].path);
    }
    return 1;
}

int
FileManagerNextTab(FileManager *manager)
{
    if(manager == NULL || manager->tab_count <= 1)
        return 0;
    return FileManagerSwitchTab(manager,
                                (manager->active_tab + 1) % manager->tab_count);
}

void
FileManagerResize(FileManager *manager, int width, int height)
{
    if(manager == NULL)
        return;
    manager->width = width;
    manager->height = height;
}

void
FileManagerSetFocused(FileManager *manager, int focused)
{
    if(manager != NULL)
        manager->focused = focused != 0;
}

int
FileManagerSelectedCount(const FileManager *manager)
{
    int count = 0;
    int i;

    if(manager == NULL)
        return 0;
    for(i = 0; i < manager->entry_count; i++)
        if(manager->entries[i].selected)
            count++;
    return count;
}

void
FileManagerClearSelection(FileManager *manager)
{
    int i;

    if(manager == NULL)
        return;
    for(i = 0; i < manager->entry_count; i++)
        manager->entries[i].selected = 0;
}

void
FileManagerSelectAll(FileManager *manager)
{
    int i;

    if(manager == NULL)
        return;
    for(i = 0; i < manager->entry_count; i++)
        manager->entries[i].selected = 1;
    if(manager->entry_count > 0) {
        manager->cursor = 0;
        manager->anchor = 0;
    }
}

static void
select_one(FileManager *manager, int index)
{
    FileManagerClearSelection(manager);
    if(index >= 0 && index < manager->entry_count) {
        manager->entries[index].selected = 1;
        manager->cursor = index;
        manager->anchor = index;
    }
}

static void
select_range(FileManager *manager, int index)
{
    int start;
    int end;
    int i;

    if(manager == NULL || index < 0 || index >= manager->entry_count)
        return;
    if(manager->anchor < 0)
        manager->anchor = manager->cursor >= 0 ? manager->cursor : index;
    start = manager->anchor < index ? manager->anchor : index;
    end = manager->anchor < index ? index : manager->anchor;
    FileManagerClearSelection(manager);
    for(i = start; i <= end; i++)
        manager->entries[i].selected = 1;
    manager->cursor = index;
}

static void
toggle_selection(FileManager *manager, int index)
{
    if(manager == NULL || index < 0 || index >= manager->entry_count)
        return;
    manager->entries[index].selected = !manager->entries[index].selected;
    manager->cursor = index;
    manager->anchor = index;
    if(FileManagerSelectedCount(manager) == 0)
        manager->entries[index].selected = 1;
}

static int
first_selected(const FileManager *manager)
{
    int i;

    if(manager == NULL)
        return -1;
    for(i = 0; i < manager->entry_count; i++)
        if(manager->entries[i].selected)
            return i;
    return manager->cursor;
}

static int
is_trash_view(const FileManager *manager)
{
    char files[FILE_MANAGER_PATH_MAX];

    if(manager == NULL)
        return 0;
    kry_fs_trash_dir(KRY_TRASH_DIR_FILES, files, sizeof(files));
    return same_text(manager->cwd, files);
}

static int
hex_value(int c)
{
    if(c >= '0' && c <= '9')
        return c - '0';
    if(c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    if(c >= 'A' && c <= 'F')
        return c - 'A' + 10;
    return -1;
}

static void
trash_info_unescape(char *out, int out_size, const char *path)
{
    int i;
    int used = 0;

    if(out == NULL || out_size <= 0)
        return;
    out[0] = '\0';
    for(i = 0; path != NULL && path[i] != '\0' && used < out_size - 1; i++) {
        if(path[i] == '%' && path[i + 1] != '\0' && path[i + 2] != '\0') {
            int hi = hex_value(path[i + 1]);
            int lo = hex_value(path[i + 2]);

            if(hi >= 0 && lo >= 0) {
                out[used++] = (char)((hi << 4) | lo);
                out[used] = '\0';
                i += 2;
                continue;
            }
        }
        out[used++] = path[i];
        out[used] = '\0';
    }
}

static int
read_trash_original_path(const char *trashed_path, char *out, int out_size)
{
    char info[FILE_MANAGER_PATH_MAX];
    char info_path[FILE_MANAGER_PATH_MAX];
    char text[FILE_MANAGER_PATH_MAX * 3];
    const char *line;
    const char *end;
    int len;

    if(trashed_path == NULL || out == NULL || out_size <= 0)
        return 0;
    kry_fs_trash_dir(KRY_TRASH_DIR_INFO, info, sizeof(info));
    snprintf(info_path, sizeof(info_path), "%.700s/%.250s.trashinfo", info,
             kry_fs_base_name(trashed_path));
    if(kry_fs_read_file(info_path, text, sizeof(text)) < 0)
        return 0;
    line = strstr(text, "Path=");
    if(line == NULL)
        return 0;
    line += 5;
    end = strchr(line, '\n');
    if(end == NULL)
        end = line + strlen(line);
    len = (int)(end - line);
    if(len < 0)
        return 0;
    if(len >= (int)sizeof(text))
        len = (int)sizeof(text) - 1;
    memmove(text, line, (size_t)len);
    text[len] = '\0';
    trash_info_unescape(out, out_size, text);
    return out[0] != '\0';
}

static void
delete_trash_info_for(const char *trashed_path)
{
    char info[FILE_MANAGER_PATH_MAX];
    char info_path[FILE_MANAGER_PATH_MAX];

    kry_fs_trash_dir(KRY_TRASH_DIR_INFO, info, sizeof(info));
    snprintf(info_path, sizeof(info_path), "%.700s/%.250s.trashinfo", info,
             kry_fs_base_name(trashed_path));
    (void)kry_fs_remove_recursive(info_path);
}

static void
trash_info_escape(char *out, int out_size, const char *path)
{
    int i;
    int used = 0;

    if(out == NULL || out_size <= 0)
        return;
    out[0] = '\0';
    for(i = 0; path != NULL && path[i] != '\0' && used < out_size - 1; i++) {
        unsigned char c = (unsigned char)path[i];

        if(c == ' ' || c == '%' || c == '\n' || c == '\r') {
            if(used + 3 >= out_size)
                break;
            snprintf(out + used, (size_t)(out_size - used), "%%%02X", c);
            used += 3;
        } else {
            out[used++] = (char)c;
            out[used] = '\0';
        }
    }
}

static int
trash_one(const char *path)
{
    char files[FILE_MANAGER_PATH_MAX];
    char info[FILE_MANAGER_PATH_MAX];
    char trashed[FILE_MANAGER_PATH_MAX];
    char info_path[FILE_MANAGER_PATH_MAX];
    char escaped[FILE_MANAGER_PATH_MAX * 2];
    char info_text[FILE_MANAGER_PATH_MAX * 3];
    time_t now;
    struct tm *tm_info;
    char deletion_date[32];

    kry_fs_trash_dir(KRY_TRASH_DIR_FILES, files, sizeof(files));
    kry_fs_trash_dir(KRY_TRASH_DIR_INFO, info, sizeof(info));
    if(kry_fs_mkdir_p(files) != 0 || kry_fs_mkdir_p(info) != 0)
        return 0;
    unique_child_path(trashed, sizeof(trashed), files, kry_fs_base_name(path));
    snprintf(info_path, sizeof(info_path), "%.700s/%.250s.trashinfo", info,
             kry_fs_base_name(trashed));
    if(kry_fs_move(path, trashed) != 0)
        return 0;
    now = time(NULL);
    tm_info = localtime(&now);
    if(tm_info != NULL)
        strftime(deletion_date, sizeof(deletion_date), "%Y-%m-%dT%H:%M:%S",
                 tm_info);
    else
        copy_text(deletion_date, sizeof(deletion_date), "1970-01-01T00:00:00");
    trash_info_escape(escaped, sizeof(escaped), path);
    snprintf(info_text, sizeof(info_text),
             "[Trash Info]\nPath=%s\nDeletionDate=%s\n", escaped,
             deletion_date);
    (void)kry_fs_write_file(info_path, info_text, (int)strlen(info_text));
    return 1;
}

int
FileManagerCreateFolder(FileManager *manager, const char *name)
{
    char path[FILE_MANAGER_PATH_MAX];

    if(manager == NULL || name == NULL || name[0] == '\0')
        return 0;
    kry_fs_join_path(path, sizeof(path), manager->cwd, name);
    if(kry_fs_create_dir(path) != 0) {
        set_error(manager, path);
        return 0;
    }
    return refresh_view(manager);
}

int
FileManagerCreateFile(FileManager *manager, const char *name)
{
    char path[FILE_MANAGER_PATH_MAX];

    if(manager == NULL || name == NULL || name[0] == '\0')
        return 0;
    kry_fs_join_path(path, sizeof(path), manager->cwd, name);
    if(kry_fs_create_file(path) != 0) {
        set_error(manager, path);
        return 0;
    }
    return refresh_view(manager);
}

int
FileManagerRenameSelection(FileManager *manager, const char *name)
{
    int index;
    char parent[FILE_MANAGER_PATH_MAX];
    char path[FILE_MANAGER_PATH_MAX];

    if(manager == NULL || name == NULL || name[0] == '\0')
        return 0;
    if(FileManagerSelectedCount(manager) != 1) {
        set_message(manager, "Rename needs exactly one selected item.");
        return 0;
    }
    index = first_selected(manager);
    if(index < 0)
        return 0;
    kry_fs_parent_path(parent, sizeof(parent), manager->entries[index].path);
    kry_fs_join_path(path, sizeof(path), parent, name);
    if(kry_fs_move(manager->entries[index].path, path) != 0) {
        set_error(manager, path);
        return 0;
    }
    return refresh_view(manager);
}

int
FileManagerDeleteSelection(FileManager *manager, int use_trash)
{
    char paths[FILE_MANAGER_MAX_SELECTION][FILE_MANAGER_PATH_MAX];
    int count = 0;
    int i;

    if(manager == NULL)
        return 0;
    for(i = 0; i < manager->entry_count && count < FILE_MANAGER_MAX_SELECTION; i++) {
        if(manager->entries[i].selected) {
            copy_text(paths[count], FILE_MANAGER_PATH_MAX, manager->entries[i].path);
            count++;
        }
    }
    if(count <= 0)
        return 0;
    for(i = 0; i < count; i++) {
        int ok = use_trash ? trash_one(paths[i]) :
            kry_fs_remove_recursive(paths[i]) == 0;

        if(!ok) {
            set_error(manager, paths[i]);
            (void)refresh_view(manager);
            return 0;
        }
    }
    return refresh_view(manager);
}

int
FileManagerRestoreSelection(FileManager *manager)
{
    char paths[FILE_MANAGER_MAX_SELECTION][FILE_MANAGER_PATH_MAX];
    int count = 0;
    int i;

    if(manager == NULL || !is_trash_view(manager))
        return 0;
    for(i = 0; i < manager->entry_count && count < FILE_MANAGER_MAX_SELECTION; i++) {
        if(manager->entries[i].selected) {
            copy_text(paths[count], FILE_MANAGER_PATH_MAX, manager->entries[i].path);
            count++;
        }
    }
    if(count <= 0)
        return 0;
    for(i = 0; i < count; i++) {
        char original[FILE_MANAGER_PATH_MAX];
        char parent[FILE_MANAGER_PATH_MAX];
        char dst[FILE_MANAGER_PATH_MAX];

        if(!read_trash_original_path(paths[i], original, sizeof(original))) {
            set_message(manager, "Could not read the trash metadata.");
            (void)refresh_view(manager);
            return 0;
        }
        kry_fs_parent_path(parent, sizeof(parent), original);
        if(kry_fs_mkdir_p(parent) != 0) {
            set_error(manager, parent);
            (void)refresh_view(manager);
            return 0;
        }
        if(kry_fs_exists(original)) {
            unique_child_path(dst, sizeof(dst), parent, kry_fs_base_name(original));
        } else {
            copy_text(dst, sizeof(dst), original);
        }
        if(kry_fs_move(paths[i], dst) != 0) {
            set_error(manager, paths[i]);
            (void)refresh_view(manager);
            return 0;
        }
        delete_trash_info_for(paths[i]);
    }
    return refresh_view(manager);
}

int
FileManagerCopySelection(FileManager *manager, int cut)
{
    int i;
    int count = 0;

    if(manager == NULL)
        return 0;
    memset(&manager->clipboard, 0, sizeof(manager->clipboard));
    for(i = 0; i < manager->entry_count && count < FILE_MANAGER_MAX_SELECTION; i++) {
        if(manager->entries[i].selected) {
            copy_text(manager->clipboard.paths[count], FILE_MANAGER_PATH_MAX,
                      manager->entries[i].path);
            count++;
        }
    }
    manager->clipboard.count = count;
    manager->clipboard.mode = count > 0 ?
        (cut ? FILE_CLIPBOARD_CUT : FILE_CLIPBOARD_COPY) : FILE_CLIPBOARD_NONE;
    return count > 0;
}

int
FileManagerPaste(FileManager *manager)
{
    int i;
    int ok = 1;

    if(manager == NULL || manager->clipboard.count <= 0 ||
       manager->clipboard.mode == FILE_CLIPBOARD_NONE)
        return 0;
    for(i = 0; i < manager->clipboard.count; i++) {
        char dst[FILE_MANAGER_PATH_MAX];
        const char *src = manager->clipboard.paths[i];

        unique_child_path(dst, sizeof(dst), manager->cwd, kry_fs_base_name(src));
        if(manager->clipboard.mode == FILE_CLIPBOARD_CUT) {
            if(kry_fs_move(src, dst) != 0) {
                set_error(manager, src);
                ok = 0;
                break;
            }
        } else if(kry_fs_copy_recursive(src, dst) != 0) {
            set_error(manager, src);
            ok = 0;
            break;
        }
    }
    if(manager->clipboard.mode == FILE_CLIPBOARD_CUT)
        memset(&manager->clipboard, 0, sizeof(manager->clipboard));
    (void)refresh_view(manager);
    return ok;
}

int
FileManagerDuplicateSelection(FileManager *manager)
{
    char paths[FILE_MANAGER_MAX_SELECTION][FILE_MANAGER_PATH_MAX];
    int count = 0;
    int i;

    if(manager == NULL)
        return 0;
    for(i = 0; i < manager->entry_count && count < FILE_MANAGER_MAX_SELECTION; i++) {
        if(manager->entries[i].selected) {
            copy_text(paths[count], FILE_MANAGER_PATH_MAX, manager->entries[i].path);
            count++;
        }
    }
    if(count <= 0)
        return 0;
    for(i = 0; i < count; i++) {
        char dst[FILE_MANAGER_PATH_MAX];
        char parent[FILE_MANAGER_PATH_MAX];

        kry_fs_parent_path(parent, sizeof(parent), paths[i]);
        unique_child_path(dst, sizeof(dst), parent, kry_fs_base_name(paths[i]));
        if(kry_fs_copy_recursive(paths[i], dst) != 0) {
            set_error(manager, paths[i]);
            (void)refresh_view(manager);
            return 0;
        }
    }
    return refresh_view(manager);
}

int
FileManagerMakeLinkSelection(FileManager *manager)
{
    char paths[FILE_MANAGER_MAX_SELECTION][FILE_MANAGER_PATH_MAX];
    int count = 0;
    int i;

    if(manager == NULL)
        return 0;
    for(i = 0; i < manager->entry_count && count < FILE_MANAGER_MAX_SELECTION; i++) {
        if(manager->entries[i].selected) {
            copy_text(paths[count], FILE_MANAGER_PATH_MAX, manager->entries[i].path);
            count++;
        }
    }
    if(count <= 0)
        return 0;
    for(i = 0; i < count; i++) {
        char link_name[300];
        char dst[FILE_MANAGER_PATH_MAX];
        char parent[FILE_MANAGER_PATH_MAX];

        snprintf(link_name, sizeof(link_name), "%.250s link", kry_fs_base_name(paths[i]));
        kry_fs_parent_path(parent, sizeof(parent), paths[i]);
        unique_child_path(dst, sizeof(dst), parent, link_name);
        if(kry_fs_symlink(paths[i], dst) != 0) {
            set_error(manager, paths[i]);
            (void)refresh_view(manager);
            return 0;
        }
    }
    return refresh_view(manager);
}

static void
open_parent(FileManager *manager)
{
    char parent[FILE_MANAGER_PATH_MAX];

    kry_fs_parent_path(parent, sizeof(parent), manager->cwd);
    (void)FileManagerOpenPathTracked(manager, parent);
}

static void
open_home(FileManager *manager)
{
    (void)FileManagerOpenPathTracked(manager, home_path());
}

static void
open_back(FileManager *manager)
{
    char path[FILE_MANAGER_PATH_MAX];

    if(manager == NULL || !history_pop(manager->back, &manager->back_count,
                                       path, sizeof(path)))
        return;
    history_push(manager->forward, &manager->forward_count, manager->cwd);
    (void)FileManagerOpenPath(manager, path);
}

static void
open_forward(FileManager *manager)
{
    char path[FILE_MANAGER_PATH_MAX];

    if(manager == NULL || !history_pop(manager->forward, &manager->forward_count,
                                       path, sizeof(path)))
        return;
    history_push(manager->back, &manager->back_count, manager->cwd);
    (void)FileManagerOpenPath(manager, path);
}

static void
open_selected(FileManager *manager)
{
    int index;

    if(manager == NULL)
        return;
    index = first_selected(manager);
    if(index < 0 || index >= manager->entry_count)
        return;
    if(manager->entries[index].is_dir) {
        (void)FileManagerOpenPathTracked(manager, manager->entries[index].path);
    } else {
        OpenURL(manager->entries[index].path);
    }
}

static int
hit(Rectangle r)
{
    return CheckCollisionPointRec(GetMousePosition(), r);
}

static void
draw_label(const char *text, int x, int y, int font_size, Color color)
{
    Vector2 position;

    if(text == NULL)
        text = "";
    position.x = (float)x;
    position.y = (float)y;
    DrawTextEx(GetTextFont(), text, position, (float)font_size, 0.0f, color);
}

static void
draw_text_fit_right(const char *text, int x, int y, int max_width,
                    int font_size, Color color)
{
    int width;

    if(text == NULL)
        text = "";
    while(font_size > Text8 &&
          MeasureTextWidth(text, font_size, NULL) > max_width)
        font_size -= 2;
    width = MeasureTextWidth(text, font_size, NULL);
    draw_label(text, x + max_width - width, y, font_size, color);
}

#ifdef FILE_MANAGER_HAS_GDK_PIXBUF
static Texture2D
load_icon_pixbuf(const char *path, int size)
{
    GError *error = NULL;
    GdkPixbuf *pixbuf;
    unsigned char *rgba;
    unsigned char *pixels;
    int width;
    int height;
    int stride;
    int channels;
    int has_alpha;
    int x;
    int y;
    Image image = {0};
    Texture2D texture = {0};

    pixbuf = gdk_pixbuf_new_from_file_at_scale(path, size, size, TRUE, &error);
    if(pixbuf == NULL) {
        if(error != NULL)
            g_error_free(error);
        return texture;
    }
    width = gdk_pixbuf_get_width(pixbuf);
    height = gdk_pixbuf_get_height(pixbuf);
    stride = gdk_pixbuf_get_rowstride(pixbuf);
    channels = gdk_pixbuf_get_n_channels(pixbuf);
    has_alpha = gdk_pixbuf_get_has_alpha(pixbuf);
    pixels = gdk_pixbuf_get_pixels(pixbuf);
    rgba = malloc((size_t)width * (size_t)height * 4);
    if(rgba == NULL) {
        g_object_unref(pixbuf);
        return texture;
    }
    for(y = 0; y < height; y++) {
        for(x = 0; x < width; x++) {
            unsigned char *src = pixels + y * stride + x * channels;
            unsigned char *dst = rgba + ((size_t)y * (size_t)width + (size_t)x) * 4;

            dst[0] = src[0];
            dst[1] = src[1];
            dst[2] = src[2];
            dst[3] = has_alpha ? src[3] : 255;
        }
    }
    image.data = rgba;
    image.width = width;
    image.height = height;
    image.mipmaps = 1;
    image.format = PIXELFORMAT_UNCOMPRESSED_R8G8B8A8;
    texture = LoadTextureFromImage(image);
    free(rgba);
    g_object_unref(pixbuf);
    return texture;
}
#endif

static Texture2D
load_themed_icon(const char *name, int size)
{
    char path[FILE_MANAGER_PATH_MAX];
    Texture2D texture = {0};

    if(kry_fs_find_icon(name, size, path, sizeof(path))) {
#ifdef FILE_MANAGER_HAS_GDK_PIXBUF
        texture = load_icon_pixbuf(path, size);
        if(IsTextureValid(texture))
            return texture;
#endif
        texture = LoadTexture(path);
    }
    return texture;
}

static void
load_icons(void)
{
    if(icons.loaded)
        return;
    icons.loaded = 1;
    icons.folder = load_themed_icon("folder", 64);
    icons.file = load_themed_icon("text-x-generic", 64);
    icons.home = load_themed_icon("user-home", 24);
    icons.desktop = load_themed_icon("user-desktop", 24);
    icons.documents = load_themed_icon("folder-documents", 24);
    icons.downloads = load_themed_icon("folder-download", 24);
    icons.trash = load_themed_icon("user-trash", 24);
    icons.filesystem = load_themed_icon("drive-harddisk", 24);
}

static void
draw_texture_icon(Texture2D texture, Rectangle r, Color tint)
{
    Rectangle source = {0, 0, (float)texture.width, (float)texture.height};
    Vector2 origin = {0, 0};

    if(!IsTextureValid(texture))
        return;
    DrawTexturePro(texture, source, r, origin, 0.0f, tint);
}

static void
draw_icon(Rectangle r, int is_dir)
{
    Color c = is_dir ? GetThemeLink() : GetThemeIcon();
    Rectangle body;
    Vector2 a;
    Vector2 b;

    load_icons();
    if(is_dir && IsTextureValid(icons.folder)) {
        draw_texture_icon(icons.folder, r, WHITE);
        return;
    }
    if(!is_dir && IsTextureValid(icons.file)) {
        draw_texture_icon(icons.file, r, WHITE);
        return;
    }
    if(is_dir) {
        body.x = r.x + 7;
        body.y = r.y + 20;
        body.width = r.width - 14;
        body.height = r.height - 24;
        DrawRectangleRoundedLinesEx(body, 0.06f, 4, 3.0f, c);
        a.x = r.x + 11;
        a.y = r.y + 19;
        b.x = r.x + 24;
        b.y = r.y + 10;
        DrawLineEx(a, b, 3.0f, c);
        a.x = r.x + 24;
        a.y = r.y + 10;
        b.x = r.x + 39;
        b.y = r.y + 10;
        DrawLineEx(a, b, 3.0f, Fade(PINK, 0.85f));
        a.x = r.x + 39;
        a.y = r.y + 10;
        b.x = r.x + 48;
        b.y = r.y + 20;
        DrawLineEx(a, b, 3.0f, Fade(PINK, 0.85f));
    } else {
        body.x = r.x + 5;
        body.y = r.y + 3;
        body.width = r.width - 10;
        body.height = r.height - 6;
        DrawRectangleRounded(body, 0.04f, 4, Fade(GetThemeSurface(), 0.96f));
        DrawRectangleRoundedLinesEx(body, 0.04f, 4, 1.0f, c);
    }
}

static int
small_button(Rectangle r, const char *label, int id, int disabled)
{
    ButtonProps props;

    memset(&props, 0, sizeof(props));
    props.bounds = r;
    props.label = label;
    props.id = id;
    props.emphasis = ButtonEmphasisSoft;
    props.size = ControlSizeSmall;
    props.disabled = disabled != 0;
    return Button(props);
}

static void
start_prompt(FileManager *manager, FileDialogKind dialog, const char *text)
{
    if(manager == NULL)
        return;
    manager->dialog = dialog;
    copy_text(manager->dialog_text, sizeof(manager->dialog_text), text);
    manager->dialog_cursor = (int)strlen(manager->dialog_text);
    manager->dialog_focused = 1;
}

static void
show_properties(FileManager *manager)
{
    int selected = FileManagerSelectedCount(manager);
    int index = first_selected(manager);
    unsigned long long total = 0;
    int i;
    char size_text[32];
    char modified_text[32];

    if(manager == NULL)
        return;
    if(selected <= 0) {
        snprintf(manager->dialog_message, sizeof(manager->dialog_message),
                 "Location: %s\nItems: %d", manager->cwd, manager->entry_count);
    } else if(selected == 1 && index >= 0) {
        FileEntry *entry = &manager->entries[index];

        format_size(size_text, sizeof(size_text), entry->size, entry->is_dir);
        format_modified(modified_text, sizeof(modified_text), entry->modified);
        snprintf(manager->dialog_message, sizeof(manager->dialog_message),
                 "Name: %s\nPath: %s\nType: %s\nSize: %s\nModified: %s\nReadable: %s",
                 entry->name, entry->path, entry->is_dir ? "Folder" : "File",
                 size_text, modified_text, entry->readable ? "Yes" : "No");
    } else {
        for(i = 0; i < manager->entry_count; i++)
            if(manager->entries[i].selected)
                total += manager->entries[i].size;
        format_size(size_text, sizeof(size_text), total, 0);
        snprintf(manager->dialog_message, sizeof(manager->dialog_message),
                 "Selected items: %d\nCombined top-level size: %s",
                 selected, size_text);
    }
    manager->dialog = FILE_DIALOG_PROPERTIES;
}

static void
set_sort(FileManager *manager, FileSortMode mode)
{
    if(manager == NULL)
        return;
    if(manager->sort_mode == mode)
        manager->sort_reverse = !manager->sort_reverse;
    else {
        manager->sort_mode = mode;
        manager->sort_reverse = 0;
    }
    (void)FileManagerOpenPath(manager, manager->cwd);
}

static void
handle_menu_command(FileManager *manager, int command)
{
    int index;

    if(manager == NULL)
        return;
    switch(command) {
    case 3001:
        (void)FileManagerNewTab(manager, manager->cwd);
        break;
    case 3002:
        (void)FileManagerCloseTab(manager, manager->active_tab);
        break;
    case 3003:
        start_prompt(manager, FILE_DIALOG_NEW_FOLDER, "New Folder");
        break;
    case 3004:
        start_prompt(manager, FILE_DIALOG_NEW_FILE, "New File.txt");
        break;
    case 3005:
        index = first_selected(manager);
        if(index >= 0 && FileManagerSelectedCount(manager) == 1)
            start_prompt(manager, FILE_DIALOG_RENAME, manager->entries[index].name);
        break;
    case 3006:
        show_properties(manager);
        break;
    case 3010:
        (void)FileManagerCopySelection(manager, 0);
        break;
    case 3011:
        (void)FileManagerCopySelection(manager, 1);
        break;
    case 3012:
        (void)FileManagerPaste(manager);
        break;
    case 3013:
        FileManagerSelectAll(manager);
        break;
    case 3014:
        (void)FileManagerDuplicateSelection(manager);
        break;
    case 3015:
        (void)FileManagerMakeLinkSelection(manager);
        break;
    case 3016:
        manager->dialog = FILE_DIALOG_TRASH;
        break;
    case 3017:
        manager->dialog = FILE_DIALOG_DELETE;
        break;
    case 3018:
        (void)FileManagerRestoreSelection(manager);
        break;
    case 3020:
        manager->show_hidden = !manager->show_hidden;
        (void)FileManagerOpenPath(manager, manager->cwd);
        break;
    case 3021:
        set_sort(manager, FILE_SORT_NAME);
        break;
    case 3022:
        set_sort(manager, FILE_SORT_SIZE);
        break;
    case 3023:
        set_sort(manager, FILE_SORT_MODIFIED);
        break;
    case 3024:
        set_sort(manager, FILE_SORT_TYPE);
        break;
    case 3025:
        (void)FileManagerOpenPath(manager, manager->cwd);
        break;
    case 3030:
        open_back(manager);
        break;
    case 3031:
        open_forward(manager);
        break;
    case 3032:
        open_parent(manager);
        break;
    case 3033:
        open_home(manager);
        break;
    case 3034:
        start_prompt(manager, FILE_DIALOG_LOCATION, manager->cwd);
        break;
    case 3035:
        start_prompt(manager, FILE_DIALOG_SEARCH, manager->search_query);
        break;
    case 3040:
        snprintf(manager->dialog_message, sizeof(manager->dialog_message),
                 "Files\n\nKryon file manager\n\nCtrl+T New tab\nCtrl+W Close tab\nCtrl+F Search\nF2 Rename\nDelete Move to trash");
        manager->dialog = FILE_DIALOG_PROPERTIES;
        break;
    default:
        break;
    }
}

static void
draw_menu_bar(FileManager *manager, Rectangle menu)
{
    MenuItem file_items[] = {
        {MenuCommand, "New Tab", "Ctrl+T", 3001, 0, 0, NULL, 0},
        {MenuCommand, "Close Tab", "Ctrl+W", 3002, manager->tab_count <= 1, 0, NULL, 0},
        {MenuSeparator, NULL, NULL, 0, 0, 0, NULL, 0},
        {MenuCommand, "New Folder", NULL, 3003, 0, 0, NULL, 0},
        {MenuCommand, "New File", NULL, 3004, 0, 0, NULL, 0},
        {MenuCommand, "Rename", "F2", 3005, FileManagerSelectedCount(manager) != 1, 0, NULL, 0},
        {MenuSeparator, NULL, NULL, 0, 0, 0, NULL, 0},
        {MenuCommand, "Properties", "Alt+Enter", 3006, 0, 0, NULL, 0}
    };
    MenuItem edit_items[] = {
        {MenuCommand, "Copy", "Ctrl+C", 3010, FileManagerSelectedCount(manager) <= 0, 0, NULL, 0},
        {MenuCommand, "Cut", "Ctrl+X", 3011, FileManagerSelectedCount(manager) <= 0, 0, NULL, 0},
        {MenuCommand, "Paste", "Ctrl+V", 3012, manager->clipboard.count <= 0, 0, NULL, 0},
        {MenuCommand, "Select All", "Ctrl+A", 3013, manager->entry_count <= 0, 0, NULL, 0},
        {MenuSeparator, NULL, NULL, 0, 0, 0, NULL, 0},
        {MenuCommand, "Duplicate", NULL, 3014, FileManagerSelectedCount(manager) <= 0, 0, NULL, 0},
        {MenuCommand, "Make Link", NULL, 3015, FileManagerSelectedCount(manager) <= 0, 0, NULL, 0},
        {MenuCommand, "Move to Trash", "Del", 3016, FileManagerSelectedCount(manager) <= 0, 0, NULL, 0},
        {MenuCommand, "Delete", "Shift+Del", 3017, FileManagerSelectedCount(manager) <= 0, 0, NULL, 0},
        {MenuCommand, "Restore", NULL, 3018, FileManagerSelectedCount(manager) <= 0 || !is_trash_view(manager), 0, NULL, 0}
    };
    MenuItem view_items[] = {
        {MenuCheck, "Show Hidden Files", "Ctrl+H", 3020, 0, manager->show_hidden, NULL, 0},
        {MenuSeparator, NULL, NULL, 0, 0, 0, NULL, 0},
        {MenuRadio, "Sort by Name", NULL, 3021, 0, manager->sort_mode == FILE_SORT_NAME, NULL, 0},
        {MenuRadio, "Sort by Size", NULL, 3022, 0, manager->sort_mode == FILE_SORT_SIZE, NULL, 0},
        {MenuRadio, "Sort by Date", NULL, 3023, 0, manager->sort_mode == FILE_SORT_MODIFIED, NULL, 0},
        {MenuRadio, "Sort by Type", NULL, 3024, 0, manager->sort_mode == FILE_SORT_TYPE, NULL, 0},
        {MenuSeparator, NULL, NULL, 0, 0, 0, NULL, 0},
        {MenuCommand, "Reload", "F5", 3025, 0, 0, NULL, 0}
    };
    MenuItem go_items[] = {
        {MenuCommand, "Back", NULL, 3030, manager->back_count <= 0, 0, NULL, 0},
        {MenuCommand, "Forward", NULL, 3031, manager->forward_count <= 0, 0, NULL, 0},
        {MenuCommand, "Up", "Backspace", 3032, 0, 0, NULL, 0},
        {MenuCommand, "Home", NULL, 3033, 0, 0, NULL, 0},
        {MenuSeparator, NULL, NULL, 0, 0, 0, NULL, 0},
        {MenuCommand, "Location", "Ctrl+L", 3034, 0, 0, NULL, 0},
        {MenuCommand, "Search", "Ctrl+F", 3035, 0, 0, NULL, 0}
    };
    MenuItem bookmark_items[] = {
        {MenuCommand, "Home", NULL, 3033, 0, 0, NULL, 0},
        {MenuCommand, "Location", "Ctrl+L", 3034, 0, 0, NULL, 0}
    };
    MenuItem help_items[] = {
        {MenuCommand, "About Files", NULL, 3040, 0, 0, NULL, 0}
    };
    MenuGroup menus[6];
    MenuProps in;
    MenuResult out;

    memset(menus, 0, sizeof(menus));
    menus[0].label = "File";
    menus[0].items = file_items;
    menus[0].item_count = (int)(sizeof(file_items) / sizeof(file_items[0]));
    menus[1].label = "Edit";
    menus[1].items = edit_items;
    menus[1].item_count = (int)(sizeof(edit_items) / sizeof(edit_items[0]));
    menus[2].label = "View";
    menus[2].items = view_items;
    menus[2].item_count = (int)(sizeof(view_items) / sizeof(view_items[0]));
    menus[3].label = "Go";
    menus[3].items = go_items;
    menus[3].item_count = (int)(sizeof(go_items) / sizeof(go_items[0]));
    menus[4].label = "Bookmarks";
    menus[4].items = bookmark_items;
    menus[4].item_count =
        (int)(sizeof(bookmark_items) / sizeof(bookmark_items[0]));
    menus[5].label = "Help";
    menus[5].items = help_items;
    menus[5].item_count = (int)(sizeof(help_items) / sizeof(help_items[0]));

    memset(&in, 0, sizeof(in));
    in.id = 4000;
    in.mode = MenuModeBar;
    in.bounds = menu;
    in.menus = menus;
    in.menu_count = 6;
    in.open_index = &manager->menu_open;
    out = Menu(in);
    if(out.activated_id != 0)
        handle_menu_command(manager, out.activated_id);
}

static void
tab_label(char *out, int out_size, const FileTab *tab)
{
    const char *name;

    if(tab == NULL || tab->path[0] == '\0') {
        copy_text(out, out_size, "Files");
        return;
    }
    name = kry_fs_base_name(tab->path);
    if(name[0] == '\0')
        name = "File System";
    copy_text(out, out_size, name);
}

static void
draw_tabs(FileManager *manager, Rectangle tabs)
{
    int x = (int)tabs.x + 8;
    int y = (int)tabs.y + 4;
    int i;
    Rectangle add;

    DrawRectangleRec(tabs, opaque_color(GetThemeSurface()));
    DrawRectangle((int)tabs.x, (int)(tabs.y + tabs.height - 1),
                  (int)tabs.width, 1, Fade(GetThemeText(), 0.16f));
    for(i = 0; i < manager->tab_count; i++) {
        Rectangle tab = {(float)x, (float)y, 132, 24};
        Rectangle close = {tab.x + tab.width - 25, tab.y + 2, 20, 20};
        char label[96];
        int active = i == manager->active_tab;

        if(tab.x + tab.width > tabs.x + tabs.width - 44)
            break;
        if(active)
            DrawRectangleRounded(tab, 0.08f, 4, Fade(GetThemeButtonHover(), 0.75f));
        else if(hit(tab))
            DrawRectangleRounded(tab, 0.08f, 4, Fade(GetThemeButton(), 0.42f));
        tab_label(label, sizeof(label), &manager->tabs[i]);
        BeginScissorMode((int)tab.x + 8, (int)tab.y,
                         (int)tab.width - (manager->tab_count > 1 ? 36 : 16),
                         (int)tab.height);
        draw_label(label, (int)tab.x + 8, (int)tab.y + 7, Text12,
             active ? GetThemeText() : GetThemeIcon());
        EndScissorMode();
        if(manager->tab_count > 1 &&
           small_button(close, "x", 12000 + i, 0)) {
            (void)FileManagerCloseTab(manager, i);
            return;
        }
        if(hit(tab) && IsMouseButtonReleased(MOUSE_BUTTON_LEFT))
            (void)FileManagerSwitchTab(manager, i);
        x += 138;
    }
    if(manager->tab_count < FILE_MANAGER_MAX_TABS &&
       x + 30 < tabs.x + tabs.width) {
        add.x = (float)x;
        add.y = (float)y;
        add.width = 28;
        add.height = 24;
        if(small_button(add, "+", 12100, 0))
            (void)FileManagerNewTab(manager, manager->cwd);
    }
}

static void
draw_toolbar(FileManager *manager, Rectangle toolbar)
{
    Rectangle menu = {toolbar.x, toolbar.y, toolbar.width, 28};
    Rectangle location = {toolbar.x, toolbar.y + 28, toolbar.width, 42};
    int x = (int)location.x + 10;
    int y = (int)location.y + 7;
    int field_x;
    Rectangle b;
    Rectangle field;

    DrawRectangleRec(toolbar, opaque_color(GetThemeSurface()));
    DrawRectangle((int)toolbar.x, (int)(toolbar.y + toolbar.height - 1),
                  (int)toolbar.width, 1, Fade(GetThemeText(), 0.18f));

    draw_menu_bar(manager, menu);

    b.x = (float)x;
    b.y = (float)y;
    b.width = 32;
    b.height = 26;
    if(small_button(b, "<", 1001, manager->back_count <= 0))
        open_back(manager);
    x += 36;
    b.x = (float)x;
    if(small_button(b, ">", 1002, manager->forward_count <= 0))
        open_forward(manager);
    x += 36;
    b.x = (float)x;
    if(small_button(b, "^", 1003, 0))
        open_parent(manager);
    x += 36;
    b.x = (float)x;
    b.width = 52;
    if(small_button(b, "Home", 1004, 0))
        open_home(manager);
    x += 60;
    field_x = x;
    field.x = (float)field_x;
    field.y = (float)y;
    field.width = location.width - (field_x - location.x) - 50;
    field.height = 26;
    DrawRectangleRounded(field, 0.02f, 4, Fade(GetThemeBackground(), 0.86f));
    draw_label(manager->cwd, field_x + 10, y + 7, Text14, GetThemeText());
    if(hit(field) && IsMouseButtonReleased(MOUSE_BUTTON_LEFT))
        start_prompt(manager, FILE_DIALOG_LOCATION, manager->cwd);
    x = (int)(location.x + location.width - 42);
    b.x = (float)x;
    b.width = 36;
    if(small_button(b, "Find", 1111, 0))
        start_prompt(manager, FILE_DIALOG_SEARCH, manager->search_query);
}

static void
draw_places(FileManager *manager, Rectangle sidebar)
{
    typedef struct PlaceItem {
        const char *label;
        const char *path;
        Texture2D *icon;
    } PlaceItem;
    char desktop[FILE_MANAGER_PATH_MAX];
    char documents[FILE_MANAGER_PATH_MAX];
    char downloads[FILE_MANAGER_PATH_MAX];
    char trash[FILE_MANAGER_PATH_MAX];
    PlaceItem places[6];
    int count = 0;
    int i;
    int y = (int)sidebar.y + 10;

    kry_fs_user_dir(KRY_USER_DIR_DESKTOP, desktop, sizeof(desktop));
    kry_fs_user_dir(KRY_USER_DIR_DOCUMENTS, documents, sizeof(documents));
    kry_fs_user_dir(KRY_USER_DIR_DOWNLOAD, downloads, sizeof(downloads));
    kry_fs_trash_dir(KRY_TRASH_DIR_FILES, trash, sizeof(trash));

    load_icons();
    places[count].label = "Home";
    places[count].path = home_path();
    places[count].icon = &icons.home;
    count++;
    places[count].label = "Desktop";
    places[count].path = desktop;
    places[count].icon = &icons.desktop;
    count++;
    places[count].label = "Documents";
    places[count].path = documents;
    places[count].icon = &icons.documents;
    count++;
    places[count].label = "Downloads";
    places[count].path = downloads;
    places[count].icon = &icons.downloads;
    count++;
    places[count].label = "Trash";
    places[count].path = trash;
    places[count].icon = &icons.trash;
    count++;
    places[count].label = "File System";
    places[count].path = "/";
    places[count].icon = &icons.filesystem;
    count++;

    DrawRectangleRec(sidebar, Fade(GetThemeSurface(), 0.66f));
    draw_label("Places", (int)sidebar.x + 12, y, Text12, GetThemeIcon());
    y += 24;
    for(i = 0; i < count; i++) {
        Rectangle row = {sidebar.x + 6, y, sidebar.width - 12, 28};
        int active = same_text(manager->cwd, places[i].path);
        int exists = kry_fs_exists(places[i].path);
        Rectangle icon_rect = {row.x + 8, row.y + 6, 16, 16};

        if(active)
            DrawRectangleRounded(row, 0.08f, 4, Fade(GetThemeButtonHover(), 0.70f));
        else if(hit(row))
            DrawRectangleRounded(row, 0.08f, 4, Fade(GetThemeButton(), 0.42f));
        if(places[i].icon != NULL && IsTextureValid(*places[i].icon))
            draw_texture_icon(*places[i].icon, icon_rect, WHITE);
        else {
            icon_rect.x = row.x + 9;
            icon_rect.y = row.y + 8;
            icon_rect.width = 12;
            icon_rect.height = 12;
            DrawRectangleRounded(icon_rect, 0.20f, 4, GetThemeIcon());
        }
        draw_label(places[i].label, (int)row.x + 30, (int)row.y + 8, Text12,
             exists ? GetThemeText() : GetThemeIcon());
        if(exists && hit(row) && IsMouseButtonReleased(MOUSE_BUTTON_LEFT))
            (void)FileManagerOpenPathTracked(manager, places[i].path);
        y += 30;
    }
}

static int
entry_name_starts_with(const FileEntry *entry, const char *prefix)
{
    size_t len;

    if(entry == NULL || prefix == NULL)
        return 0;
    len = strlen(prefix);
    return len > 0 && strncasecmp(entry->name, prefix, len) == 0;
}

static void
handle_typeahead(FileManager *manager, int visible)
{
    int ch;
    int changed = 0;
    double now;

    if(manager == NULL || mod_down())
        return;
    now = GetTime();
    if(now - manager->typeahead_time > 1.2)
        manager->typeahead[0] = '\0';
    while((ch = GetCharPressed()) != 0) {
        size_t len;

        if(ch < 32 || ch > 126)
            continue;
        len = strlen(manager->typeahead);
        if(len + 1 >= sizeof(manager->typeahead))
            manager->typeahead[0] = '\0';
        len = strlen(manager->typeahead);
        manager->typeahead[len] = (char)ch;
        manager->typeahead[len + 1] = '\0';
        manager->typeahead_time = now;
        changed = 1;
    }
    if(changed && manager->typeahead[0] != '\0') {
        int i;
        int start = manager->cursor >= 0 ? manager->cursor : 0;

        for(i = 0; i < manager->entry_count; i++) {
            int index = (start + i) % manager->entry_count;

            if(entry_name_starts_with(&manager->entries[index],
                                      manager->typeahead)) {
                select_one(manager, index);
                ensure_cursor_visible(manager, visible);
                break;
            }
        }
    }
}

static void
handle_keyboard(FileManager *manager, int visible)
{
    int next = manager->cursor;

    if(manager == NULL || !manager->focused || manager->dialog != FILE_DIALOG_NONE)
        return;
    if(mod_down() && IsKeyPressed(KEY_T)) {
        (void)FileManagerNewTab(manager, manager->cwd);
        return;
    }
    if(mod_down() && IsKeyPressed(KEY_W)) {
        (void)FileManagerCloseTab(manager, manager->active_tab);
        return;
    }
    if(mod_down() && IsKeyPressed(KEY_TAB)) {
        (void)FileManagerNextTab(manager);
        return;
    }
    if(mod_down() && IsKeyPressed(KEY_A)) {
        FileManagerSelectAll(manager);
        return;
    }
    if(mod_down() && IsKeyPressed(KEY_C)) {
        (void)FileManagerCopySelection(manager, 0);
        return;
    }
    if(mod_down() && IsKeyPressed(KEY_X)) {
        (void)FileManagerCopySelection(manager, 1);
        return;
    }
    if(mod_down() && IsKeyPressed(KEY_V)) {
        (void)FileManagerPaste(manager);
        return;
    }
    if(mod_down() && IsKeyPressed(KEY_H)) {
        manager->show_hidden = !manager->show_hidden;
        (void)FileManagerOpenPath(manager, manager->cwd);
        return;
    }
    if(mod_down() && IsKeyPressed(KEY_L)) {
        start_prompt(manager, FILE_DIALOG_LOCATION, manager->cwd);
        return;
    }
    if(mod_down() && IsKeyPressed(KEY_F)) {
        start_prompt(manager, FILE_DIALOG_SEARCH, manager->search_query);
        return;
    }
    if(IsKeyDown(KEY_LEFT_ALT) || IsKeyDown(KEY_RIGHT_ALT)) {
        if(IsKeyPressed(KEY_ENTER) || IsKeyPressed(KEY_KP_ENTER)) {
            show_properties(manager);
            return;
        }
    }
    if(IsKeyPressed(KEY_F5)) {
        (void)FileManagerOpenPath(manager, manager->cwd);
        return;
    }
    if(IsKeyPressed(KEY_F2)) {
        int index = first_selected(manager);
        if(index >= 0 && FileManagerSelectedCount(manager) == 1)
            start_prompt(manager, FILE_DIALOG_RENAME, manager->entries[index].name);
        return;
    }
    if(IsKeyPressed(KEY_DELETE)) {
        manager->dialog = shift_down() ? FILE_DIALOG_DELETE : FILE_DIALOG_TRASH;
        return;
    }
    if(IsKeyPressed(KEY_BACKSPACE)) {
        open_parent(manager);
        return;
    }
    if(IsKeyPressed(KEY_ENTER) || IsKeyPressed(KEY_KP_ENTER)) {
        open_selected(manager);
        return;
    }
    if(IsKeyPressed(KEY_ESCAPE) && manager->search_active) {
        (void)FileManagerOpenPath(manager, manager->search_root);
        return;
    }
    if(manager->entry_count <= 0)
        return;
    if(IsKeyPressed(KEY_UP))
        next--;
    else if(IsKeyPressed(KEY_DOWN))
        next++;
    else if(IsKeyPressed(KEY_HOME))
        next = 0;
    else if(IsKeyPressed(KEY_END))
        next = manager->entry_count - 1;
    else if(IsKeyPressed(KEY_PAGE_UP))
        next -= visible;
    else if(IsKeyPressed(KEY_PAGE_DOWN))
        next += visible;
    if(next != manager->cursor) {
        if(next < 0)
            next = 0;
        if(next >= manager->entry_count)
            next = manager->entry_count - 1;
        if(shift_down())
            select_range(manager, next);
        else
            select_one(manager, next);
        ensure_cursor_visible(manager, visible);
    }
    handle_typeahead(manager, visible);
}

static void
draw_rows(FileManager *manager, Rectangle list)
{
    int cell_w = 136;
    int cell_h = 98;
    int icon_size = 58;
    int cols;
    int visible_rows;
    int max_scroll;
    int row;
    int col;
    float wheel;

    cols = (int)(list.width / cell_w);
    if(cols < 1)
        cols = 1;
    visible_rows = (int)(list.height / cell_h);
    if(visible_rows < 1)
        visible_rows = 1;
    max_scroll = (manager->entry_count + cols - 1) / cols - visible_rows;
    if(max_scroll < 0)
        max_scroll = 0;
    if(manager->focused && hit(list)) {
        wheel = GetMouseWheelMove();
        if(wheel > 0.0f)
            manager->scroll -= 1;
        else if(wheel < 0.0f)
            manager->scroll += 1;
    }
    if(manager->scroll < 0)
        manager->scroll = 0;
    if(manager->scroll > max_scroll)
        manager->scroll = max_scroll;

    clamp_cursor(manager);
    handle_keyboard(manager, visible_rows * cols);

    BeginScissorMode((int)list.x, (int)list.y, (int)list.width,
                     (int)list.height);
    for(row = 0; row < visible_rows + 1; row++) {
        for(col = 0; col < cols; col++) {
            int index = (manager->scroll + row) * cols + col;
            FileEntry *entry;
            Rectangle cell;
            Rectangle icon;
            Rectangle label;
            int hover;
            int label_w;

            if(index >= manager->entry_count)
                continue;
            entry = &manager->entries[index];
            cell.x = list.x + col * cell_w + 10;
            cell.y = list.y + row * cell_h + 8;
            cell.width = cell_w - 16;
            cell.height = cell_h - 10;
            icon.x = cell.x + (cell.width - icon_size) * 0.5f;
            icon.y = cell.y + 8;
            icon.width = icon_size;
            icon.height = icon_size;
            label.x = cell.x + 4;
            label.y = cell.y + 69;
            label.width = cell.width - 8;
            label.height = 20;
            hover = manager->focused && hit(cell);

            if(entry->selected)
                DrawRectangleRounded(cell, 0.08f, 6,
                                     Fade(GetThemeButtonHover(), 0.72f));
            else if(hover)
                DrawRectangleRounded(cell, 0.08f, 6,
                                     Fade(GetThemeButton(), 0.36f));
            draw_icon(icon, entry->is_dir);
            BeginScissorMode((int)label.x, (int)label.y,
                             (int)label.width, (int)label.height);
            label_w = MeasureTextWidth(entry->name, Text12, NULL);
            draw_label(entry->name,
                 (int)(label.x + (label.width - label_w) * 0.5f),
                 (int)label.y + 3, Text12,
                 entry->readable ? GetThemeText() : GetThemeIcon());
            EndScissorMode();
            if(hover && IsMouseButtonPressed(MOUSE_BUTTON_LEFT)) {
                double now = GetTime();
                int double_click = manager->last_click_index == index &&
                                   now - manager->last_click_time < 0.38;

                if(shift_down())
                    select_range(manager, index);
                else if(mod_down())
                    toggle_selection(manager, index);
                else
                    select_one(manager, index);
                manager->last_click_index = index;
                manager->last_click_time = now;
                if(double_click && !mod_down() && !shift_down())
                    open_selected(manager);
            } else if(hover && IsMouseButtonPressed(MOUSE_BUTTON_RIGHT)) {
                if(!entry->selected)
                    select_one(manager, index);
            }
        }
    }
    EndScissorMode();

    if(manager->entry_count == 0 && manager->error[0] == '\0')
        draw_label("Empty folder", (int)list.x + 16, (int)list.y + 16, Text14,
             GetThemeIcon());
}

static void
perform_menu_command(FileManager *manager, int command)
{
    int index;

    switch(command) {
    case 2001:
        open_selected(manager);
        break;
    case 2002:
        index = first_selected(manager);
        if(index >= 0 && FileManagerSelectedCount(manager) == 1)
            start_prompt(manager, FILE_DIALOG_RENAME, manager->entries[index].name);
        break;
    case 2003:
        (void)FileManagerCopySelection(manager, 0);
        break;
    case 2004:
        (void)FileManagerCopySelection(manager, 1);
        break;
    case 2005:
        (void)FileManagerPaste(manager);
        break;
    case 2006:
        manager->dialog = FILE_DIALOG_TRASH;
        break;
    case 2007:
        manager->dialog = FILE_DIALOG_DELETE;
        break;
    case 2008:
        start_prompt(manager, FILE_DIALOG_NEW_FOLDER, "New Folder");
        break;
    case 2009:
        start_prompt(manager, FILE_DIALOG_NEW_FILE, "New File.txt");
        break;
    case 2010:
        (void)FileManagerDuplicateSelection(manager);
        break;
    case 2011:
        (void)FileManagerMakeLinkSelection(manager);
        break;
    case 2012:
        start_prompt(manager, FILE_DIALOG_SEARCH, manager->search_query);
        break;
    case 2013:
        show_properties(manager);
        break;
    case 2014:
        (void)FileManagerRestoreSelection(manager);
        break;
    default:
        break;
    }
}

static void
draw_context_menu(FileManager *manager, Rectangle trigger)
{
    int selected = FileManagerSelectedCount(manager);
    MenuItem items[17];
    MenuProps in;
    MenuResult out;
    int command;
    int trash_view = is_trash_view(manager);

    memset(&in, 0, sizeof(in));

    items[0].kind = MenuCommand;
    items[0].label = "Open";
    items[0].accelerator = "Enter";
    items[0].id = 2001;
    items[0].disabled = selected <= 0;
    items[0].checked = 0;
    items[0].submenu = NULL;
    items[0].submenu_count = 0;
    items[1].kind = MenuCommand;
    items[1].label = "Rename";
    items[1].accelerator = "F2";
    items[1].id = 2002;
    items[1].disabled = selected != 1;
    items[1].checked = 0;
    items[1].submenu = NULL;
    items[1].submenu_count = 0;
    items[2].kind = MenuCommand;
    items[2].label = "Restore";
    items[2].accelerator = NULL;
    items[2].id = 2014;
    items[2].disabled = selected <= 0 || !trash_view;
    items[2].checked = 0;
    items[2].submenu = NULL;
    items[2].submenu_count = 0;
    items[3].kind = MenuSeparator;
    items[3].label = NULL;
    items[3].accelerator = NULL;
    items[3].id = 0;
    items[3].disabled = 0;
    items[3].checked = 0;
    items[3].submenu = NULL;
    items[3].submenu_count = 0;
    items[4].kind = MenuCommand;
    items[4].label = "Copy";
    items[4].accelerator = "Ctrl+C";
    items[4].id = 2003;
    items[4].disabled = selected <= 0;
    items[4].checked = 0;
    items[4].submenu = NULL;
    items[4].submenu_count = 0;
    items[5].kind = MenuCommand;
    items[5].label = "Cut";
    items[5].accelerator = "Ctrl+X";
    items[5].id = 2004;
    items[5].disabled = selected <= 0;
    items[5].checked = 0;
    items[5].submenu = NULL;
    items[5].submenu_count = 0;
    items[6].kind = MenuCommand;
    items[6].label = "Paste";
    items[6].accelerator = "Ctrl+V";
    items[6].id = 2005;
    items[6].disabled = manager->clipboard.count <= 0;
    items[6].checked = 0;
    items[6].submenu = NULL;
    items[6].submenu_count = 0;
    items[7].kind = MenuCommand;
    items[7].label = "Duplicate";
    items[7].accelerator = NULL;
    items[7].id = 2010;
    items[7].disabled = selected <= 0;
    items[7].checked = 0;
    items[7].submenu = NULL;
    items[7].submenu_count = 0;
    items[8].kind = MenuCommand;
    items[8].label = "Make Link";
    items[8].accelerator = NULL;
    items[8].id = 2011;
    items[8].disabled = selected <= 0;
    items[8].checked = 0;
    items[8].submenu = NULL;
    items[8].submenu_count = 0;
    items[9].kind = MenuSeparator;
    items[9].label = NULL;
    items[9].accelerator = NULL;
    items[9].id = 0;
    items[9].disabled = 0;
    items[9].checked = 0;
    items[9].submenu = NULL;
    items[9].submenu_count = 0;
    items[10].kind = MenuCommand;
    items[10].label = "Move to Trash";
    items[10].accelerator = "Del";
    items[10].id = 2006;
    items[10].disabled = selected <= 0;
    items[10].checked = 0;
    items[10].submenu = NULL;
    items[10].submenu_count = 0;
    items[11].kind = MenuCommand;
    items[11].label = "Delete";
    items[11].accelerator = "Shift+Del";
    items[11].id = 2007;
    items[11].disabled = selected <= 0;
    items[11].checked = 0;
    items[11].submenu = NULL;
    items[11].submenu_count = 0;
    items[12].kind = MenuSeparator;
    items[12].label = NULL;
    items[12].accelerator = NULL;
    items[12].id = 0;
    items[12].disabled = 0;
    items[12].checked = 0;
    items[12].submenu = NULL;
    items[12].submenu_count = 0;
    items[13].kind = MenuCommand;
    items[13].label = "Search";
    items[13].accelerator = "Ctrl+F";
    items[13].id = 2012;
    items[13].disabled = 0;
    items[13].checked = 0;
    items[13].submenu = NULL;
    items[13].submenu_count = 0;
    items[14].kind = MenuCommand;
    items[14].label = "Properties";
    items[14].accelerator = "Alt+Enter";
    items[14].id = 2013;
    items[14].disabled = selected <= 0;
    items[14].checked = 0;
    items[14].submenu = NULL;
    items[14].submenu_count = 0;
    items[15].kind = MenuCommand;
    items[15].label = "New Folder";
    items[15].accelerator = NULL;
    items[15].id = 2008;
    items[15].disabled = 0;
    items[15].checked = 0;
    items[15].submenu = NULL;
    items[15].submenu_count = 0;
    items[16].kind = MenuCommand;
    items[16].label = "New File";
    items[16].accelerator = NULL;
    items[16].id = 2009;
    items[16].disabled = 0;
    items[16].checked = 0;
    items[16].submenu = NULL;
    items[16].submenu_count = 0;

    in.id = 3100;
    in.mode = MenuModeContext;
    in.bounds = trigger;
    in.trigger = trigger;
    in.items = items;
    in.item_count = 17;
    in.open = &manager->context_open;
    in.x = &manager->context_x;
    in.y = &manager->context_y;

    out = Menu(in);
    command = out.activated_id;
    if(command != 0)
        perform_menu_command(manager, command);
}

static void
draw_status(FileManager *manager, Rectangle status)
{
    char text[256];
    int selected = FileManagerSelectedCount(manager);
    int folders = 0;
    int files = 0;
    int i;

    for(i = 0; i < manager->entry_count; i++) {
        if(manager->entries[i].is_dir)
            folders++;
        else
            files++;
    }

    DrawRectangleRec(status, opaque_color(GetThemeSurface()));
    if(manager->search_active)
        snprintf(text, sizeof(text), "Search '%.120s': %d result%s | %d selected%s",
                 manager->search_query, manager->entry_count,
                 manager->entry_count == 1 ? "" : "s", selected,
                 manager->clipboard.count > 0 ?
                     (manager->clipboard.mode == FILE_CLIPBOARD_CUT ?
                          " | cut ready" : " | copy ready") : "");
    else
        snprintf(text, sizeof(text), "%d folder%s | %d file%s | %d selected%s",
                 folders, folders == 1 ? "" : "s",
                 files, files == 1 ? "" : "s", selected,
                 manager->clipboard.count > 0 ?
                     (manager->clipboard.mode == FILE_CLIPBOARD_CUT ?
                          " | cut ready" : " | copy ready") : "");
    draw_label(text, (int)status.x + 10, (int)status.y + 7, Text12, GetThemeIcon());
    if(manager->error[0] != '\0')
        draw_text_fit_right(manager->error, (int)status.x + 240,
                            (int)status.y + 7,
                            (int)status.width - 250, Text12, RED);
}

static void
draw_dialogs(FileManager *manager)
{
    static const ModalAction ok_actions[] = {{"OK", 0, 0, 0}};
    static const ModalAction prompt_actions[] = {
        {"Cancel", 0, 0, 0},
        {"OK", 0, 0, 0}
    };
    ModalAction confirm_actions[2];
    ModalProps in;
    const char *prompt_title;
    int result;

    if(manager == NULL || manager->dialog == FILE_DIALOG_NONE)
        return;
    if(manager->dialog == FILE_DIALOG_PROPERTIES) {
        memset(&in, 0, sizeof(in));
        in.title = "Properties";
        in.message = manager->dialog_message;
        in.actions = ok_actions;
        in.action_count = 1;
        result = Modal(in);
        if(result != 0)
            manager->dialog = FILE_DIALOG_NONE;
        return;
    }
    if(manager->dialog == FILE_DIALOG_DELETE ||
       manager->dialog == FILE_DIALOG_TRASH) {
        int selected = FileManagerSelectedCount(manager);
        char msg[128];

        snprintf(msg, sizeof(msg), "%s %d selected item%s?",
                 manager->dialog == FILE_DIALOG_TRASH ? "Move" : "Permanently delete",
                 selected, selected == 1 ? "" : "s");
        confirm_actions[0].label = "Cancel";
        confirm_actions[0].tone = ButtonToneNeutral;
        confirm_actions[0].emphasis = ButtonEmphasisFilled;
        confirm_actions[0].disabled = 0;
        confirm_actions[1].label =
            manager->dialog == FILE_DIALOG_TRASH ? "Trash" : "Delete";
        confirm_actions[1].tone = ButtonToneNeutral;
        confirm_actions[1].emphasis = ButtonEmphasisFilled;
        confirm_actions[1].disabled = 0;
        memset(&in, 0, sizeof(in));
        in.title = manager->dialog == FILE_DIALOG_TRASH ? "Move to Trash" :
                                                          "Delete";
        in.message = msg;
        in.actions = confirm_actions;
        in.action_count = 2;
        result = Modal(in);
        if(result == 1 || result == -1)
            manager->dialog = FILE_DIALOG_NONE;
        else if(result == 2) {
            FileDialogKind dialog = manager->dialog;
            manager->dialog = FILE_DIALOG_NONE;
            (void)FileManagerDeleteSelection(manager,
                                             dialog == FILE_DIALOG_TRASH);
        }
        return;
    }

    prompt_title =
        manager->dialog == FILE_DIALOG_RENAME ? "Rename" :
        manager->dialog == FILE_DIALOG_NEW_FOLDER ? "New Folder" :
        manager->dialog == FILE_DIALOG_NEW_FILE ? "New File" :
        manager->dialog == FILE_DIALOG_SEARCH ? "Search" : "Go to Location";
    memset(&in, 0, sizeof(in));
    in.title = prompt_title;
    in.actions = prompt_actions;
    in.action_count = 2;
    in.text = manager->dialog_text;
    in.text_size = (int)sizeof(manager->dialog_text);
    in.cursor_position = &manager->dialog_cursor;
    in.focused = &manager->dialog_focused;
    result = Modal(in);
    if(result == 1 || result == -1) {
        manager->dialog = FILE_DIALOG_NONE;
    } else if(result == 2) {
        FileDialogKind dialog = manager->dialog;

        manager->dialog = FILE_DIALOG_NONE;
        if(dialog == FILE_DIALOG_RENAME)
            (void)FileManagerRenameSelection(manager, manager->dialog_text);
        else if(dialog == FILE_DIALOG_NEW_FOLDER)
            (void)FileManagerCreateFolder(manager, manager->dialog_text);
        else if(dialog == FILE_DIALOG_NEW_FILE)
            (void)FileManagerCreateFile(manager, manager->dialog_text);
        else if(dialog == FILE_DIALOG_SEARCH)
            (void)FileManagerSearch(manager, manager->dialog_text);
        else if(dialog == FILE_DIALOG_LOCATION)
            (void)FileManagerOpenPathTracked(manager, manager->dialog_text);
    }
}

void
FileManagerDraw(FileManager *manager, Rectangle viewport)
{
    Rectangle tabs;
    Rectangle toolbar;
    Rectangle sidebar;
    Rectangle list;
    Rectangle status;
    int sidebar_w = 176;
    int tab_h = manager->tab_count > 1 ? 32 : 0;
    int toolbar_h = 70;
    int status_h = 28;

    if(manager == NULL)
        return;
    tabs.x = viewport.x;
    tabs.y = viewport.y;
    tabs.width = viewport.width;
    tabs.height = (float)tab_h;
    toolbar.x = viewport.x;
    toolbar.y = viewport.y + tab_h;
    toolbar.width = viewport.width;
    toolbar.height = (float)toolbar_h;
    sidebar.x = viewport.x;
    sidebar.y = viewport.y + tab_h + toolbar_h;
    sidebar.width = (float)sidebar_w;
    sidebar.height = viewport.height - tab_h - toolbar_h - status_h;
    list.x = viewport.x + sidebar_w;
    list.y = viewport.y + tab_h + toolbar_h;
    list.width = viewport.width - sidebar_w;
    list.height = viewport.height - tab_h - toolbar_h - status_h;
    status.x = viewport.x;
    status.y = viewport.y + viewport.height - status_h;
    status.width = viewport.width;
    status.height = (float)status_h;

    DrawRectangleRec(viewport, opaque_color(GetThemeBackground()));
    if(tab_h > 0)
        draw_tabs(manager, tabs);
    draw_toolbar(manager, toolbar);
    draw_places(manager, sidebar);
    draw_rows(manager, list);
    draw_context_menu(manager, list);
    draw_status(manager, status);
    draw_dialogs(manager);
}
