# Analysis Progress Persistence Solution

## Problem
When users refresh the page during book analysis, all progress is lost because:
- Analysis uses streaming SSE without persistent task tracking
- Frontend state (`isAnalyzing`) is stored in component memory
- No backend task record to resume from

## Solution: Add AnalysisTask Model

### 1. Create Database Model

```python
# backend/app/models/database/analysis_task.py
class AnalysisTask(Base):
    """Analysis task for tracking streaming analysis progress."""

    __tablename__ = "analysis_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"))

    # Task status
    status: Mapped[str] = mapped_column(String(50))  # pending, processing, completed, failed
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    current_step: Mapped[str] = mapped_column(String(50))  # loading, sampling, analyzing, etc.
    step_message: Mapped[Optional[str]] = mapped_column(Text)

    # LLM config
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
```

### 2. Modify Analysis Service

**On analysis start:**
- Create `AnalysisTask` record with status='processing'
- Clear old analysis data immediately
- Update task progress during streaming

**On each progress event:**
```python
# Update task progress in database
task.progress = event['progress']
task.current_step = event['step']
task.step_message = event['message']
await db.commit()
```

**On completion:**
- Save final analysis data
- Update task status='completed'

**On error/cancel:**
- Update task status='failed' or 'cancelled'
- Keep task record for user reference

### 3. Modify Frontend

**ProjectLayout:**
- Include `analysis_progress` in workflow status (similar to translation_progress)
- Poll every 5 seconds to get latest task status

**AnalysisPage:**
- On mount, check if there's an active analysis task from backend
- If task exists and is 'processing', show progress UI
- Sync local state with backend task state

### 4. Benefits

✅ Progress persists across page refreshes
✅ Users can see "Analysis in progress" even after refresh
✅ Consistent with translation/proofreading node behavior
✅ Better error tracking and debugging

### 5. Implementation Steps

1. Create migration for `analysis_tasks` table
2. Add `AnalysisTask` model
3. Update `analyze_book_streaming()` to create and update task
4. Update `/workflow/{project_id}/status` API to include analysis progress
5. Update frontend `ProjectLayout` to read analysis progress
6. Update `AnalysisPage` to sync with backend task state

## Alternative: Simple Status Flag

If full task tracking is too complex, add minimal fields to `BookAnalysis`:

```python
class BookAnalysis(Base):
    # ... existing fields ...

    # Add these fields:
    is_analyzing: Mapped[bool] = mapped_column(Boolean, default=False)
    analysis_progress: Mapped[float] = mapped_column(Float, default=0.0)
    analysis_step: Mapped[Optional[str]] = mapped_column(String(50))
    analysis_step_message: Mapped[Optional[str]] = mapped_column(Text)
```

**Pros:**
- Simpler implementation
- No new table needed

**Cons:**
- Less clean data model
- Mixes analysis result with task status
- Can't track multiple analysis attempts

## Recommendation

Implement full `AnalysisTask` model for consistency with other nodes and better long-term maintainability.
