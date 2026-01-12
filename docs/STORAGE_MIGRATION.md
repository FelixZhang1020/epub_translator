# Storage Architecture Migration

**Date:** 2026-01-09
**Status:** ✅ Completed

## Overview

Successfully migrated from global centralized storage to project-scoped storage architecture for better organization and maintainability.

---

## Changes Made

### 1. **New Project Storage Structure**

Each project now has its own isolated directory:

```
projects/{project_id}/
├── config.json                   # Project configuration
├── variables.json                # Custom template variables (optional)
├── prompts/                      # Custom prompt templates
│   ├── analysis/
│   │   └── user.md
│   ├── translation/
│   │   └── user.md
│   ├── optimization/
│   └── proofreading/
├── uploads/                      # ⭐ NEW: Original and reference EPUBs
│   ├── original.epub             # Uploaded source EPUB
│   └── reference.epub            # Reference translation (optional)
├── exports/                      # ⭐ NEW: Generated output files
│   ├── translated.epub           # Translation-only EPUB
│   └── bilingual.epub            # Bilingual EPUB
├── content/                      # Reserved (database-backed)
└── cache/                        # Reserved (future LLM caching)
```

### 2. **Architecture Changes**

#### Before (Global Storage):
```
backend/
├── uploads/
│   ├── {filename}.epub
│   └── ref_{project_id}_{filename}.epub
└── outputs/
    ├── {project_id}_translated.epub
    └── {project_id}_bilingual.epub
```

#### After (Project-Scoped Storage):
```
projects/{project_id}/
├── uploads/
│   ├── original.epub
│   └── reference.epub
└── exports/
    ├── translated.epub
    └── bilingual.epub
```

---

## Files Modified

### New Files Created:
1. **`backend/app/core/project_storage.py`** - Storage management utilities
2. **`backend/scripts/migrate_to_project_storage.py`** - Migration script

### Updated Files:
1. **`backend/app/api/v1/routes/upload.py`**
   - Uses `ProjectStorage` for file locations
   - Creates project structure on upload
   - Cleans up entire project directory on delete

2. **`backend/app/api/v1/routes/export.py`**
   - Exports to project-scoped `exports/` folder
   - Simplified filenames (no project_id prefix)

3. **`backend/app/api/v1/routes/reference.py`**
   - Stores reference EPUBs in project uploads folder

4. **`backend/app/core/epub/generator.py`**
   - Accepts optional `output_dir` parameter
   - Uses project-scoped exports directory

---

## Benefits

### ✅ Better Organization
- Each project is self-contained
- Easy to find all files related to a project
- No filename collisions between projects

### ✅ Easier Backup
- Copy one folder = backup entire project
- Selective project archiving is simple

### ✅ Cleaner Deletion
- Delete project folder = remove all artifacts
- No orphaned files in global directories

### ✅ Portability
- Move projects between systems by copying folders
- Share specific projects without full database

### ✅ Multi-User Ready
- Better isolation for future multi-user support
- Per-project access control possible

---

## Migration Status

### ✅ Existing Data Migrated

Successfully migrated 1 existing project:
- **Project:** Knowing God (J. I. Packer)
- **Original EPUB:** Moved to `projects/{id}/uploads/original.epub`
- **Reference EPUB:** Moved to `projects/{id}/uploads/reference.epub`
- **Database:** Updated with new file paths

### Files Moved:
- Original uploads: `backend/uploads/` → `projects/{id}/uploads/`
- Reference uploads: `backend/uploads/` → `projects/{id}/uploads/`
- Exports: `backend/outputs/` → `projects/{id}/exports/` (when generated)

---

## Usage Guide

### For Developers

#### 1. **Accessing Project Files**

```python
from app.core.project_storage import ProjectStorage

# Get project directory paths
uploads_dir = ProjectStorage.get_uploads_dir(project_id)
exports_dir = ProjectStorage.get_exports_dir(project_id)

# Get specific file paths
original_epub = ProjectStorage.get_original_epub_path(project_id)
reference_epub = ProjectStorage.get_reference_epub_path(project_id)
translated_epub = ProjectStorage.get_translated_epub_path(project_id)
bilingual_epub = ProjectStorage.get_bilingual_epub_path(project_id)
```

#### 2. **Creating New Project**

```python
# Initialize directory structure
ProjectStorage.initialize_project_structure(project_id)

# Save files to appropriate locations
original_path = ProjectStorage.get_original_epub_path(project_id)
shutil.copy(uploaded_file, original_path)
```

#### 3. **Deleting Project**

```python
# Delete all project files
ProjectStorage.delete_project(project_id)
```

### For Operations

#### Backup Individual Project
```bash
# Copy entire project folder
tar -czf project_backup.tar.gz projects/{project_id}/
```

#### Archive Old Projects
```bash
# Move inactive projects to archive
mv projects/{project_id} archive/
```

#### Disk Space Management
```python
# Get project size
size_bytes = ProjectStorage.get_project_size(project_id)

# List all exports
exports = ProjectStorage.list_exports(project_id)
```

---

## Database Schema

### No Schema Changes Required

The migration only updates the `original_file_path` field in the `projects` table. All other data structures remain unchanged:

- **Translations:** Still stored in database (not files)
- **Chapters/Paragraphs:** Still stored in database
- **Analysis Results:** Still stored in database

---

## Future Enhancements

### Planned Features:

#### 1. **LLM Response Caching** (cache/ folder)
```
projects/{id}/cache/
├── llm_responses/
│   ├── {hash_of_prompt}.json
│   └── embeddings/
└── analysis_results.json
```

**Benefits:**
- Save API costs on re-translation
- Faster development/testing
- Offline mode possible

#### 2. **Export Versioning**
```
projects/{id}/exports/
├── translated_v1.epub
├── translated_v2.epub
└── bilingual_latest.epub
```

#### 3. **Content Snapshots** (content/ folder)
```
projects/{id}/content/
├── source_snapshot.json    # Original text backup
└── translation_v1.json     # Translation backup
```

**Benefits:**
- Rollback capability
- External tool integration
- Data portability

---

## Testing Checklist

### ✅ Completed Tests:

- [x] Migration script (dry-run)
- [x] Migration script (actual run)
- [x] Files moved to correct locations
- [x] Database updated with new paths
- [x] Old files removed from global directories

### 🔄 Remaining Tests:

- [ ] Upload new EPUB file
- [ ] Generate translated EPUB export
- [ ] Generate bilingual EPUB export
- [ ] Upload reference EPUB
- [ ] Delete project and verify cleanup
- [ ] Test with multiple projects

---

## Rollback Procedure

If issues arise, rollback is possible:

### 1. **Restore Database**
```sql
UPDATE projects
SET original_file_path = '/path/to/backend/uploads/{filename}.epub'
WHERE id = '{project_id}';
```

### 2. **Move Files Back**
```bash
# Move files back to global directories
mv projects/{id}/uploads/original.epub backend/uploads/{original_filename}.epub
mv projects/{id}/uploads/reference.epub backend/uploads/ref_{id}_{filename}.epub
```

### 3. **Revert Code**
```bash
git revert <commit_hash>
```

---

## Support

For issues or questions:
1. Check migration logs in `backend/scripts/migrate_to_project_storage.py`
2. Verify file permissions on `projects/` directory
3. Ensure database is accessible and updated
4. Check backend logs for file path errors

---

## Credits

**Implemented by:** Claude Code
**Reviewed by:** User
**Migration Date:** 2026-01-09
