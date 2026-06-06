package com.fanbook.reader.application;

import com.fanbook.auth.application.CurrentUser;
import com.fanbook.auth.application.CurrentUserProvider;
import com.fanbook.auth.domain.UserRole;
import com.fanbook.book.application.BookAccessService;
import com.fanbook.book.domain.BookEntity;
import com.fanbook.book.domain.SegmentEntity;
import com.fanbook.book.infrastructure.SegmentRepository;
import com.fanbook.common.error.ErrorCode;
import com.fanbook.common.error.FanbookException;
import com.fanbook.reader.api.CreateNoteRequest;
import com.fanbook.reader.api.SegmentNoteResponse;
import com.fanbook.reader.api.UpdateNoteRequest;
import com.fanbook.reader.domain.SegmentNoteEntity;
import com.fanbook.reader.infrastructure.SegmentNoteRepository;
import java.time.LocalDate;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class SegmentNoteService {

    private final SegmentRepository segmentRepository;
    private final SegmentNoteRepository noteRepository;
    private final CurrentUserProvider currentUserProvider;
    private final BookAccessService bookAccessService;

    public SegmentNoteService(
            SegmentRepository segmentRepository,
            SegmentNoteRepository noteRepository,
            CurrentUserProvider currentUserProvider,
            BookAccessService bookAccessService
    ) {
        this.segmentRepository = segmentRepository;
        this.noteRepository = noteRepository;
        this.currentUserProvider = currentUserProvider;
        this.bookAccessService = bookAccessService;
    }

    @Transactional
    public SegmentNoteResponse create(Long segmentId, CreateNoteRequest request) {
        SegmentEntity segment = requireSegment(segmentId);
        bookAccessService.requireAccessToSegment(segment);
        CurrentUser currentUser = currentUserProvider.requireCurrentUser();
        SegmentNoteEntity note = noteRepository.save(new SegmentNoteEntity(
                segment.getBook(),
                segment,
                value(request == null ? null : request.content()),
                clean(request == null ? null : request.highlightColor()),
                currentUser.username()
        ));
        return toResponse(note);
    }

    @Transactional(readOnly = true)
    public List<SegmentNoteResponse> notes(Long segmentId) {
        SegmentEntity segment = requireSegment(segmentId);
        bookAccessService.requireAccessToSegment(segment);
        return noteRepository.findBySegmentIdOrderByCreatedAtAscIdAsc(segmentId).stream()
                .map(this::toResponse)
                .toList();
    }

    @Transactional
    public SegmentNoteResponse update(Long noteId, UpdateNoteRequest request) {
        SegmentNoteEntity note = requireNote(noteId);
        bookAccessService.requireAccess(note.getBook());
        requireOwnerOrAdmin(note);
        note.update(
                value(request == null ? null : request.content()),
                clean(request == null ? null : request.highlightColor())
        );
        return toResponse(note);
    }

    @Transactional
    public void delete(Long noteId) {
        SegmentNoteEntity note = requireNote(noteId);
        bookAccessService.requireAccess(note.getBook());
        requireOwnerOrAdmin(note);
        noteRepository.delete(note);
    }

    @Transactional(readOnly = true)
    public String exportMarkdown(Long bookId) {
        BookEntity book = bookAccessService.requireAccessibleBook(bookId);
        StringBuilder markdown = new StringBuilder("# My Notes - ")
                .append(book.getTitle())
                .append("\n\n");
        String previousChapter = null;
        for (SegmentNoteEntity note : noteRepository.findByBookIdForExport(bookId)) {
            SegmentEntity segment = note.getSegment();
            String chapterTitle = segment.getChapter().getTitle();
            if (!chapterTitle.equals(previousChapter)) {
                markdown.append("## ").append(chapterTitle).append("\n\n");
                previousChapter = chapterTitle;
            }
            LocalDate createdDate = note.getCreatedAt() == null ? LocalDate.now() : note.getCreatedAt().toLocalDate();
            markdown.append("**Segment ").append(segment.getSegmentOrder()).append("** (").append(createdDate).append(")\n");
            markdown.append("> ").append(segment.getSourceText()).append("\n");
            if (segment.getTranslatedText() != null) {
                markdown.append("> ").append(segment.getTranslatedText()).append("\n");
            }
            markdown.append("\n**Note:** ").append(note.getNoteContent()).append("\n\n");
        }
        return markdown.toString();
    }

    private SegmentNoteResponse toResponse(SegmentNoteEntity note) {
        return new SegmentNoteResponse(
                note.getId(),
                note.getBook().getId(),
                note.getSegment().getId(),
                note.getNoteContent(),
                note.getHighlightColor(),
                note.getCreatedBy(),
                note.getCreatedAt(),
                note.getUpdatedAt()
        );
    }

    private SegmentEntity requireSegment(Long segmentId) {
        return segmentRepository.findById(segmentId)
                .orElseThrow(() -> new FanbookException(ErrorCode.INVALID_REQUEST, HttpStatus.NOT_FOUND, "Segment '" + segmentId + "' was not found."));
    }

    private SegmentNoteEntity requireNote(Long noteId) {
        return noteRepository.findById(noteId)
                .orElseThrow(() -> new FanbookException(ErrorCode.INVALID_REQUEST, HttpStatus.NOT_FOUND, "Note '" + noteId + "' was not found."));
    }

    private void requireOwnerOrAdmin(SegmentNoteEntity note) {
        CurrentUser currentUser = currentUserProvider.requireCurrentUser();
        if (!currentUser.hasRole(UserRole.ADMIN) && !note.getCreatedBy().equals(currentUser.username())) {
            throw new FanbookException(ErrorCode.FORBIDDEN, HttpStatus.FORBIDDEN, "Only the note owner or an admin can change this note.");
        }
    }

    private String value(String candidate) {
        return candidate == null ? "" : candidate;
    }

    private String clean(String candidate) {
        return candidate == null || candidate.isBlank() ? null : candidate.trim();
    }
}
